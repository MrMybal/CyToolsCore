import hashlib
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
from cytools_core.downloads import DownloadManager
from cytools_core import CyToolError

DATA=b'CyTools download test\n'*16000

@pytest.fixture
def source():
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            offset=int(self.headers.get('Range','bytes=0-')[6:-1])
            requests.append(offset)
            self.send_response(206 if offset else 200)
            self.send_header('Content-Length',str(len(DATA)-offset))
            self.send_header('ETag','"test-v1"')
            if offset: self.send_header('Content-Range',f'bytes {offset}-{len(DATA)-1}/{len(DATA)}')
            self.end_headers()
            try: self.wfile.write(DATA[offset:])
            except (BrokenPipeError,ConnectionResetError): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}/file',requests
    server.shutdown()
    server.server_close()
    thread.join()


def test_pause_restart_resume_hash(tmp_path,source):
    url,requests=source
    manager=DownloadManager(tmp_path,allow_test_http=True)
    pause=threading.Event()
    digest=hashlib.sha256(DATA).hexdigest()
    result=manager.download('model.bin',url,sha256=digest,size=len(DATA),pause=pause,progress=lambda *a:pause.set())
    assert result['state']=='Paused'
    assert (tmp_path/'model.bin.part').stat().st_size>0
    manager=DownloadManager(tmp_path,allow_test_http=True)
    result=manager.download('model.bin',url,sha256=digest,size=len(DATA))
    assert result['state']=='Completed'
    assert requests[1]>0
    assert manager.verify('model.bin',sha256=digest,size=len(DATA))
    assert not (tmp_path/'model.bin.part').exists()


def test_hash_failure(tmp_path,source):
    manager=DownloadManager(tmp_path,allow_test_http=True)
    with pytest.raises(CyToolError) as error: manager.download('bad.bin',source[0],sha256='0'*64)
    assert error.value.code=='IntegrityFailure'
    assert not (tmp_path/'bad.bin').exists()
    assert not (tmp_path/'bad.bin.part').exists()


def test_download_permissions(tmp_path):
    manager=DownloadManager(tmp_path)
    with pytest.raises(CyToolError): manager.download('x','http://remote.invalid/x')
    with pytest.raises(CyToolError): manager.download('../x','https://example.invalid/x')
    with pytest.raises(CyToolError) as error: manager.download('x','https://example.invalid/x',license_accepted=False)
    assert error.value.code=='LicenseAcceptanceRequired'


def test_cached_file_source_and_tampering(tmp_path,source):
    manager=DownloadManager(tmp_path,allow_test_http=True)
    url,requests=source
    manager.download('file.bin',url,revision='v1')
    assert manager.download('file.bin',url,revision='v1')['cached']
    assert len(requests)==1
    (tmp_path/'file.bin').write_bytes(b'tampered')
    manager.download('file.bin',url,revision='v1')
    assert (tmp_path/'file.bin').read_bytes()==DATA
    manager.download('file.bin',url,revision='v2')
    assert len(requests)==3
    assert len(manager.list_installed())==1
    manager.remove('file.bin')
    assert manager.list_installed()==[]


def test_shared_verified_cache_reuses_bytes_and_preserves_other_installations(tmp_path,source,monkeypatch):
    monkeypatch.setenv('CYTOOLS_DOWNLOAD_CACHE',str(tmp_path/'shared'))
    sha=hashlib.sha256(DATA).hexdigest()
    first=DownloadManager(tmp_path/'tool1',allow_test_http=True)
    second=DownloadManager(tmp_path/'tool2',allow_test_http=True)
    url,requests=source
    first.download('model.bin',url,sha256=sha)
    result=second.download('model.bin',url,sha256=sha)
    assert result['cached'] and len(requests)==1
    assert (tmp_path/'tool2/model.bin').read_bytes()==DATA
    first.remove('model.bin')
    assert (tmp_path/'tool2/model.bin').read_bytes()==DATA
    assert (tmp_path/'shared'/sha/'artifact').is_file()
    (tmp_path/'shared'/sha/'artifact').write_bytes(b'corrupted')
    first.download('model.bin',url,sha256=sha)
    assert len(requests)==2
    with pytest.raises(CyToolError):
        second.download('model.bin',url,sha256=sha,license_accepted=False)
