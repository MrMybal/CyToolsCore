"""Task-owned artifact lifetime; no graphics/model imports."""
import psutil
import json
from urllib.parse import unquote
import hashlib
import os
import stat
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .errors import CyToolError


def workspace(runtime, job):
    base = runtime.root / 'Workspaces'
    expected = base / job['clientId'] / job['jobId']
    if (base.resolve() != base or expected.resolve() != expected or
            Path(job['workspace']).resolve() != expected or not expected.is_relative_to(base)):
        raise CyToolError('AccessDenied', 'Task workspace was redirected; cleanup refused')
    return expected


def purge(runtime, session):
    jobs = [j for j in runtime._jobs.values() if j['sessionId'] == session['sessionId']]
    if any(j['jobId'] in runtime._running or j['state'] not in ('Completed','Cancelled','Failed') for j in jobs):
        return False
    for job in jobs:
        for recorded in job.get('artifactProcesses',[]):
            try:
                process=psutil.Process(recorded['pid'])
                if process.create_time()==recorded['created'] and process.is_running(): return False
            except psutil.NoSuchProcess: pass
            except psutil.AccessDenied: return False
    ids = {j['jobId'] for j in jobs}
    if any(ids.intersection(j.get('artifactDependencies', [])) and
           (j['jobId'] in runtime._running or j['state'] not in ('Completed','Cancelled','Failed'))
           for j in runtime._jobs.values()):
        return False
    purge_inputs(session)
    for job in jobs:
        if not session.get("temporary"): continue
        if job.get('artifactsDeleted'): continue
        target = workspace(runtime, job)
        if target.exists(): shutil.rmtree(target)
        job.update(artifactsDeleted=True, outputs=None, parameters={})
        runtime._save(job)
        try: target.parent.rmdir()
        except OSError: pass
    session.update(closed=True, cleanupPending=False, cleanedAt=time.time())
    runtime.store.put('sessions', session['sessionId'], session)
    return True


def sweep(runtime):
    for session in runtime._sessions.values():
        if (not session.get('temporary') and not session.get('cleanupPending')) or session.get('cleanedAt'): continue
        jobs = [j for j in runtime._jobs.values() if j['sessionId'] == session['sessionId']]
        active = any(j['jobId'] in runtime._running or j['state'] not in ('Completed','Cancelled','Failed') for j in jobs)
        if not session.get('cleanupPending') and (active or time.time() < session.get('expiresAt', float('inf'))): continue
        session['cleanupPending'] = True
        try:
            purge(runtime, session)
            session.pop('cleanupError', None)
        except (OSError, CyToolError) as exc:
            session['cleanupError'] = str(exc)
        runtime.store.put('sessions', session['sessionId'], session)


def export_job(runtime, principal, job_id, destination):
    with runtime._cv:
        job = runtime.get_job(principal, job_id)
        if job['state'] not in ('Completed','Failed','Cancelled') or job_id in runtime._running:
            raise CyToolError('Busy', 'Wait for the worker to stop before exporting')
        if job.get('artifactsDeleted'): raise CyToolError('MissingInput', 'Task artifacts have been deleted')
        source = workspace(runtime, job)
        destination = Path(destination).expanduser()
        if not destination.is_absolute(): raise CyToolError('InvalidParameters', 'Export destination must be absolute')
        destination = destination.resolve()
        if destination.is_relative_to(runtime.root): raise CyToolError('AccessDenied', 'Export outside the runtime data directory')
        target = destination / ('cytools-' + job_id + '-' + uuid.uuid4().hex[:8])
        for item in source.rglob('*'):
            if item.is_symlink() or getattr(item, 'is_junction', lambda: False)() or not item.resolve().is_relative_to(source):
                raise CyToolError('AccessDenied', 'Export bundle contains a redirected path')
        try: shutil.copytree(source, target)
        except OSError as exc: raise CyToolError('ExportFailed', str(exc)) from exc
        def rewrite(value):
            if isinstance(value, dict): return {k:rewrite(v) for k,v in value.items()}
            if isinstance(value, list): return [rewrite(v) for v in value]
            if isinstance(value, str):
                try:
                    path = Path(value)
                    if path.is_absolute() and path.is_relative_to(source): return str(target / path.relative_to(source))
                except (ValueError, OSError): pass
            return value
        return {'jobId':job_id, 'directory':str(target), 'outputs':rewrite(job['outputs'])}


@contextmanager
def task(runtime, principal, **options):
    session = runtime.create_session(principal, **options)
    try: yield session['sessionId']
    finally: runtime.finish_task(principal, session['sessionId'], cancel_running=True)


