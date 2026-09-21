"""Optional Tool UI preferences/localization. Never imported by the Core runtime.

Existing frontends may use the imgui facade to migrate visible strings without
changing protocol values, model inputs or persistent widget identities.
"""
import importlib.metadata
import json
import os
from pathlib import Path
import re
import unicodedata
import sys
import uuid
import webbrowser

APP = Path(__file__).resolve().parent
ROOT = APP.parent
from standalone_log import install as install_standalone_log
journal = install_standalone_log(ROOT)
PREFERENCES = ROOT / 'data/settings/ui-preferences.json'
DEFAULTS = {'language': 'en', 'theme': 'dark', 'font_scale': 1.0, 'autosave_generation': False}

def read(path, default):
    try: return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError): return default

class Preferences:
    def __init__(self, path=PREFERENCES):
        self.path = Path(path)
        stored = read(self.path, {})
        self.values = {**DEFAULTS, **(stored if isinstance(stored, dict) else {})}
        if self.values['language'] not in ('en', 'fr'): self.values['language'] = 'en'
        if self.values['theme'] not in ('dark', 'light', 'classic'): self.values['theme'] = 'dark'
        if not isinstance(self.values.get('autosave_generation'),bool): self.values['autosave_generation']=False
        try: self.values['font_scale'] = min(1.6, max(.8, float(self.values['font_scale'])))
        except (TypeError, ValueError): self.values['font_scale'] = 1.0
    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name+'.'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps(self.values, indent=2), encoding='utf-8')
        temp.replace(self.path)

preferences = Preferences()
catalog = read(APP/'locales/ui.json', {})
def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c)).replace('’',"'").casefold()
_normalized = {normalized(k):v for k,v in catalog.items()}
_prefixes = sorted((k for k in catalog if len(k)>=8 and k.endswith((' ',': '))),key=len,reverse=True)
_raw = None
_tab_depth = 0
_has_tabs = False
_inside_options = False
_licenses = None
_widget_values = {}
_restore_widgets = {}
_id_stack = []
_configuration_message = ''
_configuration_name = 'configuration'
_configuration_path = ''
_configuration_operation = ''
_scope_getter = None
_runtime = None
_last_recipe = None
_recipe_getter = None
_recipe_loader = None
_mesh_panel = None
_model_panel = None
_advanced_panel = None

def configure_generation(runtime,getter,loader):
    """Explicit integration for new Tools; getters return operationId/parameters."""
    global _runtime,_recipe_getter,_recipe_loader
    _runtime=runtime; _recipe_getter=getter; _recipe_loader=loader

def scope():
    import inspect
    result={}
    visited=set()
    def visit(function,depth=0):
        if depth>3 or id(function) in visited or not inspect.isfunction(function): return
        visited.add(id(function))
        values=inspect.getclosurevars(function).nonlocals
        for key,value in inspect.getclosurevars(function).globals.items():
            if key in ('build_parameters','parameters_for','parameters','chosen_variant') and callable(value): values.setdefault(key,value)
        for key,value in values.items():
            result.setdefault(key,value)
            if inspect.isfunction(value): visit(value,depth+1)
    if _scope_getter: visit(_scope_getter)
    interface=result.get('interface')
    if interface is not None:
        result.update(values=interface.values,runtime=interface.runtime,parameters=interface.parameters)
    return result

def form_state():
    state=scope()
    for key in ('form','values','params'):
        if isinstance(state.get(key),dict): return state[key]
    return {}

def variable_state():
    s=scope()
    fields=('mesh','seed','faces','source','operation','resolution','padding','iterations','maxcost',
            'brute','rotate','block','winding','text','selected','speaker','threads','length','volume',
            'noise','width','normalize','profile','history','operation_index','backend','model')
    return {key:s[key] for key in fields if key in s and isinstance(s[key],(str,int,float,bool,dict,list,type(None)))}

