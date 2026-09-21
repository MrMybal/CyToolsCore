"""Complete operation access for standalone users; no UI imports in the runtime."""
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

class Panel:
    def __init__(self,runtime,principal=None):
        self.runtime=runtime;self.index=0;self.drafts={};self.job=None;self.message='';self.frames=0
        self.test='--ui-test-advanced' in sys.argv;self.future=None;self.executor=ThreadPoolExecutor(max_workers=1)
        if runtime is not None:
            from cytools_core.transports.api import LocalClient
            from model_options_ui import submit_exact
            self.submit=lambda *args,**kwargs:submit_exact(runtime,*args,**kwargs)
            self.principal=principal or runtime.authenticate(runtime.create_client('Standalone advanced')['token'])
            self.client=LocalClient(runtime,self.principal);self.session=runtime.create_session(self.principal, temporary=False)['sessionId']
            from ui_common import journal
            journal.bind(runtime,self.principal)
    def state(self):
        operation=self.runtime.descriptor['operations'][self.index]
        if operation['id'] not in self.drafts:
            defaults={k:v['default'] for k,v in operation['inputSchema'].get('properties',{}).items() if 'default' in v}
            self.drafts[operation['id']]={'text':json.dumps(defaults,indent=2),'backend':'','model':'','priority':3,'queue':'','execution':'','path':''}
        return operation,self.drafts[operation['id']]
    def payload(self):
        operation,state=self.state()
        from cytools_core import validate_parameters
        return validate_parameters(json.loads(state['text']),operation['inputSchema'])
    def restore(self,value):
        self.index=next(i for i,o in enumerate(self.runtime.descriptor['operations']) if o['id']==value['operationId'])
        _,state=self.state();state.update(text=json.dumps(value['parameters'],indent=2,ensure_ascii=False),backend=value.get('backendId',''),model=value.get('modelId',''))
        for key in ('priority','queue','execution'):
            if key in value.get('uiState',{}).get('invocation',{}):state[key]=value['uiState']['invocation'][key]
    def draw_tab(self):
        from ui_common import raw,label,tr,ROOT,current_recipe
        ui=raw();opened,_=ui.begin_tab_item(label('Advanced operations'),flags=ui.TabItemFlags_.set_selected if self.test else 0)
        if not opened:return
        try:
            self.frames+=1
            if self.runtime is None:ui.text_wrapped(tr('Runtime unavailable'));return
            if self.future and self.future.done():
                try:self.message=json.dumps(self.future.result(),indent=2,ensure_ascii=False)
                except Exception as exc:self.message=str(exc)
                self.future=None
            if self.job:self.job=self.runtime.get_job(self.principal,self.job['jobId'])
            _,self.index=ui.combo(label('Operation'),self.index,[o['id'] for o in self.runtime.descriptor['operations']])
            operation,state=self.state()
            ui.text_wrapped(tr('All declared parameters are available here. This JSON takes precedence over the simplified form and model preferences.'))
            ui.text_wrapped(operation['description'])
            if ui.button(label('Copy operation contract')):ui.set_clipboard_text(json.dumps(operation,indent=2,ensure_ascii=False))
            ui.same_line()
            if ui.button(label('Import current form')):self.restore(current_recipe());operation,state=self.state()
            if ui.collapsing_header(label('Full input and output schemas')):
                ui.input_text_multiline('##contract',json.dumps(operation,indent=2,ensure_ascii=False),ui.ImVec2(-1,180),flags=ui.InputTextFlags_.read_only)
            _,state['text']=ui.input_text_multiline(label('Parameters JSON'),state['text'],ui.ImVec2(-1,200))
            _,state['backend']=ui.input_text(label('Backend ID'),state['backend'])
            _,state['model']=ui.input_text(label('Model ID'),state['model'])
            priorities=['Interactive','Critical','High','Normal','Background','Low']
            _,state['priority']=ui.combo(label('Priority'),state['priority'],priorities)
            _,state['queue']=ui.input_text(label('Queue timeout (seconds, empty = default)'),state['queue'])
            _,state['execution']=ui.input_text(label('Execution timeout (seconds, empty = default)'),state['execution'])
            if ui.button(label('Validate and estimate')) and self.future is None:
                self.future=self.executor.submit(self.client.call,'CanRun',operationId=operation['id'],parameters=self.payload(),backendId=state['backend'],modelId=state['model'])
            ui.same_line()
            active=self.job and self.job['state'] not in ('Completed','Cancelled','Failed')
            ui.begin_disabled(bool(active))
            try:
                if ui.button(label('Run exact parameters')):
                    options={key:float(state[field]) for key,field in (('queue_timeout','queue'),('execution_timeout','execution')) if state[field].strip()}
                    self.job=self.submit(self.principal,self.session,operation['id'],self.payload(),backend_id=state['backend'],model_id=state['model'],priority=priorities[state['priority']],**options)
                    self.message=json.dumps(self.job,indent=2,ensure_ascii=False)
            finally:ui.end_disabled()
            if active:
                ui.same_line()
                if ui.button(label('Cancel')):self.runtime.cancel(self.principal,self.job['jobId'])
            _,state['path']=ui.input_text(label('Configuration path'),state['path'])
            if ui.button(label('Save exact configuration')):
                from generation_config import recipe,save
                path=Path(state['path']) if state['path'] else ROOT/'data/configurations'/(operation['id']+'-advanced.json')
                save(path,recipe(self.runtime.descriptor,operation['id'],self.payload(),backend=state['backend'],model=state['model'],ui_state={'invocation':{k:state[k] for k in ('priority','queue','execution')}}))
                state['path']=str(path);self.message=str(path)
            ui.same_line()
            if ui.button(label('Load configuration')):
                from generation_config import load
                self.restore(load(state['path'],self.runtime.descriptor))
            if self.job:
                ui.text(self.job['state'])
                if ui.button(label('Copy job and outputs')):ui.set_clipboard_text(json.dumps(self.job,indent=2,ensure_ascii=False))
                ui.input_text_multiline('##job',json.dumps(self.job,indent=2,ensure_ascii=False),ui.ImVec2(-1,180),flags=ui.InputTextFlags_.read_only)
            if self.message:ui.input_text_multiline('##result',self.message,ui.ImVec2(-1,120),flags=ui.InputTextFlags_.read_only)
        except Exception as exc:self.message=str(exc)
        finally:ui.end_tab_item()
    def close(self):
        self.executor.shutdown(wait=True,cancel_futures=True)
        if self.runtime is not None:
            try:self.runtime.close_session(self.principal,self.session)
            except Exception:pass
