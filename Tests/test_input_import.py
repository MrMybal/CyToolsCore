import json
from pathlib import Path
import pytest
from cytools_core import Runtime,load_manifest

def make_runtime(tmp_path, keep=True):
    manifest=load_manifest(Path(__file__).parents[1]/'cytool_test/CyTool.json')
    manifest['operations']=[{'id':'import_file','name':'Import file','description':'Snapshot fixture',
      'inputSchema':{'type':'object','properties':{'source':{'type':'string'}},'required':['source'],'additionalProperties':False},
      'outputSchema':{'type':'object','properties':{'file':{'type':'string'}},'required':['file']},'canCancel':True}]
    runtime=Runtime(manifest,tmp_path/'jobs')
    runtime.register('import_file',lambda context,p:{'file':str(context.import_input(p['source'],base_dir=tmp_path/'inputs',suffixes=['.png'],max_bytes=32,keep=keep))})
    return runtime

def submit(runtime,actor,session,source):
    job=runtime.submit(actor,session,'import_file',{'source':str(source)})
    return runtime.wait(actor,job['jobId'],timeout=5)

def test_external_input_snapshot_and_client_isolation(tmp_path):
    source=tmp_path/'outside space'/ 'same.png';source.parent.mkdir();source.write_bytes(b'original')
    with make_runtime(tmp_path) as r:
        a=r.authenticate(r.create_client('A')['token']);b=r.authenticate(r.create_client('B')['token'])
        sa=r.create_session(a)['sessionId'];sb=r.create_session(b)['sessionId']
        first=submit(r,a,sa,source);second=submit(r,b,sb,source)
        assert first['state']==second['state']=='Completed'
        copy=Path(first['outputs']['file']);assert copy!=Path(second['outputs']['file'])
        source.write_bytes(b'changed');assert copy.read_bytes()==b'original'
        assert copy.is_relative_to(Path(first['workspace'])/'inputs')
        receipt=json.loads((Path(first['workspace'])/'inputs/imports.json').read_text())
        assert receipt[0]['sizeBytes']==8 and len(receipt[0]['sha256'])==64
        from cytools_core import CyToolError
        with pytest.raises(CyToolError,match='unavailable'): submit(r,b,sb,copy)
        r.share_job(a,first['jobId'],'Shared',[b.client_id])
        assert submit(r,b,sb,copy)['state']=='Completed'

@pytest.mark.parametrize('kind,code',[('missing','MissingInput'),('large','InputTooLarge'),('extension','InvalidInput'),('traversal','AccessDenied')])
def test_invalid_inputs_do_not_leave_partial_copies(tmp_path,kind,code):
    source=tmp_path/('bad.txt' if kind=='extension' else 'bad.png')
    if kind!='missing':source.write_bytes(b'x'*40)
    if kind=='traversal':source='../bad.png'
    with make_runtime(tmp_path) as r:
        a=r.authenticate(r.create_client()['token']);s=r.create_session(a)['sessionId']
        job=submit(r,a,s,source);assert job['state']=='Failed' and job['error']['code']==code,job
        assert not list(Path(job['workspace']).rglob('*.partial'))

@pytest.mark.parametrize('outcome',['Completed','Failed','Cancelled'])
def test_temporary_inputs_removed_after_handler_stops(tmp_path,outcome):
    from cytools_core import CyToolError
    source=tmp_path/'input.png';source.write_bytes(b'original')
    r=make_runtime(tmp_path,keep=False);original=r._handlers['import_file'];copies=[]
    def handler(context,p):
        result=original(context,p);copies.append(Path(result['file']))
        assert copies[-1].exists()
        if outcome=='Failed':raise CyToolError('FixtureFailure','fixture failure')
        if outcome=='Cancelled':context.cancellation.cancel();context.cancellation.check()
        return result
    r._handlers.pop('import_file')
    r.register('import_file',handler)
    with r:
        a=r.authenticate(r.create_client()['token']);s=r.create_session(a)['sessionId']
        job=submit(r,a,s,source);assert job['state']==outcome
        assert copies and not copies[0].exists()
        assert source.read_bytes()==b'original'
        records=json.loads((Path(job['workspace'])/'inputs/imports.json').read_text())
        assert records[0]['removed'] and records[0]['temporary']