def set_variables(values):
    import inspect
    seen=set()
    def visit(function,depth=0):
        if not inspect.isfunction(function) or id(function) in seen or depth>3: return
        seen.add(id(function))
        for name,cell in zip(function.__code__.co_freevars,function.__closure__ or ()):
            current=cell.cell_contents
            if name in values and type(values[name])==type(current): cell.cell_contents=values[name]
            if inspect.isfunction(current): visit(current,depth+1)
    if _scope_getter: visit(_scope_getter)

def current_recipe():
    from generation_config import recipe as base_recipe
    def recipe(manifest,operation,parameters,**kwargs):
        if _model_panel is not None:
            parameters,selection=_model_panel.apply(operation,parameters,{'backend_id':kwargs.get('backend','')})
            kwargs['backend']=selection.get('backend_id','')
        return base_recipe(manifest,operation,parameters,**kwargs)
    if _runtime is None: raise ValueError('Generation configuration is unavailable for this interface')
    if _recipe_getter:
        value=_recipe_getter()
        return recipe(_runtime.descriptor,value['operationId'],value['parameters'],
                      backend=value.get('backendId',''),model=value.get('modelId',''),
                      ui_state={'widgets':_widget_values})
    s=scope(); values=form_state(); manifest=_runtime.descriptor
    identifier=manifest['id']; operation=_configuration_operation
    parameters=dict(values); backend=''; model=''
    # Existing Tools keep their parameter builders; no second model parameter contract.
    if 'build_parameters' in s:
        builder=s['build_parameters']
        if 'acestep' in identifier:
            operation=operation or 'generate_song'; parameters=builder(operation,values[operation])
        else:
            operations=s['build_parameters'].__globals__.get('OPERATIONS',[])
            operation=operation or (operations[values['operation']][0] if operations else 'text_to_video')
            parameters=builder(operation)
    elif 'parameters_for' in s:
        operation=operation or ('generate_video' if values.get('mode')==0 else 'animate_image')
        parameters=s['parameters_for'](operation)
        if 'chosen_variant' in s: model=s['chosen_variant']() or ''
    elif callable(s.get('parameters')):
        operation=operation or ('generate_variation' if 'flux' in identifier and values.get('mode')==1 else 'generate_image' if 'flux' in identifier else 'generate_sound')
        parameters=s['parameters']()
        if 'audiogen' in identifier:
            backend=s['parameters'].__globals__['BACKENDS'][values['backend']][0]
    elif 'piper' in identifier:
        operation=operation or 'synthesize'
        parameters={k:s[v] for k,v in {'text':'text','voice':'selected','speaker':'speaker','threads':'threads','length_scale':'length','volume':'volume','noise_scale':'noise','noise_w_scale':'width','normalize':'normalize'}.items() if v in s}
    elif 'unirig' in identifier:
        operation=operation or 'mesh_to_rig'; parameters={'mesh':s.get('mesh',''),'seed':s.get('seed',42),'faces_target':s.get('faces',10000)}
    elif 'xatlas' in identifier:
        operation=operation or ('unwrap','repack')[s.get('operation',0)]
        parameters={k:s[v] for k,v in {'input':'source','resolution':'resolution','padding':'padding','iterations':'iterations','maxCost':'maxcost','rotateCharts':'rotate','bruteForce':'brute','blockAlign':'block','fixWinding':'winding'}.items() if v in s}
    elif 'nymphaea' in identifier or 'profile' in s:
        operation=operation or 'generate'; parameters={k:s[k] for k in ('text','profile','history','threads','seed') if k in s}
    elif identifier=='cy.tools.manager':
        entries=s.get('entries',[])
        if not entries: raise ValueError('Select a Tool first')
        entry=entries[s.get('selected',0)]; op=entry['operations'][s.get('operation_index',0)]
        operation='invoke_tool'; payload={}
        for key,value in values.items():
            spec=op['inputSchema'].get('properties',{}).get(key,{})
            if value=='' and key not in op['inputSchema'].get('required',[]): continue
            payload[key]=json.loads(value) if spec.get('type') in ('object','array') and isinstance(value,str) else value
        parameters={'toolId':entry['id'],'operationId':op['id'],'parameters':payload,'backendId':s.get('backend',''),'modelId':s.get('model','')}
    else:
        preferred=('image_to_mesh','generate_pbr','remesh','synthesize','reconstruct','reconstruct_motion','generate')
        operation=operation or next((key for key in preferred if any(o['id']==key for o in manifest['operations'])),manifest['operations'][0]['id'])
    return recipe(manifest,operation,parameters,backend=backend,model=model,
                  ui_state={'form':values,'widgets':_widget_values,'variables':variable_state()})

