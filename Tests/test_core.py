import copy
import json
import threading
import time
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from cytools_core import CyToolError, Runtime, validate_manifest, validate_parameters
from cytools_core.schema import schema,validate_document
from cytools_core.resources import ResourceLedger,platform_status
from cytools_core.transports.api import LocalClient
from cytool_test import create_runtime
from conftest import SYSTEM,CAPACITY


def wait_state(runtime,actor,job_id,states):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        job=runtime.get_job(actor,job_id)
        if job['state'] in states: return job
        time.sleep(.005)
    pytest.fail(f'Job did not reach {states}: {job}')


@pytest.mark.parametrize('name',['tool','parameter','worker','job','event','resources','request','response'])
def test_schemas_are_valid(name): Draft202012Validator.check_schema(schema(name))


def test_manifest_round_trip(runtime):
    value=copy.deepcopy(runtime.descriptor)
    value['futureMetadata']={'hello':1}
    assert validate_manifest(json.loads(json.dumps(value)))==value
    value['schemaVersion']=2
    with pytest.raises(CyToolError,match='major'): validate_manifest(value)


def test_invalid_descriptors(runtime):
    value=copy.deepcopy(runtime.descriptor)
    value['operations'].append(value['operations'][0])
    with pytest.raises(CyToolError,match='Duplicate'): validate_manifest(value)
    value=copy.deepcopy(runtime.descriptor)
    value['operations'][0]['inputSchema']={'$ref':'https://example.invalid/schema'}
    with pytest.raises(CyToolError,match='local'): validate_manifest(value)


@pytest.mark.parametrize('parameters',[{}, {'text':3},{'text':'ok','extra':1},{'text':float('nan')}])
def test_invalid_parameters(runtime,actor,session,parameters):
    with pytest.raises(CyToolError): runtime.submit(actor,session,'echo',parameters)
    assert runtime.list_jobs(actor)==[]


def test_conditional_nested_defaults():
    spec={'type':'object','properties':{'backend':{'enum':['a','b'],'default':'a'},'options':{'type':'object','default':{},'properties':{'seed':{'type':'integer','default':42}}}},
          'if':{'properties':{'backend':{'const':'a'}}},'then':{'properties':{'precision':{'enum':['fp16'],'default':'fp16'}}}}
    assert validate_parameters({},spec)=={'backend':'a','options':{'seed':42},'precision':'fp16'}
    with pytest.raises(CyToolError): validate_parameters({'precision':'fp8'},spec)


def test_three_clients_isolation_progress_cancel(runtime):
    actors=[runtime.authenticate(runtime.create_client(str(i))['token']) for i in range(3)]
    sessions=[runtime.create_session(a)['sessionId'] for a in actors]
    jobs=[runtime.submit(a,s,'progress_test',{'seconds':.3,'steps':5}) for a,s in zip(actors,sessions)]
    for a,j in zip(actors,jobs): wait_state(runtime,a,j['jobId'],{'Running'})
    runtime.cancel(actors[1],jobs[1]['jobId'])
    results=[runtime.wait(a,j['jobId']) for a,j in zip(actors,jobs)]
    assert [r['state'] for r in results]==['Completed','Cancelled','Completed']
    assert len({r['workspace'] for r in results})==3
    for i,a in enumerate(actors):
        assert len(runtime.list_jobs(a))==1
        assert all(e.get('clientId',a.client_id)==a.client_id for e in runtime.events(a)['events'])
        with pytest.raises(CyToolError): runtime.get_job(a,jobs[(i+1)%3]['jobId'])
        with pytest.raises(CyToolError): runtime.cancel(a,jobs[(i+1)%3]['jobId'])
        with pytest.raises(CyToolError): runtime.submit(a,sessions[(i+1)%3],'echo',{'text':'no'})
    assert runtime.ledger.snapshot()['reservations']=={}


