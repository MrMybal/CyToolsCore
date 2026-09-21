import importlib.machinery,importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from cytools_core import CancellationToken
from cytools_core.workers import ProcessWorker

def template(name):
    path=Path(__file__).parents[1]/'cytools_core/templates'/(name+'.py.txt')
    spec=importlib.util.spec_from_loader('test_'+name,importlib.machinery.SourceFileLoader('test_'+name,str(path)))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_log_redacts_disk_and_readback(tmp_path):
    module=template('standalone_log');journal=module.Journal(tmp_path)
    journal.write('access_token=hf_123456789abcdef password=secret123 Authorization: Bearer abcdef')
    journal.handler.flush();text=journal.read()
    assert 'secret123' not in text and 'abcdef' not in text
    assert '[REDACTED]' in text
    journal.handler.close()

def test_fragmented_stderr_redacts_whole_line(tmp_path):
    module=template('standalone_log');journal=module.Journal(tmp_path)
    stream=module.Stream(None,journal,'ERROR')
    stream.write('hf_abcdefgh');stream.write('ijklmnop\n')
    assert 'abcdefghijklmnop' not in journal.read()
    journal.handler.close()

def test_full_log_copy_includes_content_before_display_tail(tmp_path):
    module=template('standalone_log');journal=module.Journal(tmp_path)
    path=tmp_path/'large.log'
    path.write_bytes(('start-of-log\n'+'x'*(module.LIMIT+100)+'\nend-of-log').encode('utf-8'))
    assert 'start-of-log' not in journal.read(path)
    assert journal.read(path,full=True).startswith('start-of-log\n')
    assert journal.read(path,full=True).endswith('end-of-log')
    journal.handler.close()

def test_worker_stderr_is_recorded_without_secrets(tmp_path):
    records=[]
    def path(relative):
        result=tmp_path/relative;result.parent.mkdir(parents=True,exist_ok=True);return result
    context=SimpleNamespace(workspace=tmp_path,cancellation=CancellationToken(),path=path,log=lambda message,**kw:records.append(message))
    worker=ProcessWorker([sys.executable,'-c',"import sys; print('password=hidden',file=sys.stderr); print('{}')"])
    assert worker.run(context,{})=={}
    assert 'hidden' not in (tmp_path/'logs/worker-stderr.log').read_text()
    assert records and worker.process is None

def test_model_catalog_references_and_rejects_incompatible(tmp_path,monkeypatch):
    module=template('model_options');module.ROOT=tmp_path;module.APP=tmp_path/'app';module.APP.mkdir()
    spec={'operations':{'generate':{'models':['fixture'],'loras':[]}},'formats':{'fixture':{'required':['config.json'],'weights':['*.safetensors']}}}
    (module.APP/'model-capabilities.json').write_text(json.dumps(spec))
    weights=tmp_path/'weights';weights.mkdir();(weights/'config.json').write_text('{}');(weights/'model.safetensors').write_bytes(b'fixture')
    item=module.add_asset('Derivative',weights,'fixture')
    assert len(module.catalog()['models'])==1
    assert module.resolve({'model_profile':item['id']},'generate')['model']['path']==str(weights.resolve())
    with pytest.raises(Exception):module.resolve({'model_profile':item['id']},'other')
    with pytest.raises(Exception):module.resolve({'loras':[{'id':item['id'],'strength':1}]},'generate')
    assert list((tmp_path/'data').rglob('*.safetensors'))==[]
    assert 'model_profile' in module.extend_manifest({'operations':[{'id':'generate','inputSchema':{'properties':{}}}]})['operations'][0]['inputSchema']['properties']

def test_device_selection_respects_cuda_and_saved_parameters(tmp_path,monkeypatch):
    models=template('model_options');models.ROOT=tmp_path;monkeypatch.setitem(sys.modules,'model_options',models)
    ui=template('model_options_ui')
    runtime=SimpleNamespace(submit=lambda *a,**kw:kw,system={'gpus':[{'computeBackends':['Vulkan']}]},descriptor={'operations':[{'id':'generate','inputSchema':{'properties':{'device':{'enum':['cpu','cuda']}}}}]})
    panel=ui.Panel(runtime);panel.values={'generate':{'device':'auto'}}
    parameters,_=panel.apply('generate',{},{});assert parameters['device']=='cpu'
    runtime.system['gpus']=[{'computeBackends':['CUDA']}]
    parameters,_=panel.apply('generate',{},{});assert parameters['device']=='cuda'