def bind_runtime(callback):
    global _scope_getter,_runtime
    _scope_getter=callback; _runtime=_runtime or scope().get('runtime')
    if _runtime is None or getattr(_runtime,'_ui_configuration_bound',False): return
    original=_runtime.submit
    def submit(principal,session_id,operation_id,parameters,**kwargs):
        global _last_recipe,_configuration_message
        job=original(principal,session_id,operation_id,parameters,**kwargs)
        if not operation_id.startswith(('inspect','diagnos','install','update','list','scan','register','remove','enable','export','launch','save_','preview_')):
            try:
                from generation_config import recipe,save
                _last_recipe=recipe(_runtime.descriptor,operation_id,job.get('parameters',parameters),
                                backend=job.get('backendId',kwargs.get('backend_id','')),model=job.get('modelId',kwargs.get('model_id','')),
                                ui_state={'form':form_state(),'widgets':_widget_values,'variables':variable_state()},job_id=job['jobId'])
                if preferences.values.get('autosave_generation'):
                    path=ROOT/'data/configurations/autosave'/ (job['jobId']+'.json')
                    save(path,_last_recipe); _configuration_message=tr('Configuration saved: ')+str(path)
            except Exception as exc: _configuration_message=tr('Configuration save failed: ')+str(exc)
        return job
    _runtime.submit=submit; _runtime._ui_configuration_bound=True

def configuration_panel():
    global _configuration_message,_configuration_name,_configuration_path,_restore_widgets,_configuration_operation
    from generation_config import save,load
    native=raw(); native.separator(); native.text(tr('Generation configurations'))
    changed,enabled=native.checkbox(label('Autosave on generation'),bool(preferences.values.get('autosave_generation')))
    if changed: preferences.values['autosave_generation']=enabled; preferences.save()
    native.text_wrapped(tr('Save current settings as versioned JSON. Loading never starts generation. Autosaves contain the exact submitted parameters and can be replayed by an AI.'))
    if _runtime is not None:
        candidates=[o['id'] for o in _runtime.descriptor['operations'] if not o['id'].startswith(('inspect','diagnos','install','update','list','scan','register','remove','enable','export','launch','save_','preview_','t_'))]
        choices=['Automatic']+candidates
        index=choices.index(_configuration_operation) if _configuration_operation in choices else 0
        changed,index=native.combo(label('Configuration operation'),index,[tr(x) for x in choices])
        if changed: _configuration_operation=choices[index] if index else ''
    _,_configuration_name=native.input_text(label('Configuration name'),_configuration_name)
    if native.button(label('Save configuration')):
        try:
            name=re.sub(r'[^A-Za-z0-9_.-]+','_',_configuration_name).strip('.') or 'configuration'
            path=ROOT/'data/configurations'/(name+'-'+uuid.uuid4().hex[:8]+'.json')
            save(path,current_recipe()); _configuration_path=str(path); _configuration_message=tr('Configuration saved: ')+str(path)
        except Exception as exc: _configuration_message=tr('Configuration save failed: ')+str(exc)
    native.same_line()
    if native.button(label('Browse configuration')):
        from imgui_bundle import portable_file_dialogs as pfd
        global _config_dialog
        _config_dialog=pfd.open_file(tr('Load configuration'),str(ROOT/'data/configurations'),['JSON','*.json'])
    if '_config_dialog' in globals() and _config_dialog and _config_dialog.ready():
        files=_config_dialog.result()
        if files: _configuration_path=files[0]
        _config_dialog=None
    _,_configuration_path=native.input_text(label('Configuration file'),_configuration_path)
    if native.button(label('Load configuration')):
        try:
            load_current(_configuration_path)
            _configuration_message=tr('Configuration loaded. Review the settings before generating.')
        except Exception as exc: _configuration_message=tr('Configuration load failed: ')+str(exc)
    if _configuration_message: native.text_wrapped(_configuration_message)

