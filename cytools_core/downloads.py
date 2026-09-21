"""Resumable HTTPS files with persistent validators and SHA256 verification."""
import hashlib
import http.client
import json
import os
import re
import threading
import shutil
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
from .errors import CyToolError


class DownloadManager:
    def __init__(self, root, *, timeout=30, allow_test_http=False, use_shared_cache=True):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.timeout, self.allow_test_http = timeout, allow_test_http
        self._lock = threading.Lock()
        self.shared_cache = os.environ.get('CYTOOLS_DOWNLOAD_CACHE','') if use_shared_cache else ''

    def _path(self, name):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,180}',name) or name.endswith('.'):
            raise CyToolError('InvalidParameters','Download name must be a safe basename')
        path = (self.root/name).resolve()
        if not path.is_relative_to(self.root): raise CyToolError('AccessDenied','Path outside download root')
        return path

    def _url(self, url):
        parsed = urlparse(url)
        if parsed.username or parsed.password: raise CyToolError('InvalidParameters','Credentials in URLs are not permitted')
        if parsed.scheme!='https' and not (self.allow_test_http and parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost')):
            raise CyToolError('InvalidParameters','HTTPS required')

    def verify(self, name, *, sha256=None, size=None):
        path = self._path(name)
        if not path.is_file(): return False
        if size is not None and path.stat().st_size!=size: return False
        if sha256:
            with path.open('rb') as stream: digest = hashlib.file_digest(stream,'sha256').hexdigest()
            if digest.lower()!=sha256.lower(): return False
        return True

    def download(self, name, url, *, sha256=None, size=None, headers=None, pause=None, cancellation=None, progress=None,
                 license_accepted=True, revision=None):
        self._url(url)
        if not license_accepted: raise CyToolError('LicenseAcceptanceRequired','Accept the model license before downloading')
        target = self._path(name)
        if self.shared_cache and sha256:
            if not re.fullmatch('[a-fA-F0-9]{64}',sha256):
                raise CyToolError('InvalidParameters','Invalid SHA256')
            from .storage import RuntimeLock
            from .shared_installation import write_json
            folder = Path(self.shared_cache).resolve()/sha256.lower()
            folder.mkdir(parents=True,exist_ok=True)
            lock = RuntimeLock(folder/'download.lock')
            try:
                cache = DownloadManager(folder,timeout=self.timeout,allow_test_http=self.allow_test_http,use_shared_cache=False)
                # A verified object is reusable across URLs, provided access is not gated.
                # Authorization-bearing requests retain source-specific checks below.
                if not headers and cache.verify('artifact',sha256=sha256,size=size):
                    result = {'state':'Completed','path':str(folder/'artifact'),'cached':True}
                else:
                    result = cache.download('artifact',url,sha256=sha256,size=size,headers=headers,
                        pause=pause,cancellation=cancellation,progress=progress,revision=revision)
                if result['state']!='Completed': return result
                if cancellation: cancellation.check()
                if not self.verify(name,sha256=sha256,size=size):
                    temporary = target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
                    try:
                        shutil.copyfile(folder/'artifact',temporary)
                        os.replace(temporary,target)
                    finally: temporary.unlink(missing_ok=True)
                write_json(self._path(name+'.installed.json'),{'url':url,'sha256':sha256,'size':size,
                    'revision':revision,'actualSha256':sha256.lower(),'actualSize':target.stat().st_size})
                return {**result,'path':str(target),'sharedCache':str(folder/'artifact')}
            finally: lock.close()
        partial = self._path(name+'.part')
        metadata = self._path(name+'.download.json')
        installed = self._path(name+'.installed.json')
        with self._lock:
            info = {'url':url,'sha256':sha256,'size':size,'revision':revision}
            previous = json.loads(installed.read_text('utf-8')) if installed.exists() else {}
            if target.exists() and all(previous.get(k)==v for k,v in info.items()) and previous.get('actualSha256') and self.verify(name,sha256=sha256 or previous['actualSha256'],size=size):
                return {'state':'Completed','path':str(target),'cached':True}
            old = json.loads(metadata.read_text('utf-8')) if metadata.exists() else {}
            compatible = all(old.get(key)==value for key,value in info.items())
            def finalize():
                if not self.verify(name+'.part',sha256=sha256,size=size):
                    partial.unlink(missing_ok=True)
                    raise CyToolError('IntegrityFailure','Downloaded size or SHA256 does not match')
                with partial.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
                info['actualSha256']=digest
                info['actualSize']=partial.stat().st_size
                os.replace(partial,target)
                temp=installed.with_suffix('.tmp')
                temp.write_text(json.dumps(info),encoding='utf-8')
                os.replace(temp,installed)
                metadata.unlink(missing_ok=True)
                return {'state':'Completed','path':str(target),'bytes':info['actualSize'],'sha256Verified':bool(sha256)}
            if compatible and sha256 and partial.exists() and self.verify(name+'.part',sha256=sha256,size=size):
                return finalize()
            offset = partial.stat().st_size if partial.exists() and compatible else 0
            # Resumption without a server validator is safe only with an expected hash.
            if offset and not (old.get('etag') or sha256): offset=0
            request_headers = dict(headers or {})
            request_headers['Accept-Encoding']='identity'
            if offset:
                request_headers['Range']=f'bytes={offset}-'
                if old.get('etag'): request_headers['If-Range']=old['etag']
            manager = self
            class Redirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, request, fp, code, msg, response_headers, newurl):
                    manager._url(newurl)
                    redirected = super().redirect_request(request,fp,code,msg,response_headers,newurl)
                    if urlparse(request.full_url).netloc!=urlparse(newurl).netloc:
                        redirected.remove_header('Authorization')
                        redirected.remove_header('Cookie')
                    return redirected
            try:
                request = urllib.request.Request(url,headers=request_headers)
                with urllib.request.build_opener(Redirect()).open(request,timeout=self.timeout) as response:
                    etag=response.headers.get('ETag')
                    if response.status==206:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+|\*)',response.headers.get('Content-Range',''))
                        if not match or int(match[1])!=offset or (old.get('etag') and etag!=old['etag']):
                            raise CyToolError('DownloadFailed','Invalid resume response; source changed')
                    else: offset=0
                    info['etag']=etag
                    temp = metadata.with_suffix('.tmp')
                    temp.write_text(json.dumps(info),encoding='utf-8')
                    os.replace(temp,metadata)
                    total=offset
                    expected = response.headers.get('Content-Length')
                    received=0
                    with partial.open('ab' if offset else 'wb') as stream:
                        while True:
                            if cancellation: cancellation.check()
                            if pause and pause.is_set(): return {'state':'Paused','bytes':total}
                            chunk=response.read(64*1024)
                            if not chunk: break
                            stream.write(chunk)
                            total+=len(chunk)
                            received+=len(chunk)
                            if progress: progress(total,size)
                    if expected is not None and received!=int(expected): raise CyToolError('DownloadFailed','Truncated response',recoverable=True)
                return finalize()
            except urllib.error.HTTPError as exc:
                raise CyToolError('AuthenticationRequired' if exc.code in (401,403) else 'DownloadFailed',f'HTTP {exc.code}',recoverable=exc.code>=500) from exc
            except (OSError,urllib.error.URLError,http.client.HTTPException) as exc:
                raise CyToolError('DownloadFailed',str(exc),recoverable=True) from exc

    def remove(self, name):
        with self._lock:
            for suffix in ('','.part','.download.json','.installed.json'):
                self._path(name+suffix).unlink(missing_ok=True)

    def list_installed(self):
        return [{'name':p.name,'sizeBytes':p.stat().st_size} for p in self.root.iterdir() if p.is_file() and not p.name.endswith(('.part','.download.json','.installed.json','.tmp'))]
