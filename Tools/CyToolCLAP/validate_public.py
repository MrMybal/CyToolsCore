"""Reproducible real inference through the SDK; not an independent benchmark."""
import asyncio
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from model_config import ROOT,MODEL_ID,REVISION
from tool import create_runtime

def main():
    sources=json.loads((ROOT/'audio/SOURCES.json').read_text('utf-8'))
    reports=ROOT/'reports'
    reports.mkdir(exist_ok=True)
    results=[]
    with create_runtime(reports/'runtime') as runtime:
        alice=runtime.authenticate(runtime.create_client('public-audio-test-A')['token'])
        bob=runtime.authenticate(runtime.create_client('public-audio-test-B')['token'])
        sessions={actor:runtime.create_session(actor)['sessionId'] for actor in (alice,bob)}
        jobs=[]
        for index,source in enumerate(sources):
            actor=(alice,bob)[index%2]
            job=runtime.submit(actor,sessions[actor],'classify_audio',{'audio_file':source['file'],'preset':'general','max_seconds':30},
                backend_id='transformers-cpu',model_id='clap-htsat-unfused',execution_timeout=600)
            jobs.append((source,actor,job))
        for source,actor,job in jobs:
            result=runtime.wait(actor,job['jobId'],timeout=600)
            assert result['state']=='Completed',result['error']
            output=result['outputs']
            actual=output['matches'][0]['label']
            entry={'file':source['file'],'expected':source['expected_label'],'actual':actual,'correct':actual==source['expected_label'],
                   'job_id':job['jobId'],'job_seconds':(datetime.fromisoformat(result['finishedAt'])-datetime.fromisoformat(result['startedAt'])).total_seconds(),
                   'output':output,'source':source}
            results.append(entry)
            print(json.dumps({'file':entry['file'],'expected':entry['expected'],'actual':actual,'correct':entry['correct'],
                              'job_seconds':entry['job_seconds']},ensure_ascii=False),flush=True)
        assert len(runtime.list_jobs(alice))==2 and len(runtime.list_jobs(bob))==2
        assert runtime.ledger.snapshot()['reservations']=={}
        evidence={'timestamp':datetime.now(timezone.utc).isoformat(),'model':MODEL_ID,'revision':REVISION,'device':'cpu',
                  'candidate_set':'general (28 descriptions)','samples':results,'passed':sum(r['correct'] for r in results),
                  'total':len(results),'multi_client_isolation':True,'reservations_released':True,
                  'limitation':'Small functional test; samples may overlap CLAP training data. No song-title recognition.'}
        (reports/'public-validation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    asyncio.run(check_mcp())

async def check_mcp():
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    parameters=StdioServerParameters(command=sys.executable,args=[str(ROOT/'tool.py'),'--data-dir',str(ROOT/'reports/mcp-runtime'),'mcp'],
                                    env={**os.environ,'PYTHONIOENCODING':'utf-8'})
    async with stdio_client(parameters) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert 'op_classify_audio' in {t.name for t in tools.tools}
            response=await session.call_tool('op_classify_audio',{'parameters':{'audio_file':'trumpet.ogg','preset':'general'}})
            assert not response.isError,response
            job=json.loads(response.content[0].text)
            deadline=time.monotonic()+120
            while job['state'] not in ('Completed','Failed','Cancelled'):
                assert time.monotonic()<deadline,'MCP timeout'
                await asyncio.sleep(.1)
                response=await session.call_tool('cy_get_job',{'jobId':job['jobId']})
                assert not response.isError,response
                job=json.loads(response.content[0].text)
            assert job['state']=='Completed',job.get('error')
            evidence={'transport':'MCP stdio','state':job['state'],'top_label':job['outputs']['matches'][0]['label'],
                      'output':job['outputs']}
            (ROOT/'reports/mcp-validation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'MCP':evidence['state'],'label':evidence['top_label']},ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