def load_current(path):
    global _restore_widgets,_configuration_operation
    from generation_config import load
    if _runtime is None: raise ValueError('Runtime unavailable')
    value=load(path,_runtime.descriptor)
    if _model_panel is not None:
        selected={k:v for k,v in value['parameters'].items() if k in ('model_profile','loras','device')}
        import model_options
        mapping=model_options.capabilities()['operations'].get(value['operationId'],{}).get('deviceBackends',{})
        for device,backend in mapping.items():
            if backend==value.get('backendId'):selected['device']=device
        _model_panel.values[value['operationId']]=selected
    if _recipe_loader: _recipe_loader(value)
    state=value.get('uiState',{}); target=form_state(); stored=state.get('form',{})
    if isinstance(stored,dict):
        for key,item in stored.items():
            if key in target: target[key]=item
    _restore_widgets=dict(state.get('widgets',{}))
    variables=state.get('variables',{})
    if isinstance(variables,dict):
        allowed=variable_state()
        set_variables({k:v for k,v in variables.items() if k in allowed})
    _configuration_operation=value['operationId']
    return value

def raw():
    global _raw
    if _raw is None:
        from imgui_bundle import imgui as native
        _raw = native
    return _raw

def tr(text):
    if not isinstance(text, str) or not text: return text
    language = preferences.values['language']
    translation = catalog.get(text) or _normalized.get(normalized(text))
    if translation: return translation.get(language, translation.get('en', text))
    # Only registered display fragments are substituted. No remote translator,
    # model inference, token access or modification of user-entered text.
    if not text.lstrip().startswith(('{','[')):
        for prefix in _prefixes:
            if text.startswith(prefix): return catalog[prefix].get(language,prefix)+tr(text[len(prefix):])
    return text

def label(text):
    if not isinstance(text, str) or not text or text.startswith('##'): return text
    visible, separator, identity = text.partition('###')
    if not separator:
        # ## hides a suffix but the FULL original label contributes to its ID.
        # Only an explicit ### intentionally replaces the identity.
        visible = text.partition('##')[0]
        identity = text
    return tr(visible)+'###'+identity

