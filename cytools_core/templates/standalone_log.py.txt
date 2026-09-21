"""Local standalone diagnostics. Import only from the graphical entry point."""
from datetime import datetime, timezone
import io
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
import threading
import time
import traceback

LIMIT=8*1024*1024
def save_screenshot(path,pixels):
    # Optional smoke-test capture without adding Pillow to every audio/text Tool.
    import struct,zlib
    height,width,channels=pixels.shape
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    data=b''.join(b'\0'+pixels[y,:,:3].tobytes() for y in range(height))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(data))+chunk(b'IEND',b''))
def redact(text):
    text=re.sub(r'\bhf_[A-Za-z0-9]{8,}\b','[REDACTED]',str(text))
    text=re.sub(r'(?i)(bearer\s+)[^\s,;\"\']+',r'\1[REDACTED]',text)
    return re.sub(r'''(?i)((?:["']?)(?:access_token|api_key|apikey|password|authorization|token|secret)(?:["']?)\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''',r'\1[REDACTED]',text)

class SafeFormatter(logging.Formatter):
    def format(self,record):return redact(super().format(record))

class Stream(io.TextIOBase):
    def __init__(self,original,journal,level):self.original=original;self.journal=journal;self.level=level;self.local=threading.local()
    @property
    def encoding(self):return 'utf-8'
    def write(self,text):
        # Buffer split writes so a token cannot leak between fragments.
        buffer=getattr(self.local,'buffer','')+str(text)
        while '\n' in buffer:
            line,buffer=buffer.split('\n',1)
            if line.strip():self.journal.write(line,self.level)
        self.local.buffer=buffer[-65536:]
        if self.original:
            try:self.original.write(text)
            except (OSError,ValueError):pass
        return len(text)
    def flush(self):
        if self.original:
            try:self.original.flush()
            except (OSError,ValueError):pass

