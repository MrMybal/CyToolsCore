"""Lazy C ABI bindings. CyMCPSDK C++ owns protocols, CLI parsing and networking.

The callback adapts the existing Tool runtime; it does not implement a transport.
"""
import ctypes
import json
import os
from pathlib import Path
import sys
import threading

from ..errors import CyToolError
from ..schema import schema, validate_document, _check_schema
from .api import LocalClient

_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)
_library = None
_load_lock = threading.Lock()


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')


def _result(raw):
    value = json.loads(raw)
    if 'error' in value:
        error = value['error']
        raise CyToolError(error['code'], error.get('message', 'Native communication failed'),
                          details=error.get('technicalDetails'), recoverable=error.get('recoverable', False))
    return value['result']


def library():
    global _library
    with _load_lock:
        if _library is not None:
            return _library
        name = ('cytools_communication.dll' if sys.platform == 'win32' else
                'libcytools_communication.dylib' if sys.platform == 'darwin' else
                'libcytools_communication.so')
        root = Path(__file__).resolve().parents[1]
        configured = os.environ.get('CYTOOLS_NATIVE_LIBRARY')
        candidates = ([Path(configured)] if configured else [
            root/'native'/name, root.parent/'build/native'/name,
            root.parent/'build/native/Release'/name])
        target = next((p for p in candidates if p.is_absolute() and p.is_file()), None)
        if target is None:
            raise CyToolError('NativeDependencyMissing',
                'CyMCPSDK native communication is not installed. Build Native/ and package its library; '
                'see Docs/NativeCommunication.md. There is no Python transport fallback.')
        try:
            lib = ctypes.CDLL(str(target))
        except OSError as exc:
            raise CyToolError('NativeDependencyMissing', 'Cannot load packaged native communication library') from exc
        lib.cytools_native_info.restype = ctypes.c_char_p
        info = json.loads(lib.cytools_native_info())
        if info.get('abi') != 1 or info.get('version') != '0.11.0':
            raise CyToolError('IncompatibleVersion', 'Native communication library does not match this Core')
        lib.cytools_communication_create.argtypes = [_CALLBACK, ctypes.c_void_p]
        lib.cytools_communication_create.restype = ctypes.c_void_p
        lib.cytools_communication_call.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.cytools_communication_call.restype = ctypes.c_char_p
        lib.cytools_communication_destroy.argtypes = [ctypes.c_void_p]
        lib.cytools_communication_destroy.restype = None
        lib.cytools_http_call.argtypes = [ctypes.c_char_p]
        lib.cytools_http_call.restype = ctypes.c_char_p
        _library = lib
        return lib


class NativeHost:
    def __init__(self, factory=None, *, runtime=None, client=None):
        self.factory, self.runtime, self.client = factory, runtime, client
        self.owned_runtime = False
        self.actors = {}
        if isinstance(client, LocalClient):
            self.runtime = client.runtime
            self.actors[client.principal.client_id] = client.principal
        # Foreign C++ worker callbacks receive transient Python thread states.
        # Keep buffers on the host, not threading.local(), beyond callback return.
        self._buffers = {}
        self._callback = _CALLBACK(self._on_request)
        self.lib = library()
        self.handle = self.lib.cytools_communication_create(self._callback, None)
        if not self.handle:
            raise CyToolError('ConfigurationError', 'Cannot create native communication host')

    def _start_runtime(self, data_dir):
        if self.runtime is None and self.factory is not None:
            self.runtime = self.factory(data_dir)
            self.owned_runtime = True
            self.runtime.start()

    def _handle_request(self, request):
        method = request['method']
        if method in ('$bootstrap', '$create_client'):
            params = request.get('params', {})
            self._start_runtime(params.get('dataDir', '.cytools'))
            if method == '$create_client':
                return self.runtime.create_client(params['name'], params.get('permissions', []))
            if self.client is None:
                token = os.environ.get('CYTOOLS_TOKEN')
                actor = self.runtime.authenticate(token if token else self.runtime.create_client('standalone')['token'])
                self.client = LocalClient(self.runtime, actor)
                self.actors[actor.client_id] = actor
            return {'principal': self.client.principal.client_id if isinstance(self.client, LocalClient) else 'remote'}
        if method == '$authenticate':
            actor = self.runtime.authenticate(request['token'])
            self.actors[actor.client_id] = actor
            return {'principal': actor.client_id}
        if method == '$request':
            wire = request['request']
            if self.runtime is not None:
                actor = self.actors.get(request['principal'])
                if actor is None:
                    raise CyToolError('AccessDenied', 'Authenticated transport identity required')
                return LocalClient(self.runtime, actor).dispatch(wire)
            validate_document(wire, 'request')
            try:
                return {'protocolVersion': '1.0', 'id': wire['id'],
                        'result': self.client.call(wire['method'], **wire['params'])}
            except CyToolError as exc:
                return {'protocolVersion': '1.0', 'id': wire['id'], 'error': exc.to_dict()}
        if method == '$schemas':
            return {'requests': {item['if']['properties']['method']['const']: item['then']['properties']['params']
                                 for item in schema('request')['allOf']}, 'job': schema('job')}
        if method in ('$check_schema', '$validate'):
            from jsonschema import Draft202012Validator
            from jsonschema.exceptions import SchemaError, ValidationError
            spec = request['schema']
            _check_schema(spec)
            try:
                if method == '$check_schema':
                    Draft202012Validator.check_schema(spec)
                else:
                    Draft202012Validator(spec).validate(request['value'])
            except (SchemaError, ValidationError) as exc:
                raise CyToolError('InvalidSchema' if method == '$check_schema' else 'InvalidParameters', exc.message) from exc
            return None
        raise CyToolError('UnknownMethod', 'Unknown private runtime binding method')

    def _on_request(self, raw, _):
        try:
            result = {'result': self._handle_request(json.loads(raw))}
        except CyToolError as exc:
            result = {'error': exc.to_dict()}
        except Exception:
            result = {'error': CyToolError('InternalError', 'Tool host callback failed').to_dict()}
        buffer = ctypes.create_string_buffer(_json(result))
        self._buffers[threading.get_ident()] = buffer
        return ctypes.addressof(buffer)

    def call(self, command, **params):
        if not self.handle:
            raise CyToolError('InvalidState', 'Native host is closed')
        return _result(self.lib.cytools_communication_call(self.handle, _json({'command': command, **params})))

    def close(self):
        if self.handle:
            self.lib.cytools_communication_destroy(self.handle)
            self.handle = None
        if self.owned_runtime:
            self.runtime.close()
            self.owned_runtime = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def http_call(url, token, request, timeout=30):
    return _result(library().cytools_http_call(_json({
        'url': url, 'token': token, 'request': request, 'timeoutMs': round(timeout * 1000)})))