class ImGuiFacade:
    texts = {'text', 'text_wrapped', 'text_disabled', 'text_unformatted', 'set_tooltip', 'bullet_text', 'separator_text'}
    labels = {'button','small_button','checkbox','radio_button','input_text','input_text_multiline',
              'input_int','input_float','input_double','slider_int','slider_float','drag_int','drag_float',
              'combo','begin_combo','selectable','collapsing_header','tree_node','tree_node_ex',
              'begin_tab_item','menu_item','begin_menu'}
    def __getattr__(self, name):
        target = getattr(raw(), name)
        if name=='push_id':
            def push(value):
                _id_stack.append(str(value)); return target(value)
            return push
        if name=='pop_id':
            def pop():
                if _id_stack: _id_stack.pop()
                return target()
            return pop
        if name == 'begin_tab_bar':
            def begin(*args, **kwargs):
                global _tab_depth, _has_tabs
                opened = target(*args, **kwargs)
                if opened: _tab_depth += 1; _has_tabs = True
                return opened
            return begin
        if name == 'end_tab_bar':
            def end(*args, **kwargs):
                global _tab_depth
                if _tab_depth == 1 and not _inside_options:
                    if _mesh_panel is not None: _mesh_panel.tab()
                    journal.draw_tab()
                    if _model_panel is not None:_model_panel.draw_tab()
                    if _advanced_panel is not None:_advanced_panel.draw_tab()
                    options_tab()
                _tab_depth -= 1
                return target(*args, **kwargs)
            return end
        if name not in self.texts | self.labels | {'progress_bar'}: return target
        def call(*args, **kwargs):
            args = list(args)
            from generation_config import secret_key
            editable=name.startswith(('input_','slider_','drag_')) or name in ('checkbox','combo')
            key='/'.join(_id_stack+[str(args[0])]) if args else ''
            restore=False
            if editable and len(args)>1 and not secret_key(key) and key in _restore_widgets:
                value=_restore_widgets.pop(key)
                if type(value)==type(args[1]):
                    if name=='combo' and len(args)>2: value=max(0,min(value,len(args[2])-1))
                    args[1]=value; restore=True
            # Free-form text may be user content or generated output. Source UI
            # literals use explicit tr(); never translate arbitrary text here.
            if args and name in self.labels: args[0] = label(args[0])
            if name == 'combo' and len(args)>2 and isinstance(args[2], (list,tuple)):
                args[2] = [tr(value) for value in args[2]]
            if name == 'progress_bar' and len(args)>2: args[2] = tr(args[2])
            result=target(*args, **kwargs)
            if editable and not secret_key(key) and isinstance(result,tuple) and len(result)==2:
                _widget_values[key]=result[1]
                if restore: result=(True,result[1])
            return result
        return call

imgui = ImGuiFacade()

def apply_style():
    native = raw()
    {'dark': native.style_colors_dark, 'light': native.style_colors_light,
     'classic': native.style_colors_classic}[preferences.values['theme']]()
    style = native.get_style()
    if hasattr(style, 'font_scale_main'): style.font_scale_main = preferences.values['font_scale']
    else: native.get_io().font_global_scale = preferences.values['font_scale']

def license_records():
    manifest = read(APP/'CyTool.json', {})
    records = [{'kind':'Tool', 'name':manifest.get('name',ROOT.name),
                'license':manifest.get('license') or 'Not declared',
                'url':manifest.get('licenseUrl') or manifest.get('homepage','')}]
    for backend in manifest.get('backends',[]):
        records.append({'kind':'Engine','name':backend.get('name',backend.get('id','')),
                        'license':backend.get('license') or 'Not declared',
                        'url':backend.get('licenseUrl') or backend.get('source','')})
        for model in backend.get('models',[]):
            records.append({'kind':'Model','name':model.get('name',model.get('id','')),
                            'license':model.get('license') or 'Not declared',
                            'url':model.get('licenseUrl') or model.get('source','')})
    extra = read(APP/'licenses.json', [])
    if isinstance(extra,list): records.extend(x for x in extra if isinstance(x,dict))
    return records

def dependency_records():
    records=[]
    for dist in sorted(importlib.metadata.distributions(), key=lambda d:d.metadata.get('Name','').lower()):
        meta=dist.metadata
        license_name=meta.get('License-Expression') or meta.get('License')
        if not license_name:
            license_name='; '.join(x.split(' :: ')[-1] for x in meta.get_all('Classifier',[]) if x.startswith('License ::')) or 'Not declared'
        records.append({'name':meta.get('Name','?'), 'version':dist.version,
                        'license':license_name, 'url':meta.get('Home-page','')})
    return records