def import_file(runtime, principal, session_id, source, companions=()):
    """Import into the Tool's accepted input root, under a task-owned directory."""
    with runtime._cv:
        session=runtime._session(principal,session_id)
        root=getattr(runtime,'input_root',None)
        if root is None: raise CyToolError('Unsupported','Tool must configure its input root')
        source=Path(source).expanduser()
        if not source.is_absolute(): raise CyToolError('InvalidInput','Provide an absolute local source path')
        source=source.resolve()
        if not source.is_file(): raise CyToolError('MissingInput','Source file unavailable to the Tool process')
        for job in runtime._jobs.values():
            if source.is_relative_to(Path(job['workspace'])) and not runtime._allowed(principal,job):
                raise CyToolError('AccessDenied','Source job unavailable')
        for owner in runtime._sessions.values():
            if owner.get('inputDirectory') and source.is_relative_to(Path(owner['inputDirectory'])) and owner['clientId']!=principal.client_id:
                raise CyToolError('AccessDenied','Source task belongs to another client')
        namespace=hashlib.sha256(str(runtime.root).encode()).hexdigest()[:24]
        base=root/'.cytools-tasks'/namespace
        directory=base/session_id
        if base.resolve()!=base or directory.resolve()!=directory:
            raise CyToolError('AccessDenied','Input staging directory was redirected')
        session['inputDirectory']=str(directory)
        session['inputBase']=str(base)
        runtime.store.put('sessions',session_id,session)
        bundle=directory/uuid.uuid4().hex
        files=[(source,Path(source.name))]
        for name in dict.fromkeys([*mesh_companions(source), *companions]):
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts: raise CyToolError('InvalidInput','Companions must be relative to the source directory')
            path=(source.parent/relative).resolve()
            if not path.is_relative_to(source.parent): raise CyToolError('AccessDenied','Companion outside source directory')
            files.append((path,relative))
        total=0; records=[]
        try:
            for path,relative in files:
                destination=bundle/relative
                destination.parent.mkdir(parents=True,exist_ok=True)
                digest=hashlib.sha256()
                with path.open('rb') as reader, destination.open('xb') as writer:
                    before=os.fstat(reader.fileno())
                    if not stat.S_ISREG(before.st_mode): raise CyToolError('InvalidInput','Only regular files can be imported')
                    while True:
                        chunk=reader.read(1024*1024)
                        if not chunk: break
                        total+=len(chunk)
                        if total>runtime.input_max_bytes: raise CyToolError('InputTooLarge','Input bundle exceeds configured size limit')
                        writer.write(chunk);digest.update(chunk)
                    after=os.fstat(reader.fileno())
                    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise CyToolError('InputChanged','Source changed during import')
                records.append({'path':str(destination),'sha256':digest.hexdigest(),'sizeBytes':before.st_size})
        except BaseException:
            if bundle.resolve().is_relative_to(directory) and bundle.exists(): shutil.rmtree(bundle)
            raise
        runtime.keep_task_alive(principal,session_id)
        return {'sessionId':session_id,'path':str(bundle/source.name),
                'relativePath':str((bundle/source.name).relative_to(root)),'files':records,'temporary':True}


def purge_inputs(session):
    if not session.get('inputDirectory'): return
    base=Path(session['inputBase']);directory=Path(session['inputDirectory'])
    if directory!=base/session['sessionId'] or base.resolve()!=base or directory.resolve()!=directory:
        raise CyToolError('AccessDenied','Input staging directory was redirected; cleanup refused')
    if directory.exists(): shutil.rmtree(directory)
    for empty in (base,base.parent):
        try: empty.rmdir()
        except OSError: pass


def prepare_inputs(runtime, job, parameters):
    from .runtime import Principal
    fields=getattr(runtime,'input_fields',{}).get(job['operationId'],[])
    def visit(value, parts):
        if not parts:
            if not isinstance(value,str) or not value: return value
            path=Path(value).expanduser()
            if not path.is_absolute():
                path=(runtime.input_root/path).resolve()
                if not path.is_relative_to(runtime.input_root): raise CyToolError('AccessDenied','Relative input escapes its root; use an absolute external path')
            path=path.resolve()
            # Already staged by this task: do not duplicate a multi-file bundle.
            session=runtime._sessions[job['sessionId']]
            if session.get('inputDirectory') and path.is_relative_to(Path(session['inputDirectory'])): return str(path)
            return import_file(runtime,Principal(job['clientId']),job['sessionId'],str(path))['path']
        if parts[0]=='*' and isinstance(value,list): return [visit(item,parts[1:]) for item in value]
        if isinstance(value,dict) and parts[0] in value: value[parts[0]]=visit(value[parts[0]],parts[1:])
        return value
    for field in fields: parameters=visit(parameters,field.split('.'))
    return parameters


def mesh_companions(source):
    """Read local mesh references only; never fetch URLs or traverse parent folders."""
    names=[]
    if source.suffix.lower()=='.gltf':
        if source.stat().st_size>16*1024**2: raise CyToolError('InputTooLarge','GLTF JSON exceeds 16 MiB; use GLB')
        try: document=json.loads(source.read_text('utf-8-sig'))
        except (ValueError,UnicodeError): return names
        for section in ('buffers','images'):
            for item in document.get(section,[]):
                uri=item.get('uri','')
                if uri and not uri.startswith('data:'): names.append(unquote(uri))
    elif source.suffix.lower()=='.obj':
        with source.open(encoding='utf-8',errors='replace') as stream:
            for line in stream:
                if line.lstrip().lower().startswith('mtllib '): names.extend(line.strip().split()[1:])
        for name in list(names):
            path=(source.parent/name).resolve()
            if not path.is_relative_to(source.parent): raise CyToolError('AccessDenied','Material reference outside mesh folder')
            if not path.is_file(): raise CyToolError('MissingInput','Missing mesh companion: '+name)
            with path.open(encoding='utf-8',errors='replace') as stream:
                for line in stream:
                    tokens=line.strip().split()
                    if tokens and (tokens[0].lower().startswith('map_') or tokens[0].lower() in ('bump','disp','decal','norm')):
                        names.append(str((Path(name).parent/tokens[-1])))
    if len(names)>1000: raise CyToolError('InputTooLarge','Too many mesh companions')
    for name in names:
        relative=Path(name)
        if '://' in name or relative.is_absolute() or '..' in relative.parts:
            raise CyToolError('AccessDenied','Only relative local mesh companions are supported')
    return list(dict.fromkeys(names))
