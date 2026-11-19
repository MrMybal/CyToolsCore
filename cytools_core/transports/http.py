"""Compatibility bindings for CyMCPSDK native authenticated HTTP."""
import threading
from ..errors import CyToolError


class NativeHTTPServer:
    def __init__(self, runtime, port):
        from ._native import NativeHost
        self.host = NativeHost(runtime=runtime)
        try:
            self.server_port = self.host.call('start_http', port=port)
        except BaseException:
            self.host.close()
            raise
        self.server_address = ('127.0.0.1', self.server_port)
        self.stopped = threading.Event()

    def serve_forever(self, poll_interval=.5):
        self.stopped.wait()

    def shutdown(self):
        self.host.call('stop_http')
        self.stopped.set()

    def server_close(self):
        self.stopped.set()
        self.host.close()


def make_server(runtime, port=0):
    return NativeHTTPServer(runtime, port)


class HTTPClient:
    def __init__(self, url, token, timeout=30):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')):
            raise ValueError('Remote API connections require HTTPS')
        self.url, self.token, self.timeout = url, token, timeout

    def call(self, method, **params):
        from ._native import http_call
        result = http_call(self.url, self.token,
                           {'protocolVersion': '1.0', 'id': 1, 'method': method, 'params': params}, self.timeout)
        if 'error' in result:
            error = result['error']
            raise CyToolError(error['code'], error.get('message', 'Request failed'),
                              details=error.get('technicalDetails'), recoverable=error.get('recoverable', False))
        return result['result']
