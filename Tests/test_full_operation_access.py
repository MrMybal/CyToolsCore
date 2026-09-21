import json
from types import SimpleNamespace
from test_standalone_extensions import template
from cytools_core import load_manifest
from pathlib import Path

def test_exact_submission_preserves_hooks_without_form_overrides(monkeypatch,tmp_path):
    import sys
    monkeypatch.setitem(sys.modules,'model_options',SimpleNamespace(ROOT=tmp_path,read=lambda p,d:d))
    module=template('model_options_ui');calls=[]
    runtime=SimpleNamespace(submit=lambda *args,**kw:calls.append((args,kw)))
    panel=module.Panel(runtime)
    panel.apply=lambda op,p,kw:({'device':'cpu'},kw)
    original=runtime.submit;hooks=[]
    def preview(*args,**kw):hooks.append('preview');return original(*args,**kw)
    runtime.submit=preview
    module.submit_exact(runtime,None,'session','generate',{'device':'cuda'})
    assert calls[-1][0][-1]=={'device':'cuda'} and hooks==['preview']
    runtime.submit(None,'session','generate',{'device':'cuda'})
    assert calls[-1][0][-1]=={'device':'cpu'}

def test_gpu_environment_preserves_parent_environment(monkeypatch):
    from cytools_core.resources import _gpu_process_environment
    monkeypatch.setenv('ProgramFiles','explicit-test-value')
    monkeypatch.setenv('CYTOOLS_TEST_ENV','preserve')
    value=_gpu_process_environment()
    assert next(v for k,v in value.items() if k.casefold()=='programfiles')=='explicit-test-value'
    assert value['CYTOOLS_TEST_ENV']=='preserve'

def test_windows_gpu_environment_recovers_mcp_omission(monkeypatch):
    import os,pytest
    if os.name!='nt':pytest.skip('Windows registry integration')
    from cytools_core.resources import _gpu_process_environment
    monkeypatch.delenv('ProgramFiles',raising=False)
    value=_gpu_process_environment()
    assert os.path.isdir(value['ProgramFiles'])
    assert 'ProgramFiles' not in os.environ

def test_advanced_payload_preserves_nested_values_and_optional_omission(tmp_path):
    module=template('advanced_ui')
    # Construct the pure editor state without creating a UI or authenticated runtime.
    panel=object.__new__(module.Panel);panel.index=0;panel.drafts={}
    panel.runtime=SimpleNamespace(descriptor={'operations':[{'id':'test','inputSchema':{'type':'object','additionalProperties':False,
       'properties':{'weights':{'type':'array','items':{'type':'number'}},'options':{'type':'object'},'optional':{'type':'string'}}}}]})
    _,state=panel.state();state['text']='{"weights":[0,0.5],"options":{"enabled":false,"seed":0}}'
    assert panel.payload()=={'weights':[0,0.5],'options':{'enabled':False,'seed':0}}
    panel.restore({'operationId':'test','parameters':{'weights':[]},'backendId':'cpu','modelId':'local'})
    assert panel.payload()=={'weights':[]} and state['backend']=='cpu'

def test_model_library_operations_use_real_runtime(tmp_path):
    module=template('model_options');module.ROOT=tmp_path;module.APP=tmp_path/'app';module.APP.mkdir()
    (module.APP/'model-capabilities.json').write_text(json.dumps({'operations':{},'formats':{'test':{'required':['config.json']}}}))
    model=tmp_path/'weights';model.mkdir();(model/'config.json').write_text('{}')
    descriptor=load_manifest(Path(__file__).parents[1]/'cytool_test/CyTool.json')
    descriptor['operations']=[]
    with module.Runtime(descriptor,tmp_path/'jobs') as runtime:
        actor=runtime.authenticate(runtime.create_client('test')['token']);session=runtime.create_session(actor)['sessionId']
        job=runtime.submit(actor,session,'model_library_register',{'name':'Local test','path':str(model),'format':'test'})
        job=runtime.wait(actor,job['jobId'],timeout=5)
        assert job['state']=='Completed',job.get('error')
        identifier=job['outputs']['model']['id']
        listing=runtime.submit(actor,session,'model_library_list',{})
        listing=runtime.wait(actor,listing['jobId'],timeout=5)
        assert listing['outputs']['library']['models'][0]['id']==identifier
        assert list(model.iterdir())==[model/'config.json']
