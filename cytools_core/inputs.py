"""Bounded local input snapshots owned by the authenticated job."""
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
from .errors import CyToolError

def import_input(context, source, *, base_dir, suffixes, max_bytes, keep=False):
    from .runtime import Principal
    if not isinstance(source,str) or not source.strip():
        raise CyToolError('MissingInput','Provide a local file path')
    if '://' in source or source.startswith(('\\\\.\\','\\\\?\\')):
        raise CyToolError('InvalidInput','Expected a regular local file path')
    path=Path(source).expanduser();base=Path(base_dir).resolve()
    if not path.is_absolute():
        path=(base/path).resolve()
        if not path.is_relative_to(base):raise CyToolError('AccessDenied','Relative input must remain inside the input directory; use an absolute path for an external file')
    else:path=path.resolve()
    allowed={s.lower() for s in suffixes}
    if not allowed or path.suffix.lower() not in allowed:
        raise CyToolError('InvalidInput','Unsupported input file extension')
    if not isinstance(max_bytes,int) or isinstance(max_bytes,bool) or max_bytes<=0:raise ValueError('A positive input size limit is required')
    runtime=context.runtime
    with runtime._cv:
        actor=Principal(runtime._jobs[context.job_id]['clientId'])
        if path.is_relative_to((runtime.root/'Workspaces').resolve()):
            owner=next((job for job in runtime._jobs.values() if path.is_relative_to(Path(job['workspace']).resolve())),None)
            if owner is None or not runtime._allowed(actor,owner):raise CyToolError('AccessDenied','Input job is unavailable to this client')
    context.cancellation.check()
    destination=context.path('inputs/'+uuid.uuid4().hex+path.suffix.lower())
    partial=destination.with_suffix(destination.suffix+'.partial')
    if not isinstance(keep,bool):raise ValueError('keep must be a boolean')
    if not keep:context._temporary_inputs.append(destination)
    try:
        if not path.is_file():raise CyToolError('MissingInput','Input file is missing or is not a regular file',recoverable=True)
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NONBLOCK',0))
        digest=hashlib.sha256();total=0
        with os.fdopen(descriptor,'rb') as reader:
            before=os.fstat(reader.fileno())
            if not stat.S_ISREG(before.st_mode):raise CyToolError('InvalidInput','Input must be a regular file')
            if before.st_size>max_bytes:raise CyToolError('InputTooLarge',f'Input exceeds {max_bytes} bytes')
            with partial.open('xb') as writer:
                while True:
                    context.cancellation.check();chunk=reader.read(1024*1024)
                    if not chunk:break
                    total+=len(chunk)
                    if total>max_bytes:raise CyToolError('InputTooLarge',f'Input exceeds {max_bytes} bytes')
                    writer.write(chunk);digest.update(chunk)
            after=os.fstat(reader.fileno())
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise CyToolError('InputChanged','Input changed while being copied; retry with a stable file',recoverable=True)
        context.cancellation.check();partial.replace(destination)
        record={'source':str(path),'snapshot':str(destination.relative_to(context.workspace)), 'sizeBytes':total,'sha256':digest.hexdigest(),'temporary':not keep,'removed':False}
        with runtime._cv:
            receipt=context.path('inputs/imports.json')
            entries=json.loads(receipt.read_text('utf-8')) if receipt.exists() else []
            entries.append(record);receipt.write_text(json.dumps(entries,indent=2,ensure_ascii=False),'utf-8')
        context.log('Input copied to private job workspace: '+destination.name)
        return destination
    except OSError as exc:
        raise CyToolError('InputUnavailable','The Tool process cannot read the source or write its private input copy',details={'reason':str(exc)},recoverable=True) from exc
    finally:
        partial.unlink(missing_ok=True)
