import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import pytest
from cytools_core import CyToolError
from cytools_core.transports.http import make_server,HTTPClient
from cytools_core.scaffold import create_project


def test_http_two_clients_one_scheduler(runtime):
    alice,bob=[runtime.create_client(name) for name in ('Alice','Bob')]
    server=make_server(runtime)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url=f'http://127.0.0.1:{server.server_port}/v1'
    try:
        a,b=HTTPClient(url,alice['token']),HTTPClient(url,bob['token'])
        s=a.call('CreateSession')['sessionId']
        job=a.call('SubmitJob',sessionId=s,operationId='echo',parameters={'text':'HTTP'})
        assert b.call('ListJobs')==[]
        with pytest.raises(CyToolError): b.call('GetJob',jobId=job['jobId'])
        with pytest.raises(CyToolError): HTTPClient(url,'invalid').call('DescribeTool')
        result=runtime.wait(runtime.authenticate(alice['token']),job['jobId'])
        assert result['outputs']=={'text':'HTTP'}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_cli_and_generated_project(tmp_path):
    project=create_project(tmp_path/'CyToolSample','CyToolSample','cy.tool.sample')
    with pytest.raises(ValueError): create_project(project,'CyToolSample','cy.tool.sample')
    result=subprocess.run([sys.executable,'tool.py','invoke','echo','--params-file','params.json'],cwd=project,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['outputs']=={'text':'Hello CyTools'}
    result=subprocess.run([sys.executable,'-m','unittest','-v'],cwd=project,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr


def test_mcp_real_stdio(tmp_path):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def scenario():
        parameters=StdioServerParameters(command=sys.executable,args=['-m','cytool_test','--data-dir',str(tmp_path),'mcp'])
        async with stdio_client(parameters) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                tools=await session.list_tools()
                assert 'op_echo' in {t.name for t in tools.tools}
                by_name={t.name:t for t in tools.tools}
                assert {'cy_describe_operation','cy_estimate','cy_list_models','cy_system_resources'} <= by_name.keys()
                assert 'executionTimeout' in by_name['op_echo'].inputSchema['properties']
                contract=await session.call_tool('cy_describe_operation',{'operationId':'echo'})
                assert json.loads(contract.content[0].text)['outputSchema']['properties']['text']['type']=='string'
                estimate=await session.call_tool('cy_estimate',{'operationId':'echo','parameters':{'text':'MCP'}})
                assert not estimate.isError
                result=await session.call_tool('op_echo',{'parameters':{'text':'MCP'},'queueTimeout':10,'executionTimeout':10})
                assert not result.isError,result
                job=json.loads(result.content[0].text)
                for _ in range(100):
                    result=await session.call_tool('cy_get_job',{'jobId':job['jobId']})
                    job=json.loads(result.content[0].text)
                    if job['state']=='Completed': break
                    await asyncio.sleep(.02)
                assert job['outputs']=={'text':'MCP'}
                invalid=await session.call_tool('op_echo',{'parameters':{'text':8}})
                assert invalid.isError
    asyncio.run(scenario())


def test_desktop_scaffold_clean_layout_and_external_cwd(tmp_path):
    project = create_project(tmp_path/'DesktopTool', 'DesktopTool', 'cy.tool.desktop', desktop=True)
    assert not (project/'tool.py').exists()
    assert (project/'app/desktop.py').is_file()
    assert (project/'app/Docs/StandaloneDelivery.md').is_file()
    assert (project/'app/launcher.cpp').is_file()
    assert {p.name for p in project.iterdir()} == {'app','data','runtime','Lancer.cmd','DesktopTool.sh','LISEZ-MOI.md'}
    result = subprocess.run([sys.executable, str(project/'app/tool.py'), 'invoke', 'echo',
        '--params-file', str(project/'app/params.json')], cwd=tmp_path,
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    job = json.loads(result.stdout)
    assert job['outputs'] == {'text':'Hello CyTools'}
    assert Path(job['workspace']).is_relative_to(project/'data/jobs')


def test_mcp_disconnect_cleans_shared_http_runtime(runtime,tmp_path):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    runtime.configure_inputs(tmp_path/'inputs')
    source=tmp_path/'external.bin';source.write_bytes(b'original')
    credential=runtime.create_client('MCP bridge')
    server=make_server(runtime);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    async def scenario():
        parameters=StdioServerParameters(command=sys.executable,args=['-m','cytool_test','--connect',f'http://127.0.0.1:{server.server_port}/v1','mcp'],env={**os.environ,'CYTOOLS_TOKEN':credential['token']})
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                reply=await session.call_tool('cy_import_file',{'source':str(source)})
                assert not reply.isError,reply
                imported=Path(reply.structuredContent['result']['path']);assert imported.exists()
        for _ in range(100):
            if not imported.exists():break
            await asyncio.sleep(.03)
        assert not imported.exists()
        assert runtime.status()['acceptingJobs'] and source.exists()
    try:asyncio.run(scenario())
    finally:server.shutdown();server.server_close();thread.join()
