"""Standalone editor for the local model library and per-operation execution settings."""
import json
from pathlib import Path
import sys
import model_options as models
from contextvars import ContextVar

_explicit_parameters=ContextVar('cytools-explicit-ui-parameters',default=False)

def submit_exact(runtime,*args,**kwargs):
    """Keep logging/preview/autosave hooks while bypassing simplified form overrides."""
    token=_explicit_parameters.set(True)
    try:return runtime.submit(*args,**kwargs)
    finally:_explicit_parameters.reset(token)

class Panel:
    def __init__(self,runtime):
        self.runtime=runtime;self.operation=0;self.message='';self.name='';self.path='';self.license='';self.source='';self.base='';self.format=0;self.dialog=None
        self.path_settings=models.ROOT/'data/settings/model-selection.json'
        self.values=models.read(self.path_settings,{})
        self.test='--ui-test-models' in sys.argv;self.frames=0
        if runtime is not None:
            original=runtime.submit
            def submit(principal,session,operation,parameters,**kwargs):
                if not _explicit_parameters.get():parameters,kwargs=self.apply(operation,parameters,kwargs)
                return original(principal,session,operation,parameters,**kwargs)
            runtime.submit=submit
    def save(self):
        if self.test:return
        self.path_settings.parent.mkdir(parents=True,exist_ok=True)
        from generation_config import save
        save(self.path_settings,self.values)
    def apply(self,operation,parameters,kwargs):
        selection=self.values.get(operation,{})
        props=next((o['inputSchema'].get('properties',{}) for o in self.runtime.descriptor['operations'] if o['id']==operation),{})
        parameters=dict(parameters);kwargs=dict(kwargs)
        for key in ('model_profile','loras'):
            if key in props and key in selection:parameters[key]=selection[key]
        if parameters.get('model_profile') and models.capabilities()['operations'].get(operation,{}).get('baseModelId'):
            kwargs['model_id']=''  # The adapter resolves the registered base variant from the profile.
        device=selection.get('device','default')
        if device!='default':
            if 'device' in props:
                if device=='auto':device='cuda' if any('CUDA' in g.get('computeBackends',[]) for g in self.runtime.system.get('gpus',[])) else 'cpu'
                if device not in props['device'].get('enum',[]):raise ValueError('Device is not supported by this operation')
                parameters['device']=device
            else:
                mapping=models.capabilities()['operations'].get(operation,{}).get('deviceBackends',{})
                if device=='auto':device='cuda' if any('CUDA' in g.get('computeBackends',[]) for g in self.runtime.system.get('gpus',[])) else 'cpu'
                if device in mapping:kwargs['backend_id']=mapping[device]
        return parameters,kwargs
    def draw_tab(self):
        from ui_common import raw,label,tr
        ui=raw();opened,_=ui.begin_tab_item(label('Models / compute'),flags=ui.TabItemFlags_.set_selected if self.test else 0)
        if not opened:return
        try:self.draw(ui,label,tr)
        except Exception as exc:self.message=str(exc)
        finally:ui.end_tab_item()
    def draw(self,ui,label,tr):
        specs=models.capabilities();operations=list(specs.get('operations',{}))
        if not operations:
            ui.text_wrapped(tr('This Tool has no configurable inference model.'));self.frames+=1;return
        self.operation=min(self.operation,len(operations)-1)
        _,self.operation=ui.combo(label('Operation'),self.operation,operations)
        operation=operations[self.operation];spec=specs['operations'][operation]
        state=self.values.setdefault(operation,{})
        devices=['default']+spec.get('devices',[])
        current=state.get('device','default');index=devices.index(current) if current in devices else 0
        changed,index=ui.combo(label('Compute device'),index,[tr({'default':'Use generation settings','auto':'Auto','cpu':'CPU','cuda':'GPU (CUDA)'}[d]) for d in devices])
        if changed:state['device']=devices[index];self.save()
        ui.text_wrapped(tr(spec.get('deviceNote','')))
        items=models.catalog()['models'];compatible=[i for i in items if i['kind']=='model' and i['format'] in spec.get('models',[])]
        ids=['']+[i['id'] for i in compatible];names=[tr('Built-in model')]+[i['name'] for i in compatible]
        current=state.get('model_profile','');index=ids.index(current) if current in ids else 0
        if spec.get('models'):
            changed,index=ui.combo(label('Model profile'),index,names)
            if changed:state['model_profile']=ids[index];self.save()
            if index:
                item=compatible[index-1];ui.text_wrapped(item['path']);ui.text_wrapped(tr('License: ')+item['license'])
                ui.text_wrapped(tr('Use the matching built-in architecture and task. Registration checks structure, not generation quality.'))
        else:ui.text_wrapped(tr('Custom checkpoints are not supported by this adapter.'))
        adapters=[i for i in items if i['kind']=='lora' and i['format'] in spec.get('loras',[])]
        if spec.get('loras'):
            ui.separator_text(label('LoRA adapters'))
            state.setdefault('loras',[])
            for item in adapters:
                ui.push_id(item['id']);active=next((x for x in state['loras'] if x['id']==item['id']),None)
                changed,enabled=ui.checkbox(item['name'],active is not None)
                if changed:
                    state['loras']=[x for x in state['loras'] if x['id']!=item['id']]
                    if enabled:state['loras'].append({'id':item['id'],'strength':1.})
                    self.save()
                if active:
                    ui.same_line();changed,active['strength']=ui.slider_float(label('Strength'),active['strength'],-4.,4.)
                    if changed:self.save()
                ui.pop_id()
            if not adapters:ui.text_wrapped(tr('Register a compatible local LoRA below.'))
        else:ui.text_wrapped(tr('LoRA loading is not supported by this adapter.'))
        ui.separator_text(label('Add a local model or LoRA'))
        formats=list(specs.get('formats',{}))
        if formats:
            _,self.name=ui.input_text(label('Display name'),self.name)
            _,self.format=ui.combo(label('Model format'),min(self.format,len(formats)-1),formats)
            _,self.path=ui.input_text(label('Local model path'),self.path);ui.same_line()
            if ui.button(label('Browse model')):
                from imgui_bundle import portable_file_dialogs as pfd
                if specs['formats'][formats[self.format]].get('suffix'):self.dialog=pfd.open_file(tr('Local model path'),str(models.ROOT/'data/models'),['Model','*.safetensors *.onnx *.gguf'])
                else:self.dialog=pfd.select_folder(tr('Local model path'),str(models.ROOT/'data/models'))
            if self.dialog is not None and self.dialog.ready(0):
                result=self.dialog.result();self.path=(result[0] if result else '') if isinstance(result,list) else result;self.dialog=None
            bases=specs['formats'][formats[self.format]].get('bases',[])
            if bases:
                index=bases.index(self.base) if self.base in bases else 0
                _,index=ui.combo(label('Base model / variant'),index,bases);self.base=bases[index]
            else:_,self.base=ui.input_text(label('Base model / variant'),self.base)
            _,self.license=ui.input_text(label('Model license'),self.license)
            _,self.source=ui.input_text(label('Model source URL'),self.source)
            if ui.button(label('Register local model')):
                models.add_asset(self.name,self.path,formats[self.format],self.base,self.license,self.source)
                self.message=tr('Model registered. Select it above before generating.')
            ui.text_wrapped(tr('Files are referenced in place, never copied into configurations. No download starts automatically.'))
        ui.text_wrapped(tr('Few-step acceleration requires a matching distilled model or LoRA and its documented scheduler. Reducing steps alone is not equivalent.'))
        if self.message:ui.text_wrapped(self.message)
        self.frames+=1
    def close(self):
        if self.dialog:self.dialog.kill()
