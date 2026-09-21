"""Owned one-shot process workers. Heavy runtimes can subclass the release contract."""
import json
import subprocess
import threading
import time
import psutil
from .errors import CyToolError


class ProcessWorker:
    def __init__(self, command, *, cwd=None, startup_timeout=10, idle_timeout=60):
        if not command or not all(isinstance(arg,str) for arg in command):
            raise ValueError('command must be a nonempty argv list')
        self.command, self.cwd = list(command), cwd
        self.startup_timeout, self.idle_timeout = startup_timeout, idle_timeout
        self.state, self.process, self.last_response = 'Stopped', None, None
        self._lock = threading.RLock()

    def run(self, context, parameters):
        with self._lock:
            if self.state not in ('Stopped','Failed'): raise CyToolError('Busy','Worker already running')
            context.cancellation.check()
            self.state = 'Starting'
            try:
                self.process = subprocess.Popen(self.command, cwd=self.cwd or context.workspace, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', shell=False)
            except OSError as exc:
                self.state = 'Failed'
                raise CyToolError('MissingRuntime',str(exc)) from exc
            self.state = 'Busy'
            self.last_response = time.monotonic()
        try:
            if hasattr(context,'runtime'):
                with context.runtime._cv:
                    job=context.runtime._jobs[context.job_id]
                    try:
                        process=psutil.Process(self.process.pid)
                        job.setdefault('artifactProcesses',[]).append({'pid':process.pid,'created':process.create_time()})
                        context.runtime._save(job)
                    except psutil.NoSuchProcess: pass
            payload = json.dumps({'protocolVersion':'1.0','parameters':parameters,'workspace':str(context.workspace)},allow_nan=False)
            first = True
            while True:
                context.cancellation.check()
                if time.monotonic()-self.last_response > self.idle_timeout:
                    raise CyToolError('Timeout','Worker response deadline exceeded')
                try:
                    stdout,stderr = self.process.communicate(payload if first else None,timeout=.05)
                    break
                except subprocess.TimeoutExpired:
                    first = False
            self.last_response = time.monotonic()
            if stderr:
                from .diagnostics import redact
                diagnostics=redact(stderr[-2*1024*1024:])
                context.path('logs/worker-stderr.log').write_text(diagnostics,encoding='utf-8')
                context.log(diagnostics[-16000:],level='Warning' if self.process.returncode else 'Info')
            if self.process.returncode:
                raise CyToolError('WorkerCrashed',f'Worker exited with code {self.process.returncode}',details=stderr[-2000:])
            try: result = json.loads(stdout)
            except (ValueError,TypeError) as exc: raise CyToolError('ProtocolError','Worker output must be one JSON value') from exc
            context.cancellation.check()
            return result
        except Exception:
            self.state = 'Failed'
            raise
        finally:
            failed = self.state == 'Failed'
            self.stop()
            if failed: self.state='Failed'

    def stop(self):
        with self._lock:
            process = self.process
            if process:
                self.state = 'Stopping'
                try:
                    parent = psutil.Process(process.pid)
                    descendants = parent.children(recursive=True)
                    for child in descendants:
                        try: child.terminate()
                        except psutil.NoSuchProcess: pass
                    if process.poll() is None: process.terminate()
                    _,alive = psutil.wait_procs(descendants,timeout=1)
                    for child in alive:
                        try: child.kill()
                        except psutil.NoSuchProcess: pass
                except psutil.NoSuchProcess: pass
                try: process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                for stream in (process.stdin,process.stdout,process.stderr):
                    if stream: stream.close()
                self.process = None
            self.state = 'Stopped'

    def release(self, level):
        if level in ('Worker','All'): self.stop()
        elif level not in ('Temporary','Job','Model'): raise CyToolError('InvalidParameters','Unknown release level')
        # One-shot worker owns no model/cache between calls.

    def health(self):
        with self._lock:
            return {'state':self.state,'pid':self.process.pid if self.process else None,
                    'alive':bool(self.process and self.process.poll() is None),'lastResponseMonotonic':self.last_response,
                    'heartbeatSupported':False}
