import threading
import time
from pathlib import Path
import pytest
from cytools_core import Runtime, load_manifest, CyToolError


def runtime(tmp_path, handler=None):
    m=load_manifest(Path(__file__).parents[1]/'cytool_test/CyTool.json')
    m['operations']=[{'id':'copy','name':'Copy','description':'Fixture','inputSchema':{'type':'object','properties':{'source':{'type':'string'}},'required':['source']},'outputSchema':{'type':'object'},'canCancel':True}]
    r=Runtime(m,tmp_path/'jobs')
    r.configure_inputs(tmp_path/'inputs',fields={'copy':['source']})
    def copy(c,p):
        source=Path(p['source']); assert source.is_relative_to(tmp_path/'inputs')
        out=c.path('outputs/result.bin');out.write_bytes(source.read_bytes())
        c.path('intermediate/big.bin').write_bytes(b'intermediate')
        return {'file':str(out)}
    r.register('copy',handler or copy)
    return r


def actor(r): return r.authenticate(r.create_client()['token'])


def test_auto_import_export_and_finish(tmp_path):
    source=tmp_path/'external.bin';source.write_bytes(b'original')
    with runtime(tmp_path) as r:
        a=actor(r)
        with r.task(a) as session:
            job=r.wait(a,r.submit(a,session,'copy',{'source':str(source)})['jobId'])
            assert job['state']=='Completed',job
            result=Path(job['outputs']['file']);assert result.exists()
            exported=r.export_job(a,job['jobId'],str(tmp_path/'project'))
            kept=Path(exported['outputs']['file']);assert kept.read_bytes()==b'original'
        assert not result.exists() and not Path(job['workspace']).exists()
        assert not list((tmp_path/'inputs').rglob('*.bin'))
        assert source.read_bytes()==b'original' and kept.read_bytes()==b'original'
        assert r.get_job(a,job['jobId'])['artifactsDeleted']


def test_running_worker_never_purged_early(tmp_path):
    started=threading.Event();stop=threading.Event();files=[]
    def handler(c,p):
        file=c.path('work.bin');file.write_bytes(b'active');files.append(file);started.set()
        stop.wait(5)
        assert file.exists()
        return {}
    source=tmp_path/'original.bin';source.write_bytes(b'input')
    with runtime(tmp_path,handler) as r:
        a=actor(r);s=r.create_session(a)['sessionId'];j=r.submit(a,s,'copy',{'source':str(source)})
        assert started.wait(3)
        state=r.finish_task(a,s,cancel_running=True)
        assert state['cleanupPending'] and files[0].exists()
        stop.set();r.wait(a,j['jobId'])
        assert not files[0].exists()


def test_import_companions_isolation_and_persistent_ui(tmp_path):
    source=tmp_path/'asset.obj';source.write_text('mtllib asset.mtl')
    (tmp_path/'asset.mtl').write_text('newmtl test')
    with runtime(tmp_path) as r:
        a=actor(r);b=actor(r);s=r.create_session(a,temporary=False)['sessionId']
        imported=r.import_file(a,s,str(source),companions=['asset.mtl'])
        assert Path(imported['path']).with_suffix('.mtl').exists()
        with pytest.raises(CyToolError):r.finish_task(b,s)
        j=r.wait(a,r.submit(a,s,'copy',{'source':imported['path']})['jobId'])
        r.close_session(a,s)
        assert Path(j['outputs']['file']).exists()
        assert not Path(imported['path']).exists()
    assert Path(j['outputs']['file']).exists()


def test_idle_expiry_and_runtime_close(tmp_path):
    source=tmp_path/'asset.bin';source.write_bytes(b'x')
    with runtime(tmp_path) as r:
        a=actor(r);s=r.create_session(a,retention_seconds=1)['sessionId']
        imported=r.import_file(a,s,str(source));deadline=time.monotonic()+4
        while Path(imported['path']).exists() and time.monotonic()<deadline:time.sleep(.05)
        assert not Path(imported['path']).exists()
        s=r.create_session(a)['sessionId'];other=r.import_file(a,s,str(source))
    assert not Path(other['path']).exists() and source.exists()


