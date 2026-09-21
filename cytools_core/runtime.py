"""Synchronous public API; one scheduler and bounded execution threads per tool."""
from __future__ import annotations
import copy
import hashlib
import json
import secrets
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from .errors import CyToolError
from .schema import validate_manifest, validate_parameters
from .resources import ResourceLedger, system_resources, platform_status
from .storage import Store, RuntimeLock

TERMINAL = {'Completed','Cancelled','Failed'}
PRIORITIES = {name:i for i,name in enumerate(['Interactive','Critical','High','Normal','Background','Low'])}
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())


@dataclass(frozen=True)
class Principal:
    client_id: str
    permissions: frozenset[str] = frozenset()


class CancellationToken:
    def __init__(self, deadline=None):
        self.event = threading.Event()
        self.deadline = deadline
        self.reason = 'Cancelled'

    def cancel(self, reason='Cancelled'):
        self.reason = reason
        self.event.set()

    def check(self):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.cancel('Timeout')
        if self.event.is_set():
            raise CyToolError(self.reason, 'Job cancelled' if self.reason=='Cancelled' else 'Execution deadline exceeded')

    def sleep(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            self.event.wait(min(.05, max(0, end-time.monotonic())))
        self.check()


class JobContext:
    def __init__(self, runtime, job_id, token):
        self.runtime, self.job_id, self.cancellation = runtime, job_id, token
        self.workspace = Path(runtime._jobs[job_id]['workspace'])
        self._temporary_inputs = []

    def path(self, relative):
        path = (self.workspace / relative).resolve()
        if path == self.workspace or not path.is_relative_to(self.workspace):
            raise CyToolError('AccessDenied', 'Output path must remain inside the job workspace')
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def progress(self, percent, **fields):
        self.cancellation.check()
        from .schema import schema
        spec = schema('job')
        payload = {'percent':percent, **fields}
        validate_parameters(payload, {'$defs':spec['$defs'], '$ref':'#/$defs/progress'}, defaults=False)
        with self.runtime._cv:
            job = self.runtime._jobs[self.job_id]
            job['progress'] = payload
            self.runtime._save(job)
            self.runtime._emit('JobProgress', job, payload)

    def log(self, message, level='Info'):
        with self.runtime._cv:
            self.runtime._emit('Log', self.runtime._jobs[self.job_id], {'level':level,'message':message})

    def emit(self, event_type, data):
        """Backend events are always bound to this job's authenticated identity."""
        json.dumps(data, allow_nan=False)
        with self.runtime._cv:
            self.runtime._emit(event_type,self.runtime._jobs[self.job_id],data)

    def import_input(self, source, *, base_dir, suffixes, max_bytes, keep=False):
        """Copy an input into this job; absolute paths need no manual staging."""
        from .inputs import import_input
        return import_input(self,source,base_dir=base_dir,suffixes=suffixes,max_bytes=max_bytes,keep=keep)

    def _cleanup_inputs(self):
        removed=set()
        for path in self._temporary_inputs:
            try:
                if not path.resolve().is_relative_to((self.workspace/'inputs').resolve()):
                    raise OSError('Temporary input no longer resolves inside this job')
                path.unlink(missing_ok=True);removed.add(str(path.relative_to(self.workspace)))
            except OSError as exc:self.log('Temporary input cleanup failed: '+str(exc),level='Warning')
        if removed:
            try:
                receipt=self.path('inputs/imports.json')
                entries=json.loads(receipt.read_text('utf-8')) if receipt.exists() else []
                for item in entries:
                    if isinstance(item,dict) and item.get('snapshot') in removed:item['removed']=True
                receipt.write_text(json.dumps(entries,indent=2,ensure_ascii=False),'utf-8')
                self.log('Temporary input copies removed: '+str(len(removed)))
            except (OSError,ValueError,TypeError) as exc:self.log('Input cleanup receipt: '+str(exc),level='Warning')

    def observe_resources(self, usage, profile=None):
        from .schema import validate_document
        validate_document(usage, 'resources')
        self.runtime.store.put('observations', self.job_id, {'jobId':self.job_id, 'usage':usage, 'profile':profile or {}, 'timestamp':now()})


class Runtime:
    def __init__(self, descriptor, data_dir, *, capacity=None, system=None, event_limit=2000):
        self.descriptor = validate_manifest(descriptor)
        self.root = Path(data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        # Lifetime lock prevents two schedulers sharing a database/workspace root.
        self._ownership = RuntimeLock(self.root/'runtime.lock.sqlite3')
        self.store = Store(self.root/'state.sqlite3')
        previous = self.store.all('settings').get('identity')
        if previous and previous['toolId'] != self.descriptor['id']:
            self.store.close()
            self._ownership.close()
            raise CyToolError('InvalidState','Data directory belongs to another Tool')
        self.store.put('settings','identity',{'toolId':self.descriptor['id'],'protocolVersion':'1.0'})
        self.system = copy.deepcopy(system) if system else system_resources(self.root)
        budget = capacity or {'ramBytes':self.system['ramFreeBytes'], 'diskBytes':self.system['diskFreeBytes'],
                              'cpuThreads':self.system['cpuThreads'],
                              'vramBytes':{g['id']:g['vramFreeBytes'] for g in self.system['gpus']}}
        self.ledger = ResourceLedger(budget)
        self._cv = threading.Condition(threading.RLock())
        self._clients = self.store.all('clients')
        self._sessions = self.store.all('sessions')
        self._jobs = self.store.all('jobs')
        self._events = deque(maxlen=event_limit)
        self._sequence = 0
        self._handlers = {}
        self._estimators = {}
        self._tokens = {}
        self._threads = {}
        self._running = set()
        self._queue = []
        self._workers = {}
        self._closed = False
        self._started = False
        for job in self._jobs.values():
            if job['state'] not in TERMINAL:
                job.update(state='Failed', finishedAt=now(), error=CyToolError('Interrupted','Runtime stopped before job completion', recoverable=True).to_dict())
                self._save(job)
        for session in self._sessions.values():
            if session.get('temporary') and not session.get('cleanedAt'):
                session.update(closed=True,cleanupPending=True)
        self._emit('ToolStarted', data={})

    def register(self, operation_id, handler, *, estimate=None):
        with self._cv:
            if self._started:
                raise CyToolError('InvalidState','Register operations before starting runtime')
            self.operation(operation_id)
            if operation_id in self._handlers:
                raise CyToolError('InvalidState','Operation already registered')
            self._handlers[operation_id] = handler
            if estimate:
                self._estimators[operation_id] = estimate

    def start(self):
        with self._cv:
            if self._closed:
                raise CyToolError('InvalidState','Runtime closed')
            if self._started: return self
            missing = {o['id'] for o in self.descriptor['operations']} - self._handlers.keys()
            if missing: raise CyToolError('MissingImplementation',f'Missing handlers: {sorted(missing)}')
            self._started = True
            self._scheduler = threading.Thread(target=self._schedule, name='CyToolsScheduler', daemon=True)
            self._scheduler.start()
        return self

    def __enter__(self): return self.start()
    def __exit__(self, *args): self.close()

    def operation(self, operation_id):
        for operation in self.descriptor['operations']:
            if operation['id'] == operation_id: return copy.deepcopy(operation)
        raise CyToolError('UnknownOperation', f'Unknown operation: {operation_id}')

    def create_client(self, name='local', permissions=()):
        token, client_id = secrets.token_urlsafe(32), uid()
        record = {'clientId':client_id,'name':name,'permissions':list(permissions), 'tokenHash':hashlib.sha256(token.encode()).hexdigest()}
        with self._cv:
            self._clients[client_id] = record
            self.store.put('clients',client_id,record)
        return {'clientId':client_id,'token':token}

    def authenticate(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._cv:
            for record in self._clients.values():
                if secrets.compare_digest(digest, record['tokenHash']):
                    return Principal(record['clientId'], frozenset(record['permissions']))
        raise CyToolError('AuthenticationRequired','Invalid client credential')

    def create_session(self, principal, *, temporary=True, retention_seconds=3600):
        if type(temporary) is not bool or type(retention_seconds) not in (int,float) or not 1 <= retention_seconds <= 86400:
            raise CyToolError("InvalidParameters", "temporary must be boolean; retention must be 1..86400 seconds")
        record = {'sessionId':uid(),'clientId':principal.client_id,'createdAt':now(),'closed':False, 'temporary':temporary,
                  'retentionSeconds':retention_seconds,'expiresAt':time.time()+retention_seconds}
        with self._cv:
            self._sessions[record['sessionId']] = record
            self.store.put('sessions',record['sessionId'],record)
            self._emit('SessionCreated', data=record, client_id=principal.client_id)
        return copy.deepcopy(record)

    def _session(self, principal, session_id):
        session = self._sessions.get(session_id)
        if not session or session['clientId'] != principal.client_id or session['closed'] or session.get('cleanupPending'):
            raise CyToolError('AccessDenied','Session unavailable')
        return session

    def close_session(self, principal, session_id):
        return self.finish_task(principal, session_id)

    def finish_task(self, principal, session_id, *, cancel_running=False):
        from .task_files import sweep
        with self._cv:
            session = self._sessions.get(session_id)
            if not session or session['clientId'] != principal.client_id:
                raise CyToolError('AccessDenied','Session unavailable')
            if session.get('cleanedAt'): return copy.deepcopy(session)
            active = [j for j in self._jobs.values() if j['sessionId']==session_id and
                      (j['state'] not in TERMINAL or j['jobId'] in self._running)]
            if active and not cancel_running: raise CyToolError('Busy','Session still owns active workers')
            for job in active:
                self._tokens[job['jobId']].cancel()
                if job['jobId'] not in self._running:
                    self._finish(job,'Cancelled',error=CyToolError('Cancelled','Task finished'))
            session.update(closed=True,cleanupPending=True)
            self.store.put('sessions',session_id,session)
            sweep(self)
            self._cv.notify_all()
            return copy.deepcopy(session)

    def keep_task_alive(self, principal, session_id):
        with self._cv:
            session = self._session(principal,session_id)
            session['expiresAt']=time.time()+session.get('retentionSeconds',3600)
            self.store.put('sessions',session_id,session)
            return copy.deepcopy(session)

    def configure_inputs(self, root, *, max_bytes=8*1024**3, fields=None):
        self.input_root=Path(root).resolve()
        self.input_max_bytes=max_bytes
        self.input_fields=fields or {}
        for op in self.descriptor['operations']:
            for field in self.input_fields.get(op['id'],[]):
                spec=op['inputSchema']
                for part in field.split('.'):
                    spec=spec.get('items',{}) if part=='*' else spec.get('properties',{}).get(part,{})
                if spec:
                    spec['description']='Local file path, automatically imported by the Tool. Use ImportFile/cy_import_file for explicit imports and companion files. Task copies are deleted on FinishTask.'
                    spec['x-cy-task-input']=True
                    if 'maxLength' in spec: spec['maxLength']=max(spec['maxLength'],4096)

    def import_file(self, principal, session_id, source, *, companions=()):
        from .task_files import import_file
        return import_file(self,principal,session_id,source,companions)

    def export_job(self, principal, job_id, destination):
        from .task_files import export_job
        return export_job(self,principal,job_id,destination)

    def task(self, principal, **options):
        from .task_files import task
        return task(self,principal,**options)

    def _selection(self, operation, backend_id, model_id):
        backend, model = None, None
        supported = operation.get('supportedBackends', [])
        if supported and not backend_id:
            if len(supported) != 1:
                raise CyToolError('UnsupportedBackend','Choose an explicit backendId')
            backend_id = supported[0]
        if backend_id:
            if backend_id not in supported:
                raise CyToolError('UnsupportedBackend','Backend not supported by this operation')
            backend = next(b for b in self.descriptor['backends'] if b['id']==backend_id)
        if model_id:
            model = next((m for m in (backend or {}).get('models',[]) if m['id']==model_id),None)
            if not model: raise CyToolError('MissingModel','Model not declared in selected backend')
            if model.get('location','Local')!='Remote' and not model.get('installed',False):
                raise CyToolError('MissingModel','Model is not installed')
        return backend,model

    def estimate_resources(self, operation_id, parameters, backend_id='', model_id=''):
        operation = self.operation(operation_id)
        parameters = validate_parameters(parameters, operation['inputSchema'])
        backend, model = self._selection(operation,backend_id,model_id)
        estimate = {}
        for source in (backend,model,operation):
            if source:
                estimate.update(copy.deepcopy(source.get('resourceRequirements',{})))
        if operation_id in self._estimators:
            estimate.update(self._estimators[operation_id](parameters, backend, model))
        from .schema import validate_document
        validate_document(estimate,'resources')
        # Auto chooses one capable device; explicit device maps support multi-GPU.
        vram = estimate.get('vramBytes',{})
        if 'auto' in vram:
            if len(vram)!=1: raise CyToolError('InvalidParameters','auto cannot be mixed with explicit GPU IDs')
            available = self.ledger.snapshot()['available'].get('vramBytes',{})
            candidates = [d for d,size in self.ledger.capacity.get('vramBytes',{}).items() if size>=vram['auto']]
            if not candidates: raise CyToolError('InsufficientVRAM','No GPU fits the requested reservation')
            estimate['vramBytes'] = {max(candidates,key=lambda d:available.get(d,0)):vram['auto']}
        return estimate

    def can_run(self, operation_id, parameters, backend_id='', model_id=''):
        try:
            operation = self.operation(operation_id)
            validate_parameters(parameters,operation['inputSchema'])
            backend,model = self._selection(operation,backend_id,model_id)
            statuses = []
            for source in (self.descriptor,operation,backend,model):
                if source and (source is self.descriptor or 'platforms' in source):
                    statuses.append(platform_status(source.get('platforms',[]),self.system))
            if any(s not in ('Supported','Experimental') for s in statuses):
                raise CyToolError('UnsupportedPlatform','Platform support is unsupported or unknown')
            import shutil
            for dependency in self.descriptor.get('runtimeRequirements',[]) + (backend or {}).get('dependencies',[]):
                if dependency.get('required',True) and not (dependency.get('path') and Path(dependency['path']).is_file()) and not (dependency.get('executable') and shutil.which(dependency['executable'])):
                    raise CyToolError('MissingDependency',f"Missing dependency: {dependency['id']}")
            estimate = self.estimate_resources(operation_id,parameters,backend_id,model_id)
            cpu = estimate.get('cpu',{})
            if cpu.get('minimumThreads',0)>self.system.get('cpuThreads',0) or cpu.get('minimumCores',0)>(self.system.get('cpuCores') or 0):
                raise CyToolError('UnsupportedCPU','CPU core/thread requirement not met')
            if not set(cpu.get('instructions',[])) <= set(self.system.get('cpuInstructions',[])):
                raise CyToolError('UnsupportedCPU','Required CPU instructions are unavailable or unverified')
            gpu = estimate.get('gpu',{})
            if gpu.get('required') and not self.system.get('gpus'):
                raise CyToolError('UnsupportedGPU','Required GPU is unavailable or unverified')
            if gpu.get('vendors') and not any(g['vendor'] in gpu['vendors'] for g in self.system.get('gpus',[])):
                raise CyToolError('UnsupportedGPU','Required GPU vendor not detected')
            for requested in (gpu.get('computeBackends',[]),(model or {}).get('computeBackends',[])):
                if requested and not set(requested)&set(self.system['computeBackends']):
                    raise CyToolError('UnsupportedGPU','Requested compute backend is not detected')
            shortage = self.ledger.shortage(self.ledger.normalize(estimate), self.ledger.capacity)
            if shortage: raise CyToolError(shortage,'Requested resources exceed the configured capacity')
            waiting = self.ledger.shortage(self.ledger.normalize(estimate), self.ledger.snapshot()['available']) is not None
            return {'status':'CanRun','canRun':True,'waitingForResources':waiting,'estimate':estimate,
                    'platformStatus':'Experimental' if 'Experimental' in statuses else 'Supported', 'suggestions':[]}
        except CyToolError as exc:
            return {'status':exc.code,'canRun':False,'error':exc.to_dict(),'suggestions':[]}

    def submit(self, principal, session_id, operation_id, parameters, *, backend_id='', model_id='', priority='Normal', queue_timeout=None, execution_timeout=None):
        if priority not in PRIORITIES: raise CyToolError('InvalidParameters','Unknown priority')
        for value in (queue_timeout,execution_timeout):
            if value is not None and (isinstance(value,bool) or not isinstance(value,(float,int)) or not 0 < value < float('inf')):
                raise CyToolError('InvalidParameters','Timeouts must be finite positive seconds')
        operation = self.operation(operation_id)
        parameters = validate_parameters(parameters, operation['inputSchema'])
        if not set(operation.get('permissions',[])) <= principal.permissions:
            raise CyToolError('AccessDenied','Client lacks operation permissions')
        with self._cv:
            if not self._started or self._closed: raise CyToolError('InvalidState','Runtime is not accepting jobs')
            self.keep_task_alive(principal,session_id)
            feasibility = self.can_run(operation_id,parameters,backend_id,model_id)
            if not feasibility['canRun']:
                raise CyToolError(feasibility['status'],feasibility['error']['message'])
            backend,_ = self._selection(operation,backend_id,model_id)
            job_id = uid()
            workspace = self.root/'Workspaces'/principal.client_id/job_id
            job = {'jobId':job_id,'clientId':principal.client_id,'sessionId':session_id,'workspaceId':uid(),
                   'workspace':str(workspace),'toolId':self.descriptor['id'],'operationId':operation_id,
                   'backendId':(backend or {}).get('id',''),'modelId':model_id,'parameters':parameters,
                   'priority':priority,'createdAt':now(),'startedAt':None,'finishedAt':None,'state':'Created',
                   'progress':{'percent':0},'outputs':None,'error':None,'visibility':'Owner','sharedWith':[],
                   'resourceEstimate':feasibility['estimate'],'queueTimeout':queue_timeout,'executionTimeout':execution_timeout}
            # Lease in-runtime producer workspaces until this consumer stops.
            def paths(value):
                if isinstance(value,dict):
                    for item in value.values(): yield from paths(item)
                elif isinstance(value,list):
                    for item in value: yield from paths(item)
                elif isinstance(value,str):
                    try:
                        path=Path(value)
                        if path.is_absolute(): yield path.resolve()
                    except (ValueError,OSError): pass
            dependencies=[]
            for source in paths(parameters):
                for producer in self._jobs.values():
                    if source.is_relative_to(Path(producer['workspace'])):
                        if not self._allowed(principal,producer) or producer.get('artifactsDeleted'):
                            raise CyToolError('AccessDenied','Input job artifacts unavailable')
                        dependencies.append(producer['jobId'])
            workspace.mkdir(parents=True)
            job['artifactDependencies']=list(set(dependencies))
            job['artifactsDeleted']=False
            self._jobs[job_id] = job
            self._tokens[job_id] = CancellationToken()
            self._emit('JobCreated',job)
            self._state(job,'Queued')
            self._queue.append((time.monotonic(), job_id))
            self._cv.notify_all()
            return copy.deepcopy(job)

    def _save(self, job): self.store.put('jobs',job['jobId'],job)

    def _emit(self, event_type, job=None, data=None, client_id=None):
        self._sequence += 1
        event = {'sequence':self._sequence,'type':event_type,'timestamp':now(),'toolId':self.descriptor['id'],'data':copy.deepcopy(data or {})}
        if job: event.update({key:job[key] for key in ('clientId','sessionId','jobId')})
        elif client_id: event['clientId'] = client_id
        self._events.append(event)

    def _state(self, job, state):
        job['state'] = state
        self._save(job)
        self._emit({'Running':'JobStarted'}.get(state,'Job'+state),job,{'state':state})

    def _allowed(self, principal, job, write=False):
        return job['clientId']==principal.client_id or (not write and (job['visibility']=='Global' or (job['visibility']=='Shared' and principal.client_id in job['sharedWith'])))

    def get_job(self, principal, job_id):
        with self._cv:
            job = self._jobs.get(job_id)
            if not job or not self._allowed(principal,job): raise CyToolError('AccessDenied','Job unavailable')
            return copy.deepcopy(job)

    def list_jobs(self, principal):
        with self._cv:
            return [copy.deepcopy(j) for j in self._jobs.values() if self._allowed(principal,j)]

    def share_job(self, principal, job_id, visibility='Owner', shared_with=None):
        with self._cv:
            job = self._jobs.get(job_id)
            if not job or not self._allowed(principal,job,True): raise CyToolError('AccessDenied','Only owner can share')
            if visibility not in ('Owner','Shared','Global'): raise CyToolError('InvalidParameters','Invalid visibility')
            job.update(visibility=visibility,sharedWith=list(shared_with or []))
            self._save(job)
            return copy.deepcopy(job)

    def cancel(self, principal, job_id):
        with self._cv:
            job = self._jobs.get(job_id)
            if not job or not self._allowed(principal,job,True): raise CyToolError('AccessDenied','Only owner can cancel')
            if job['state'] in TERMINAL: return copy.deepcopy(job)
            if not self.operation(job['operationId']).get('canCancel',False): raise CyToolError('Unsupported','Operation cannot cancel')
            self._tokens[job_id].cancel()
            if job_id not in self._running:
                self._finish(job,'Cancelled',error=CyToolError('Cancelled','Cancelled in queue'))
            else: self._state(job,'Cancelling')
            self._cv.notify_all()
            return copy.deepcopy(job)

    def events(self, principal, after=0):
        with self._cv:
            visible = [copy.deepcopy(e) for e in self._events if e['sequence']>after and
                       (('jobId' in e and self._allowed(principal,self._jobs[e['jobId']])) or
                        ('jobId' not in e and ('clientId' not in e or e['clientId']==principal.client_id)))]
            return {'events':visible,'cursor':self._sequence,'gap':bool(self._events and after and after<self._events[0]['sequence']-1)}

    def _can_dispatch(self, job):
        policy = self.descriptor['concurrency']['policy']
        maximum = self.descriptor['concurrency'].get('maxWorkers',1)
        if len(self._running)>=maximum: return False
        if policy in ('Exclusive','Sequential') and self._running: return False
        peers = [self._jobs[j] for j in self._running if self._jobs[j]['backendId']==job['backendId']]
        if policy=='SharedModelSequential' and peers: return False
        if job['backendId'] and peers:
            backend = next(b for b in self.descriptor['backends'] if b['id']==job['backendId'])
            if not backend.get('threadSafe',False) or not backend.get('concurrentInference',False): return False
            if len(peers)>=backend.get('maxConcurrentInference',1): return False
        return True

    def _schedule(self):
        while True:
            with self._cv:
                if self._closed and not self._running: return
                if time.monotonic() >= getattr(self,'_next_cleanup',0):
                    from .task_files import sweep
                    sweep(self)
                    self._next_cleanup=time.monotonic()+1
                for created, job_id in sorted(self._queue, key=lambda item:(PRIORITIES[self._jobs[item[1]]['priority']],item[0])):
                    job = self._jobs[job_id]
                    if job['state'] in TERMINAL: continue
                    if job['queueTimeout'] is not None and time.monotonic()-created >= job['queueTimeout']:
                        self._finish(job,'Failed',error=CyToolError('Timeout','Queue deadline exceeded'))
                        continue
                    if not self._can_dispatch(job): continue
                    if not self.ledger.reserve(job_id,job['resourceEstimate']):
                        if job['state']!='WaitingForResources': self._state(job,'WaitingForResources')
                        continue
                    self._emit('ResourceReservationCreated',job,job['resourceEstimate'])
                    self._running.add(job_id)
                    self._state(job,'Preparing')
                    thread = threading.Thread(target=self._execute,args=(job_id,),name='CyToolJob-'+job_id,daemon=True)
                    self._threads[job_id] = thread
                    thread.start()
                self._queue = [(t,j) for t,j in self._queue if self._jobs[j]['state'] not in TERMINAL and j not in self._running]
                for job_id in list(self._running):
                    token = self._tokens[job_id]
                    if token.deadline and time.monotonic()>=token.deadline and not token.event.is_set():
                        token.cancel('Timeout')
                        self._state(self._jobs[job_id],'Cancelling')
                self._cv.wait(.025)

    def _execute(self, job_id):
        with self._cv:
            job = self._jobs[job_id]
            token = self._tokens[job_id]
            if job['executionTimeout']: token.deadline = time.monotonic()+job['executionTimeout']
            job['startedAt'] = now()
            self._state(job,'Running')
        try:
            token.check()
            context=JobContext(self,job_id,token)
            try:
                from .task_files import prepare_inputs
                parameters=prepare_inputs(self,job,copy.deepcopy(job['parameters']))
                token.check()
                outputs = self._handlers[job['operationId']](context,parameters)
            finally: context._cleanup_inputs()
            token.check()
            try: outputs = validate_parameters(outputs,self.operation(job['operationId'])['outputSchema'],defaults=False)
            except CyToolError as exc: raise CyToolError('InvalidOutput',exc.message) from exc
            with self._cv:
                token.check()
                self._finish(job,'Completed',outputs=outputs)
        except CyToolError as exc:
            with self._cv: self._finish(job,'Cancelled' if exc.code=='Cancelled' else 'Failed',error=exc)
        except BaseException as exc:
            with self._cv: self._finish(job,'Failed',error=CyToolError('InternalError',str(exc)))
        finally:
            with self._cv:
                self.ledger.release(job_id)
                self._emit('ResourceReservationReleased',job)
                self._running.discard(job_id)
                session=self._sessions[job['sessionId']]
                session['expiresAt']=time.time()+session.get('retentionSeconds',3600)
                self.store.put('sessions',session['sessionId'],session)
                from .task_files import sweep
                sweep(self)
                self._cv.notify_all()

    def _finish(self, job, state, outputs=None, error=None):
        job.update(finishedAt=now(), outputs=outputs, error=error.to_dict() if error else None)
        if state=='Completed': job['progress']['percent']=100
        self._state(job,state)

    def wait(self, principal, job_id, timeout=30):
        deadline = time.monotonic()+timeout
        with self._cv:
            while True:
                job = self.get_job(principal,job_id)
                if job['state'] in TERMINAL and job_id not in self._running: return job
                remaining = deadline-time.monotonic()
                if remaining<=0: raise CyToolError('Timeout','Waiting deadline exceeded; job may still be active')
                self._cv.wait(min(remaining,.05))

    def status(self):
        with self._cv:
            return {'toolId':self.descriptor['id'],'activeClients':len({s['clientId'] for s in self._sessions.values() if not s['closed']}),
                    'activeSessions':sum(not s['closed'] for s in self._sessions.values()), 'queuedJobs':len(self._queue),
                    'runningJobs':len(self._running),'runningWorkers':sum(w.state!='Stopped' for w in self._workers.values()),
                    'resources':self.ledger.snapshot(),'acceptingJobs':self._started and not self._closed}

    def register_worker(self, worker_id, worker):
        with self._cv:
            if worker_id in self._workers: raise CyToolError('InvalidState','Worker already registered')
            self._workers[worker_id]=worker

    def reserve_worker(self, worker_id, requirements):
        with self._cv:
            if worker_id not in self._workers: raise CyToolError('InvalidState','Register worker before reserving resources')
            return self.ledger.reserve('worker:'+worker_id,requirements)

    def release_resources(self, principal, level):
        if 'manageResources' not in principal.permissions: raise CyToolError('AccessDenied','manageResources permission required')
        if level not in ('Temporary','Job','Model','Worker','All'): raise CyToolError('InvalidParameters','Unknown release level')
        with self._cv:
            if self._running: raise CyToolError('Busy','Cannot release resources while jobs are executing')
            for worker_id,worker in self._workers.items():
                worker.release(level)
                if level in ('Worker','All'):
                    self.ledger.release('worker:'+worker_id)
            return {'released':level,'resources':self.ledger.snapshot()}

    def close(self, timeout=10):
        with self._cv:
            if self._closed and not self._started: return
            self._closed = True
            for job_id,token in self._tokens.items():
                if self._jobs[job_id]['state'] not in TERMINAL:
                    token.cancel()
                    if job_id not in self._running: self._finish(self._jobs[job_id],'Cancelled',error=CyToolError('Cancelled','Runtime stopping'))
            self._cv.notify_all()
        if self._started:
            self._scheduler.join(timeout)
            if self._scheduler.is_alive():
                raise CyToolError('Busy','Handler ignored cancellation; reservations retained until it exits')
        for worker in self._workers.values(): worker.release('All')
        with self._cv:
            for session in self._sessions.values():
                if session.get('temporary') or session.get('inputDirectory'): session['cleanupPending']=True
            from .task_files import sweep
            sweep(self)
        self._emit('ToolStopping')
        self.store.close()
        self._ownership.close()
        self._started = False