def options_panel():
    global _licenses
    native=raw()
    native.text(tr('Interface preferences'))
    changed,index=native.combo(label('Language'),('en','fr').index(preferences.values['language']),['English','Français'])
    if changed: preferences.values['language']=('en','fr')[index]; preferences.save()
    changed,index=native.combo(label('Theme'),('dark','light','classic').index(preferences.values['theme']),[tr('Dark'),tr('Light'),tr('Classic')])
    if changed: preferences.values['theme']=('dark','light','classic')[index]; preferences.save(); apply_style()
    changed,scale=native.slider_float(label('Text size'),preferences.values['font_scale'],.8,1.6,'%.2fx')
    if changed: preferences.values['font_scale']=scale; preferences.save(); apply_style()
    if native.button(label('Reset interface preferences')):
        preferences.values=dict(DEFAULTS); preferences.save(); apply_style()
    native.text_wrapped(tr('Preferences are saved for this Tool. Model settings and files are not changed.'))
    configuration_panel()
    from installation_ui import panel as installation_panel
    installation_panel(native, tr, label)
    native.separator()
    native.text(tr('Licenses'))
    native.text_wrapped(tr('Application, engine and model licenses are separate. Missing information does not grant usage rights. See the original license for its exact terms; translated interface labels are not a legal translation.'))
    if _licenses is None: _licenses=license_records()
    for index,record in enumerate(_licenses):
        native.push_id(index)
        if native.collapsing_header(tr(record.get('kind','Component'))+' / '+str(record.get('name',''))):
            text=str(record.get('license') or 'Not declared')
            native.text_wrapped(tr(text) if text=='Not declared' else text)
            if record.get('notes'): native.text_wrapped(str(record['notes']))
            url=record.get('url','')
            if isinstance(url,str) and url.startswith(('https://','http://')) and native.button(label('Open official page / license')): webbrowser.open(url)
        native.pop_id()
    if native.collapsing_header(label('Installed dependencies')):
        global _dependencies
        if '_dependencies' not in globals(): _dependencies=dependency_records()
        native.text_wrapped(tr('License information comes from installed package metadata. A missing or incomplete declaration must be checked with the publisher.'))
        for index,record in enumerate(_dependencies):
            native.push_id('dependency-'+str(index))
            if native.collapsing_header(record['name']+' '+record['version']):
                value=record['license']; native.text_wrapped(tr(value) if value=='Not declared' else value)
                if record['url'].startswith(('https://','http://')) and native.button(label('Open publisher page')): webbrowser.open(record['url'])
            native.pop_id()

def options_tab():
    global _inside_options
    native=raw()
    flags=native.TabItemFlags_.set_selected if '--ui-test-options' in sys.argv else 0
    opened,_=native.begin_tab_item(label('Options'),flags=flags)
    if opened:
        _inside_options=True
        try: options_panel()
        finally: _inside_options=False; native.end_tab_item()