def test_vram_queue_and_release(runtime,actor,session):
    a=runtime.submit(actor,session,'simulate_vram',{'bytes':10*1024**3,'seconds':.2})
    wait_state(runtime,actor,a['jobId'],{'Running'})
    b=runtime.submit(actor,session,'simulate_vram',{'bytes':10*1024**3,'seconds':.02})
    wait_state(runtime,actor,b['jobId'],{'WaitingForResources'})
    assert runtime.ledger.snapshot()['available']['vramBytes']['simulation']==6*1024**3
    assert runtime.wait(actor,a['jobId'])['state']=='Completed'
    assert runtime.wait(actor,b['jobId'])['state']=='Completed'
    assert runtime.ledger.snapshot()['available']['vramBytes']['simulation']==16*1024**3


def test_priority_queue(tmp_path,runtime):
    descriptor=copy.deepcopy(runtime.descriptor)
    descriptor['concurrency']={'policy':'Sequential','maxWorkers':1}
    started=threading.Event()
    release=threading.Event()
    order=[]
    with _priority_runtime(descriptor,tmp_path/'priority',started,release,order) as r:
        a=r.authenticate(r.create_client()['token'])
        s=r.create_session(a)['sessionId']
        first=r.submit(a,s,'echo',{'text':'block'})
        assert started.wait(2)
        low=r.submit(a,s,'echo',{'text':'low'},priority='Low')
        high=r.submit(a,s,'echo',{'text':'high'},priority='Critical')
        release.set()
        for j in (first,low,high): r.wait(a,j['jobId'])
        assert order==['block','high','low']


def _priority_runtime(descriptor,path,started,release,order):
    r=Runtime(descriptor,path,capacity=CAPACITY,system=SYSTEM)
    def handler(ctx,p):
        order.append(p['text'])
        if p['text']=='block':
            started.set()
            assert release.wait(3)
        return p
    for o in descriptor['operations']: r.register(o['id'],handler)
    return r


def test_queue_and_execution_timeout(runtime,actor,session):
    a=runtime.submit(actor,session,'simulate_vram',{'bytes':16*1024**3,'seconds':.25})
    wait_state(runtime,actor,a['jobId'],{'Running'})
    b=runtime.submit(actor,session,'simulate_vram',{'bytes':16*1024**3},queue_timeout=.02)
    assert runtime.wait(actor,b['jobId'])['error']['code']=='Timeout'
    runtime.wait(actor,a['jobId'])
    c=runtime.submit(actor,session,'sleep',{'seconds':1},execution_timeout=.03)
    assert runtime.wait(actor,c['jobId'])['error']['code']=='Timeout'


def test_cancel_queued_job(runtime,actor,session):
    a=runtime.submit(actor,session,'simulate_vram',{'bytes':16*1024**3,'seconds':.15})
    wait_state(runtime,actor,a['jobId'],{'Running'})
    b=runtime.submit(actor,session,'simulate_vram',{'bytes':16*1024**3})
    runtime.cancel(actor,b['jobId'])
    assert runtime.wait(actor,b['jobId'])['state']=='Cancelled'
    runtime.wait(actor,a['jobId'])


def test_insufficient_resources():
    ledger=ResourceLedger({'ramBytes':20,'vramBytes':{'0':24},'diskBytes':100,'cpuThreads':1})
    assert ledger.reserve('a',{'ramBytes':12,'vramBytes':{'0':18}})
    assert not ledger.reserve('b',{'ramBytes':12,'vramBytes':{'0':15}})
    ledger.release('a')
    assert ledger.reserve('b',{'ramBytes':12,'vramBytes':{'0':15}})
    assert ledger.shortage({'ramBytes':21},ledger.capacity)=='InsufficientRAM'
    assert ledger.shortage({'vramBytes':{'0':25}},ledger.capacity)=='InsufficientVRAM'


