"""Authenticated loopback JSON API. Remote deployments require a TLS/auth gateway."""
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ..errors import CyToolError
from .api import LocalClient


def make_server(runtime, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def do_POST(self):
            self.connection.settimeout(10)
            try:
                if self.path!='/v1': return self.reply(404,{'error':'Not found'})
                # No browser-origin requests; desktop clients use Bearer credentials.
                if self.headers.get('Origin'): return self.reply(403,{'error':'Browser origins not accepted'})
                auth=self.headers.get('Authorization','')
                if not auth.startswith('Bearer '): raise CyToolError('AuthenticationRequired','Bearer token required')
                actor=runtime.authenticate(auth[7:])
                if self.headers.get('Transfer-Encoding') or not self.headers.get('Content-Length'):
                    return self.reply(411,{'error':'Content-Length is required; chunked requests are not supported'})
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1024*1024: return self.reply(413,{'error':'Request must be between 1 byte and 1 MiB'})
                request=json.loads(self.rfile.read(length))
                self.reply(200,LocalClient(runtime,actor).dispatch(request))
            except CyToolError as exc: self.reply(401,{'error':exc.to_dict()})
            except (ValueError,TimeoutError): self.reply(400,{'error':'Invalid JSON request'})

        def reply(self,status,data):
            encoded=json.dumps(data,allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server


class HTTPClient:
    def __init__(self,url,token,timeout=30):
        from urllib.parse import urlparse
        parsed=urlparse(url)
        if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1')):
            raise ValueError('Remote API connections require HTTPS')
        self.url,self.token,self.timeout=url,token,timeout

    def call(self,method,**params):
        data=json.dumps({'protocolVersion':'1.0','id':1,'method':method,'params':params},allow_nan=False).encode('utf-8')
        request=urllib.request.Request(self.url,data=data,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        # Refuse redirects so credentials never follow a different endpoint.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): return None
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=self.timeout) as response: result=json.load(response)
        except urllib.error.HTTPError as exc:
            raise CyToolError('AuthenticationRequired' if exc.code==401 else 'TransportError',f'HTTP {exc.code}') from exc
        if 'error' in result:
            error=result['error']
            raise CyToolError(error['code'],error['message'],details=error.get('technicalDetails'),recoverable=error.get('recoverable',False))
        return result['result']