def run(runner):
    global _mesh_panel,_model_panel,_advanced_panel
    from imgui_bundle import hello_imgui
    original=runner.callbacks.show_gui
    bind_runtime(original)
    from advanced_ui import Panel as AdvancedPanel
    principal=next((v for v in scope().values() if hasattr(v,'client_id') and hasattr(v,'permissions')),None)
    _advanced_panel=AdvancedPanel(_runtime,principal)
    if (APP/'model-capabilities.json').is_file():
        from model_options_ui import Panel
        _model_panel=Panel(_runtime)
    if _runtime is not None:
        journal.bind(_runtime)
        for value in scope().values():
            if hasattr(value,'client_id') and hasattr(value,'permissions'):journal.bind(_runtime,value)
    if (APP/'mesh-viewer.json').is_file():
        from mesh_viewer_ui import install
        _mesh_panel=install(_runtime,ROOT)
    frames=0
    # Run options smoke checks without mutating the user's saved preference.
    test_language=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--ui-test-language=')),None)
    if test_language in ('en','fr'): preferences.values['language']=test_language
    runner.app_window_params.window_title=tr(runner.app_window_params.window_title)
    source=Path(sys.modules['__main__'].__file__).read_text(encoding='utf-8-sig')
    has_tabs='begin_tab_bar(' in source
    def draw():
        nonlocal frames
        frames+=1
        journal.poll()
        if _mesh_panel is not None: _mesh_panel.poll()
        if frames==1: apply_style()
        if has_tabs: original()
        else:
            native=raw()
            if native.begin_tab_bar('###cytool-navigation'):
                opened,_=native.begin_tab_item(label('Tool'))
                if opened:
                    original(); native.end_tab_item()
                if _mesh_panel is not None: _mesh_panel.tab()
                journal.draw_tab()
                if _model_panel is not None:_model_panel.draw_tab()
                if _advanced_panel is not None:_advanced_panel.draw_tab()
                options_tab(); native.end_tab_bar()
        if '--ui-test-config' in sys.argv and frames==5:
            from generation_config import save
            value=current_recipe(); path=ROOT/'data/reports/configuration-roundtrip.json'
            save(path,value)
            original_form=json.loads(json.dumps(form_state()))
            if 'seed' in form_state(): form_state()['seed']=123456789
            load_current(path)
            assert form_state()==original_form,'Configuration load did not restore the current form'
        if '--ui-test-options' in sys.argv and frames>15: runner.app_shall_exit=True
        if journal.test:runner.app_shall_exit=journal.frames>=8
        if _advanced_panel.test:runner.app_shall_exit=_advanced_panel.frames>=8
        if _model_panel is not None and _model_panel.test:runner.app_shall_exit=_model_panel.frames>=8
        if _mesh_panel is not None:
            if _mesh_panel.test: runner.app_shall_exit=False
            _mesh_panel.check_test(runner)
    runner.callbacks.show_gui=draw
    try: hello_imgui.run(runner)
    except Exception:
        import traceback
        journal.write(traceback.format_exc(),'ERROR')
        raise
    finally:
        if _mesh_panel is not None: _mesh_panel.close()
        if _model_panel is not None:_model_panel.close()
        if _advanced_panel is not None:_advanced_panel.close()
    if _advanced_panel.test:
        from standalone_log import save_screenshot
        reports=ROOT/'data/reports';reports.mkdir(parents=True,exist_ok=True)
        save_screenshot(reports/('advanced-'+preferences.values['language']+'.png'),hello_imgui.final_app_window_screenshot())
        (reports/'advanced-test.json').write_text(json.dumps({'frames':_advanced_panel.frames,'runtime':_runtime is not None,'error':_advanced_panel.message}),'utf-8')
    if journal.test:
        from standalone_log import save_screenshot
        reports=ROOT/'data/reports';reports.mkdir(parents=True,exist_ok=True)
        save_screenshot(reports/('logs-'+preferences.values['language']+'.png'),hello_imgui.final_app_window_screenshot())
        (reports/'logs-test.json').write_text(json.dumps({'frames':journal.frames,'clipboard':True,'log':str(journal.path)}),'utf-8')
    if _mesh_panel is not None and _mesh_panel.test:
        from PIL import Image
        screenshot=hello_imgui.final_app_window_screenshot()
        if screenshot.size:
            reports=ROOT/'data/reports';reports.mkdir(parents=True,exist_ok=True)
            Image.fromarray(screenshot).save(reports/('mesh-viewer-'+preferences.values['language']+'.png'))
    if '--ui-test-options' in sys.argv:
        reports=ROOT/'data/reports'; reports.mkdir(parents=True,exist_ok=True)
        try:
            from PIL import Image
            screenshot=hello_imgui.final_app_window_screenshot()
            if screenshot.size: Image.fromarray(screenshot).save(reports/('options-'+preferences.values['language']+'.png'))
        except (ImportError,TypeError): pass
        (reports/('options-'+preferences.values['language']+'.json')).write_text(json.dumps({'language':preferences.values['language'],'closed':True,'frames':frames}),encoding='utf-8')