class Journal:
    def __init__(self,root):
        self.root=Path(root);folder=self.root/'data/logs';folder.mkdir(parents=True,exist_ok=True)
        self.path=folder/'standalone.log';self.selected=self.path;self.text='';self.paused=False;self.last=0.;self.focus=False
        self.copy_thread=None;self.copy_result=None
        self.principals={};self.cursors={};self.files=set();self.bound=set();self.discovery={};self.test='--ui-test-logs' in sys.argv;self.frames=0
        self.handler=RotatingFileHandler(self.path,maxBytes=2*1024*1024,backupCount=3,encoding='utf-8',delay=True)
        self.handler.setFormatter(SafeFormatter('%(asctime)s %(levelname)s %(message)s'))
        self.logger=logging.getLogger('cytools.standalone.'+str(id(self)));self.logger.setLevel(logging.INFO);self.logger.propagate=False;self.logger.addHandler(self.handler)
        self.write('Standalone started; '+sys.version.split()[0])
    def write(self,message,level='INFO'):
        self.logger.log(getattr(logging,level.upper(),logging.INFO),str(message))
    def bind(self,runtime,principal=None):
        if principal is not None:self.principals[(id(runtime),principal.client_id)]=(runtime,principal)
        if runtime is None or id(runtime) in self.bound:return
        self.bound.add(id(runtime));original=runtime.submit
        def submit(principal,session_id,operation_id,parameters,**kwargs):
            self.principals[(id(runtime),principal.client_id)]=(runtime,principal)
            try:
                job=original(principal,session_id,operation_id,parameters,**kwargs)
                self.write('Submitted '+operation_id+' job='+job['jobId'])
                return job
            except Exception:
                self.write(traceback.format_exc(),'ERROR');raise
        runtime.submit=submit
    def poll(self):
        if time.monotonic()-self.last<.3:return
        self.last=time.monotonic()
        for key,(runtime,principal) in list(self.principals.items()):
            try:
                batch=runtime.events(principal,after=self.cursors.get(key,0));self.cursors[key]=batch['cursor']
                if batch.get('gap'):self.write('Runtime event buffer gap','WARNING')
                for event in batch['events']:
                    self.write(event['type']+' '+event.get('jobId','')+' '+json.dumps(event.get('data'),ensure_ascii=False))
                    terminal=event['type'] in ('JobCompleted','JobFailed','JobCancelled')
                    discover=event.get('jobId') and time.monotonic()-self.discovery.get(event['jobId'],0)>1
                    if event.get('jobId') and (terminal or discover):
                        job=runtime.get_job(principal,event['jobId'])
                        self.discovery[event['jobId']]=time.monotonic()
                        if terminal:
                            if job.get('error'):self.write(json.dumps(job['error'],ensure_ascii=False),'ERROR')
                            outputs=job.get('outputs') or {}
                            summary={k:outputs[k] for k in ('width','height','device','device_name','model_id','steps_used','warnings') if k in outputs}
                            if summary:self.write('Effective output: '+json.dumps(summary,ensure_ascii=False))
                        workspace=Path(job['workspace']).resolve()
                        for p in list(workspace.rglob('*.log'))[:32]:
                            if p.resolve().is_relative_to(workspace):self.files.add(p)
            except Exception as exc:self.write('Log polling: '+str(exc),'WARNING')
    def read(self,path=None,full=False):
        path=Path(path or self.selected)
        try:
            with path.open('rb') as stream:
                size=path.stat().st_size;stream.seek(0 if full else max(0,size-LIMIT));data=stream.read() if full else stream.read(LIMIT)
            return ('[Showing last 8 MiB]\n' if size>LIMIT and not full else '')+redact(data.decode('utf-8',errors='replace'))
        except OSError as exc:return str(exc)
    def draw_tab(self):
        from ui_common import raw,label,tr
        ui=raw();opened,_=ui.begin_tab_item(label('Application log'),flags=ui.TabItemFlags_.set_selected if self.test else 0)
        if not opened:return
        try:
            choices=sorted(set((self.root/'data/logs').glob('*.log*'))|self.files,key=str)
            if self.selected not in choices:choices.insert(0,self.selected)
            changed,index=ui.combo(label('Log file'),choices.index(self.selected),[str(p.relative_to(self.root)) if p.is_relative_to(self.root) else str(p) for p in choices])
            if changed:self.selected=choices[index];self.text=self.read()
            _,self.paused=ui.checkbox(label('Pause log refresh'),self.paused);ui.same_line()
            if ui.button(label('Refresh log')):self.text=self.read()
            ui.same_line()
            if ui.button(label('Copy entire log')) and not (self.copy_thread and self.copy_thread.is_alive()):
                selected=self.selected
                def copy():self.copy_result=self.read(selected,full=True)
                self.copy_thread=threading.Thread(target=copy,daemon=True);self.copy_thread.start()
            if self.copy_result is not None:ui.set_clipboard_text(self.copy_result);self.copy_result=None
            ui.text_wrapped(tr('Select text and press Ctrl+C. Ctrl+A selects all. Refresh pauses while selecting.'))
            if not self.paused and not self.focus:self.text=self.read()
            ui.input_text_multiline('##standalone-log',self.text,ui.ImVec2(-1,max(180,ui.get_content_region_avail().y-20)),flags=ui.InputTextFlags_.read_only)
            self.focus=ui.is_item_active()
            if self.test:
                self.frames+=1
                if self.frames==3:
                    # Exercise native clipboard, restoring the user's previous value.
                    text=self.read(full=True);old=ui.get_clipboard_text();ui.set_clipboard_text(text);assert ui.get_clipboard_text()==text;ui.set_clipboard_text(old)
        finally:ui.end_tab_item()

_journal=None
def install(root):
    global _journal
    if _journal is not None:return _journal
    _journal=Journal(root)
    logging.getLogger().addHandler(_journal.handler)
    sys.stdout=Stream(sys.stdout,_journal,'INFO');sys.stderr=Stream(sys.stderr,_journal,'ERROR')
    old=sys.excepthook
    def hook(t,e,tb):_journal.write(''.join(traceback.format_exception(t,e,tb)),'ERROR');old(t,e,tb)
    sys.excepthook=hook
    previous=threading.excepthook
    def thread_hook(args):_journal.write(''.join(traceback.format_exception(args.exc_type,args.exc_value,args.exc_traceback)),'ERROR');previous(args)
    threading.excepthook=thread_hook
    return _journal