def test_no_overcommit_under_threads():
    ledger=ResourceLedger({'ramBytes':10,'vramBytes':{}})
    barrier=threading.Barrier(20)
    successes=[]
    def reserve(i):
        barrier.wait()
        if ledger.reserve(str(i),{'ramBytes':6}): successes.append(i)
    threads=[threading.Thread(target=reserve,args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(successes)==1


def test_outputs_and_workspaces(runtime,actor,session):
    a=runtime.submit(actor,session,'generate_file',{'text':'one'})
    b=runtime.submit(actor,session,'generate_file',{'text':'two'})
    ra,rb=[runtime.wait(actor,j['jobId']) for j in (a,b)]
    assert ra['outputs']['file']!=rb['outputs']['file']
    assert Path(ra['outputs']['file']).read_text()=='one'
    assert Path(rb['outputs']['file']).read_text()=='two'
    validate_document(ra,'job')
    for event in runtime.events(actor)['events']: validate_document(event,'event')


def test_access_and_sharing(runtime,actor,session):
    bob=runtime.authenticate(runtime.create_client('Bob')['token'])
    job=runtime.submit(actor,session,'echo',{'text':'shared'})
    runtime.wait(actor,job['jobId'])
    runtime.share_job(actor,job['jobId'],'Shared',[bob.client_id])
    assert runtime.get_job(bob,job['jobId'])['outputs']=={'text':'shared'}
    with pytest.raises(CyToolError): runtime.share_job(bob,job['jobId'],'Global')
    runtime.share_job(actor,job['jobId'],'Owner')
    assert not runtime.list_jobs(bob)
    with pytest.raises(CyToolError): runtime.authenticate(actor.client_id)


def test_sessions_and_permissions(runtime,actor,session):
    runtime.close_session(actor,session)
    with pytest.raises(CyToolError): runtime.submit(actor,session,'echo',{'text':'x'})
    with pytest.raises(CyToolError): runtime.release_resources(actor,'All')


def test_persistence_and_ownership_lock(tmp_path):
    with create_runtime(tmp_path,system=SYSTEM,capacity=CAPACITY) as r:
        credential=r.create_client()
        actor=r.authenticate(credential['token'])
        s=r.create_session(actor,temporary=False)['sessionId']
        job=r.submit(actor,s,'echo',{'text':'persisted'})
        r.wait(actor,job['jobId'])
        with pytest.raises(CyToolError,match='directory'): create_runtime(tmp_path)
    with create_runtime(tmp_path,system=SYSTEM,capacity=CAPACITY) as r:
        actor=r.authenticate(credential['token'])
        assert r.get_job(actor,job['jobId'])['outputs']=={'text':'persisted'}
        assert r.ledger.snapshot()['reservations']=={}


def test_unknown_platform():
    assert platform_status([],SYSTEM)=='Unknown'
    assert platform_status([{'os':'Windows','architecture':'x64','status':'Unknown'}],SYSTEM)=='Unknown'
    assert platform_status([{'os':'Linux','architecture':'x64','status':'Supported'}],SYSTEM)=='Unsupported'


def test_can_run_model_and_platform(runtime):
    assert runtime.can_run('simulate_vram',{'bytes':17*1024**3})['status']=='InsufficientVRAM'
    assert runtime.can_run('echo',{'text':'x'},'imaginary')['status']=='UnsupportedBackend'
    assert runtime.can_run('echo',{'text':'x'},model_id='missing')['status']=='MissingModel'
    runtime.descriptor['platforms'][0]['status']='Unknown'
    assert runtime.can_run('echo',{'text':'x'})['status']=='UnsupportedPlatform'


def test_error_and_observation(runtime,actor,session):
    j=runtime.submit(actor,session,'fail',{})
    assert runtime.wait(actor,j['jobId'])['error']['code']=='SimulatedFailure'
    j=runtime.submit(actor,session,'allocate_ram',{'bytes':4096,'seconds':0})
    assert runtime.wait(actor,j['jobId'])['outputs']['allocatedBytes']==4096
    assert runtime.store.all('observations')[j['jobId']]['usage']['ramBytes']==4096


def test_dispatch_contract(runtime,actor):
    client=LocalClient(runtime,actor)
    response=client.dispatch({'protocolVersion':'1.0','id':2,'method':'DescribeTool','params':{}})
    validate_document(response,'response')
    assert response['result']['id']=='cy.tool.test'
    response=client.dispatch({'protocolVersion':'99.0','id':2,'method':'DescribeTool','params':{}})
    assert 'error' in response
