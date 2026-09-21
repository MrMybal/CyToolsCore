import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from cytools_core.scaffold import create_project

@pytest.fixture
def ui(tmp_path,monkeypatch):
    root=create_project(tmp_path/'Desktop','Desktop','cy.test.desktop',desktop=True)
    app=root/'app'; monkeypatch.syspath_prepend(str(app))
    spec=importlib.util.spec_from_file_location('test_ui_common',app/'ui_common.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def test_english_default_and_persistent_french(ui):
    assert ui.preferences.values['language']=='en'
    assert ui.tr('Applications autonomes / catalogue MCP local')=='Standalone applications / local MCP catalog'
    assert ui.tr('Annuler')=='Cancel'
    english_id=ui.label('Annuler##job')
    ui.preferences.values['language']='fr'; ui.preferences.save()
    assert ui.Preferences().values['language']=='fr'
    assert ui.tr('Save configuration')=='Sauvegarder la configuration'
    assert english_id.split('###')[1]==ui.label('Annuler##job').split('###')[1]

def test_invalid_preferences_fall_back(ui):
    ui.PREFERENCES.parent.mkdir(parents=True,exist_ok=True)
    ui.PREFERENCES.write_text('{"language":"xx","theme":"unknown","font_scale":"bad"}')
    prefs=ui.Preferences()
    assert prefs.values['language']=='en' and prefs.values['font_scale']==1

def test_missing_license_is_not_invented(ui):
    records=ui.license_records()
    assert records[0]['license']=='Not declared'

def test_recipe_roundtrip_secret_removal_and_cross_tool_rejection(ui,tmp_path):
    import generation_config as configs
    manifest=json.loads((ui.APP/'CyTool.json').read_text())
    value=configs.recipe(manifest,'echo',{'text':'Do not translate: bonjour'},ui_state={'token':'secret','nested':{'password':'secret','seed':42},'widgets':{'Token (masked)':'secret','Prompt':'bonjour'}})
    path=configs.save(tmp_path/'recipe.json',value)
    loaded=configs.load(path,manifest)
    assert loaded['validParameters'] and loaded['parameters']['text']=='Do not translate: bonjour'
    assert 'secret' not in path.read_text()
    assert loaded['uiState']['nested']['seed']==42
    with pytest.raises(ValueError): configs.load(path,{**manifest,'id':'other'})

def test_replay_uses_native_runtime(ui,tmp_path):
    import generation_config as configs
    from cytools_core import Runtime,load_manifest
    manifest=load_manifest(ui.APP/'CyTool.json')
    path=configs.save(tmp_path/'recipe.json',configs.recipe(manifest,'echo',{'text':'Replay'}))
    runtime=Runtime(manifest,tmp_path/'jobs2'); runtime.register('echo',lambda c,p:p)
    with runtime:
        actor=runtime.authenticate(runtime.create_client()['token']); session=runtime.create_session(actor)['sessionId']
        job=configs.submit_config(runtime,actor,session,path)
        assert runtime.wait(actor,job['jobId'])['outputs']['text']=='Replay'

def test_autosave_preserves_submitted_parameters(ui):
    manifest={'id':'cy.test.desktop','version':'1','operations':[{'id':'generate','inputSchema':{'type':'object','properties':{'seed':{'type':'integer'}},'required':['seed']}}]}
    runtime=SimpleNamespace(descriptor=manifest,submit=lambda *a,**kw:{'jobId':'job-42','parameters':a[3],'backendId':'resolved-backend','modelId':'resolved-model'})
    values={'seed':7}
    def draw(): return runtime,values
    ui.bind_runtime(draw); ui.preferences.values['autosave_generation']=True
    runtime.submit(None,'session','generate',{'seed':42})
    path=ui.ROOT/'data/configurations/autosave/job-42.json'
    value=json.loads(path.read_text())
    assert value['parameters']['seed']==42 and value['uiState']['form']['seed']==7
    assert value['backendId']=='resolved-backend' and value['modelId']=='resolved-model'

def test_display_does_not_translate_user_generated_text(ui):
    ui._raw=SimpleNamespace(text_wrapped=lambda value:value)
    assert ui.imgui.text_wrapped('Annuler')=='Annuler'

def test_explicit_configuration_loader_does_not_submit(ui,tmp_path):
    import generation_config as configs
    manifest=json.loads((ui.APP/'CyTool.json').read_text())
    form={'text':'current'}; calls=[]
    runtime=SimpleNamespace(descriptor=manifest)
    ui.configure_generation(runtime,lambda:{'operationId':'echo','parameters':dict(form)},lambda value:form.update(value['parameters']))
    path=configs.save(tmp_path/'config.json',ui.current_recipe())
    form['text']='changed'; ui.load_current(path)
    assert form['text']=='current'
