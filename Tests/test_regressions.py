import copy
import json
import sys
import threading
import time
from pathlib import Path
import pytest
from cytools_core import Runtime, CyToolError, JobContext, CancellationToken
from cytools_core.schema import validate_document,validate_manifest
from cytools_core.transports.api import LocalClient
from cytools_core.transports.mcp import _envelope_schema
from cytools_core.downloads import DownloadManager
from jsonschema import Draft202012Validator
from conftest import SYSTEM,CAPACITY


def test_output_validation_and_systemexit(tmp_path,runtime):
    descriptor=copy.deepcopy(runtime.descriptor)
    descriptor['operations']=descriptor['operations'][:1]
    with _bad_runtime(descriptor,tmp_path/'bad-output') as r:
        actor=r.authenticate(r.create_client()['token'])
        session=r.create_session(actor)['sessionId']
        for text,code in [('bad','InvalidOutput'),('exit','InternalError')]:
            job=r.submit(actor,session,'echo',{'text':text})
            result=r.wait(actor,job['jobId'])
            assert result['state']=='Failed'
            assert result['error']['code']==code


def _bad_runtime(descriptor,path):
    r=Runtime(descriptor,path,capacity=CAPACITY,system=SYSTEM)
    def handler(ctx,p):
        if p['text']=='exit': raise SystemExit(5)
        return {'wrong':1}
    r.register('echo',handler)
    return r


def test_nonfinite_resources_rejected():
    for number in (float('inf'),float('nan'),-1):
        with pytest.raises(CyToolError): validate_document({'ramBytes':number},'resources')


def test_mcp_nested_references():
    parameters={'type':'object','$defs':{'text':{'type':'string'}},'properties':{'text':{'$ref':'#/$defs/text'}},'required':['text']}
    envelope={'type':'object','properties':{'parameters':_envelope_schema(parameters)},'required':['parameters']}
    Draft202012Validator(envelope).validate({'parameters':{'text':'ok'}})
    assert not Draft202012Validator(envelope).is_valid({'parameters':{'text':9}})


def test_permission_and_request_fields(runtime,actor,session):
    runtime.descriptor['operations'][0]['permissions']=['externalFiles']
    with pytest.raises(CyToolError,match='permissions'): runtime.submit(actor,session,'echo',{'text':'x'})
    authorized=runtime.authenticate(runtime.create_client('authorized',['externalFiles'])['token'])
    s=runtime.create_session(authorized)['sessionId']
    j=runtime.submit(authorized,s,'echo',{'text':'x'})
    assert runtime.wait(authorized,j['jobId'])['state']=='Completed'
    response=LocalClient(runtime,actor).dispatch({'protocolVersion':'1.0','id':1,'method':'GetEvents','params':{'after':-1}})
    assert 'error' in response


def test_path_traversal(runtime,actor,session):
    job=runtime.submit(actor,session,'echo',{'text':'x'})
    runtime.wait(actor,job['jobId'])
    context=JobContext(runtime,job['jobId'],CancellationToken())
    for name in ('../escape.txt', str(runtime.root/'escape.txt')):
        with pytest.raises(CyToolError): context.path(name)


def test_model_and_cpu_requirements(runtime):
    operation=runtime.descriptor['operations'][0]
    operation['supportedBackends']=['engine']
    model={'id':'model','name':'Model','version':'1','installed':False,'location':'Local'}
    runtime.descriptor['backends']=[{'id':'engine','name':'Engine','models':[model]}]
    assert runtime.can_run('echo',{'text':'x'},'engine','model')['status']=='MissingModel'
    model['installed']=True
    assert runtime.can_run('echo',{'text':'x'},'engine','model')['canRun']
    model['computeBackends']=['unverifiedGPU']
    assert runtime.can_run('echo',{'text':'x'},'engine','model')['status']=='UnsupportedGPU'
    operation['resourceRequirements']={'cpu':{'instructions':['unverifiedInstruction']}}
    assert runtime.can_run('echo',{'text':'x'})['status']=='UnsupportedCPU'


def test_dependency_missing(runtime):
    runtime.descriptor['runtimeRequirements']=[{'id':'missing','required':True,'executable':'cytools-impossible-runtime-123'}]
    assert runtime.can_run('echo',{'text':'x'})['status']=='MissingDependency'


def test_interrupted_history(tmp_path,runtime):
    descriptor=copy.deepcopy(runtime.descriptor)
    root=tmp_path/'restart'
    r=Runtime(descriptor,root,capacity=CAPACITY,system=SYSTEM)
    credential=r.create_client()
    r.store.put('jobs','interrupted',{'jobId':'interrupted','clientId':credential['clientId'],'state':'Running'})
    r.close()
    r=Runtime(descriptor,root,capacity=CAPACITY,system=SYSTEM)
    try:
        actor=r.authenticate(credential['token'])
        assert r.get_job(actor,'interrupted')['error']['code']=='Interrupted'
    finally: r.close()


def test_ledger_not_released_before_uncooperative_handler_stops(tmp_path,runtime):
    descriptor=copy.deepcopy(runtime.descriptor)
    descriptor['operations']=descriptor['operations'][:1]
    descriptor['operations'][0]['resourceRequirements']={'ramBytes':10}
    started,release=threading.Event(),threading.Event()
    r=Runtime(descriptor,tmp_path/'uncooperative',capacity=CAPACITY,system=SYSTEM)
    def handler(ctx,p):
        started.set()
        release.wait(2)
        return p
    r.register('echo',handler)
    r.start()
    try:
        actor=r.authenticate(r.create_client()['token'])
        session=r.create_session(actor)['sessionId']
        job=r.submit(actor,session,'echo',{'text':'x'})
        assert started.wait(1)
        r.cancel(actor,job['jobId'])
        assert job['jobId'] in r.ledger.snapshot()['reservations']
        assert r.get_job(actor,job['jobId'])['state']=='Cancelling'
        release.set()
        assert r.wait(actor,job['jobId'])['state']=='Cancelled'
        assert r.ledger.snapshot()['reservations']=={}
    finally:
        release.set()
        r.close()