def test_restart_recovers_task_files(tmp_path):
    source=tmp_path/'asset.bin';source.write_bytes(b'x')
    r=runtime(tmp_path);a=actor(r);s=r.create_session(a)['sessionId'];imported=r.import_file(a,s,str(source))
    # Simulate a stopped process, without graceful cleanup.
    r.store.close();r._ownership.close()
    with runtime(tmp_path) as recovered:
        deadline=time.monotonic()+3
        while Path(imported['path']).exists() and time.monotonic()<deadline:time.sleep(.02)
        assert not Path(imported['path']).exists()


def test_consumer_lease_keeps_producer_until_stopped(tmp_path):
    started=threading.Event();stop=threading.Event();source=tmp_path/'input.bin';source.write_bytes(b'data')
    r=runtime(tmp_path)
    original=r._handlers['copy']
    def handler(c,p):
        if len(r._jobs)>1:started.set();stop.wait(5)
        return original(c,p)
    r._handlers['copy']=handler
    with r:
        a=actor(r);one=r.create_session(a)['sessionId'];two=r.create_session(a)['sessionId']
        producer=r.wait(a,r.submit(a,one,'copy',{'source':str(source)})['jobId'])
        output=Path(producer['outputs']['file'])
        consumer=r.submit(a,two,'copy',{'source':str(output)})
        assert started.wait(3)
        assert r.finish_task(a,one)['cleanupPending'] and output.exists()
        stop.set();result=r.wait(a,consumer['jobId'])
        assert result['state']=='Completed' and not output.exists()
        r.finish_task(a,two)
        assert not Path(result['outputs']['file']).exists()


def test_mesh_bundle_and_ownership(tmp_path):
    source=tmp_path/'mesh.obj';source.write_text('mtllib materials/main.mtl')
    (tmp_path/'materials').mkdir();(tmp_path/'materials/main.mtl').write_text('newmtl x\nmap_Kd color.png')
    (tmp_path/'materials/color.png').write_bytes(b'fixture')
    with runtime(tmp_path) as r:
        a=actor(r);b=actor(r);one=r.create_session(a)['sessionId'];two=r.create_session(b)['sessionId']
        bundle=r.import_file(a,one,str(source))
        assert len(bundle['files'])==3
        with pytest.raises(CyToolError,match='another client'):r.import_file(b,two,bundle['path'])
        r.finish_task(a,one)
        assert not Path(bundle['path']).exists() and source.exists()


def test_no_export_into_temporary_runtime_or_foreign_job(tmp_path):
    source=tmp_path/'input.bin';source.write_bytes(b'data')
    with runtime(tmp_path) as r:
        a=actor(r);b=actor(r);s=r.create_session(a)['sessionId']
        job=r.wait(a,r.submit(a,s,'copy',{'source':str(source)})['jobId'])
        with pytest.raises(CyToolError):r.export_job(b,job['jobId'],str(tmp_path/'export'))
        with pytest.raises(CyToolError):r.export_job(a,job['jobId'],str(r.root/'retained'))
        r.finish_task(a,s)
        assert not r.finish_task(a,s)['cleanupPending']


def test_failure_cleanup_and_no_relative_escape(tmp_path):
    source=tmp_path/'source.bin';source.write_bytes(b'source')
    def fail(c,p):
        c.path('partial.bin').write_bytes(b'partial')
        raise CyToolError('FixtureFailure','failed')
    with runtime(tmp_path,fail) as r:
        a=actor(r)
        with r.task(a) as s:
            job=r.wait(a,r.submit(a,s,'copy',{'source':str(source)})['jobId'])
            assert job['state']=='Failed' and Path(job['workspace']).exists()
        assert not Path(job['workspace']).exists() and source.exists()
        with r.task(a) as s:
            job=r.wait(a,r.submit(a,s,'copy',{'source':'../source.bin'})['jobId'])
            assert job['error']['code']=='AccessDenied'
