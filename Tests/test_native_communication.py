"""Conformance across the real CyMCPSDK C++ boundary, without AI/model downloads."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from cytools_core import CyToolError
from cytools_core.transports._native import NativeHost, library
from cytools_core.transports.api import LocalClient
from cytools_core.transports.http import make_server


def invoke(host, name, **arguments):
    return host.call('sdk', request={'method': 'invoke', 'name': name, 'arguments': arguments})['result']


def test_native_catalogue_preserves_refs_and_enforces_pattern(runtime, actor):
    op = runtime.descriptor['operations'][0]
    op['inputSchema'] = {'type': 'object', '$defs': {'word': {'type': 'string', 'pattern': '^yes$'}},
                         'properties': {'text': {'$ref': '#/$defs/word'}}, 'required': ['text'],
                         'additionalProperties': False}
    with NativeHost(client=LocalClient(runtime, actor)) as host:
        catalogue = host.call('sdk', request={'method': 'describe'})['operations']
        spec = next(x for x in catalogue if x['name'] == 'op_echo')['inputSchema']
        assert spec['properties']['parameters']['properties']['text']['$ref'] == '#/properties/parameters/$defs/word'
        with pytest.raises(CyToolError, match='yes'):
            invoke(host, 'op_echo', parameters={'text': 'no'})
        job = invoke(host, 'op_echo', parameters={'text': 'yes'})
        assert runtime.wait(actor, job['jobId'])['outputs'] == {'text': 'yes'}


def test_native_sdk_task_identity_and_cleanup(runtime, tmp_path):
    runtime.configure_inputs(tmp_path/'inputs')
    source = tmp_path/'original.txt'
    source.write_text('original', encoding='utf-8')
    actors = [runtime.authenticate(runtime.create_client(name)['token']) for name in ['A', 'B']]
    with NativeHost(client=LocalClient(runtime, actors[0])) as a, NativeHost(client=LocalClient(runtime, actors[1])) as b:
        task = invoke(a, 'cy_begin_task')['sessionId']
        with pytest.raises(CyToolError, match='another connection'):
            invoke(b, 'op_echo', sessionId=task, parameters={'text': 'spoof'})
        with pytest.raises(CyToolError):
            invoke(b, 'cy_begin_task', temporary=False)
        imported = Path(invoke(a, 'cy_import_file', sessionId=task, source=str(source))['path'])
        job = invoke(a, 'op_generate_file', sessionId=task, parameters={'text': 'result'})
        stopped = runtime.wait(actors[0], job['jobId'])
        generated = Path(stopped['outputs']['file'])
        assert imported.exists() and generated.exists()
        assert invoke(b, 'cy_list_jobs') == []
    assert source.read_text('utf-8') == 'original'
    assert not imported.exists() and not generated.exists()
    assert runtime.get_job(actors[0], job['jobId'])['artifactsDeleted']


def test_native_cli_unicode_export_and_temporary_files(tmp_path):
    params = tmp_path/'réglages.json'
    params.write_text(json.dumps({'text': 'été et forêt'}, ensure_ascii=False), encoding='utf-8-sig')
    command = [sys.executable, '-m', 'cytool_test', '--data-dir', str(tmp_path/'runtime'),
               'invoke', 'generate_file', '--params-file', str(params)]
    result = subprocess.run(command, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    job = json.loads(result.stdout)
    assert job['artifactsDeleted']
    assert not Path(job['workspace']).exists()
    assert not Path(job['outputs']['file']).exists()
    result = subprocess.run(command+['--export-dir', str(tmp_path/'exports')],
                            capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    bundle = json.loads(result.stdout)
    assert Path(bundle['outputs']['file']).read_text('utf-8') == 'été et forêt'


def test_native_executable_needs_no_python_for_remote_calls(runtime, tmp_path):
    credential = runtime.create_client('Native executable')
    server = make_server(runtime)
    executable = Path(__file__).resolve().parents[1]/'cytools_core/native'/('cytools-native.exe' if os.name == 'nt' else 'cytools-native')
    try:
        result = subprocess.run([str(executable), '--connect', f'http://127.0.0.1:{server.server_port}/v1', 'describe'],
                                env={**os.environ, 'PATH': '', 'CYTOOLS_TOKEN': credential['token']},
                                capture_output=True, encoding='utf-8', timeout=20)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['id'] == runtime.descriptor['id']
        params = tmp_path/'réglages.json'
        params.write_text(json.dumps({'text': 'forêt'}, ensure_ascii=False), 'utf-8')
        destination = tmp_path.parent/(tmp_path.name+'-exporté')
        result = subprocess.run([str(executable), '--connect', f'http://127.0.0.1:{server.server_port}/v1',
                    'invoke', 'generate_file', '--params-file', str(params), '--export-dir', str(destination)],
                    env={**os.environ, 'PATH': '', 'CYTOOLS_TOKEN': credential['token']},
                    capture_output=True, encoding='utf-8', timeout=20)
        assert result.returncode == 0, result.stderr
        assert Path(json.loads(result.stdout)['outputs']['file']).read_text('utf-8') == 'forêt'
    finally:
        server.shutdown()
        server.server_close()


def test_missing_native_library_is_explicit_and_import_stays_lazy(tmp_path):
    env = {**os.environ, 'CYTOOLS_NATIVE_LIBRARY': str(tmp_path/'not-installed.dll')}
    result = subprocess.run([sys.executable, '-c',
        "import sys,cytools_core; assert 'cytools_core.transports._native' not in sys.modules"],
        env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([sys.executable, '-m', 'cytool_test', 'describe'],
                            env=env, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 1
    assert json.loads(result.stderr)['error']['code'] == 'NativeDependencyMissing'


def test_native_mcp_bridge_has_no_python_client_process(runtime):
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    credential = runtime.create_client('Native MCP bridge')
    server = make_server(runtime)
    executable = Path(__file__).resolve().parents[1]/'cytools_core/native'/('cytools-native.exe' if os.name == 'nt' else 'cytools-native')
    async def scenario():
        params = StdioServerParameters(command=str(executable),
            args=['--connect', f'http://127.0.0.1:{server.server_port}/v1', 'mcp'],
            env={**os.environ, 'PATH': '', 'CYTOOLS_TOKEN': credential['token']})
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool('op_echo', {'parameters': {'text': 'native client'}})
                assert not result.isError, result
                job = json.loads(result.content[0].text)
                actor = runtime.authenticate(credential['token'])
                assert runtime.wait(actor, job['jobId'])['outputs'] == {'text': 'native client'}
                invalid = await session.call_tool('op_generate_file', {'parameters': {'name': '../bad', 'text': 'x'}})
                assert invalid.isError
    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()


def test_native_http_rejects_origin_and_identity_spoof(runtime):
    import urllib.request
    import urllib.error
    server = make_server(runtime)
    token = runtime.create_client('Native auth')['token']
    url = f'http://127.0.0.1:{server.server_port}/v1'
    body = {'protocolVersion': '1.0', 'id': 1, 'method': 'DescribeTool', 'params': {}}
    try:
        request = urllib.request.Request(url, json.dumps(body).encode(),
                   headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json', 'Origin': 'http://localhost'})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 403
        other = runtime.authenticate(runtime.create_client('Other identity')['token'])
        session = runtime.create_session(other)['sessionId']
        runtime.submit(other, session, 'echo', {'text': 'private'})
        body.update(method='ListJobs', principal=other.client_id)
        request = urllib.request.Request(url, json.dumps(body).encode(),
                   headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request) as response:
            assert json.load(response)['result'] == []
        from cytools_core.transports._native import http_call
        for internal in [
            {'method': '$authenticate', 'token': token},
            {'method': '$validate', 'schema': {'type': 'string', 'pattern': '(a+)+$'}, 'value': 'x'},
        ]:
            result = http_call(url, token, {'method': 'cytools.host', 'request': internal})
            assert result['error']['code'] == 'AccessDenied'
    finally:
        server.shutdown()
        server.server_close()


def test_native_cli_rejects_ignored_options():
    for args in [['describe', '--model', 'ignored'], ['invoke', 'echo', '--timeout', 'invalid']]:
        result = subprocess.run([sys.executable, '-m', 'cytool_test', *args],
                                capture_output=True, encoding='utf-8', timeout=20)
        assert result.returncode == 1
        assert json.loads(result.stderr)['error']['code'] == 'InvalidParameters'



def test_native_principal_is_opaque_during_cleanup(runtime, actor):
    class OpaqueHost(NativeHost):
        def _handle_request(self, request):
            result = super()._handle_request(request)
            if request['method'] == '$bootstrap':
                self.actors['tenant:plugin/user'] = actor
                return {'principal': 'tenant:plugin/user'}
            return result
    with OpaqueHost(client=LocalClient(runtime, actor)) as host:
        job = invoke(host, 'op_generate_file', parameters={'text': 'opaque identity'})
        stopped = runtime.wait(actor, job['jobId'])
        output = Path(stopped['outputs']['file'])
        assert output.exists()
    assert not output.exists()



def test_native_mcp_keeps_full_length_operation_ids(runtime, tmp_path):
    from cytools_core import Runtime
    from conftest import CAPACITY, SYSTEM
    descriptor = copy.deepcopy(runtime.descriptor)
    descriptor['operations'] = [descriptor['operations'][0]]
    full_id = 'operation_' + 'x' * 118
    assert len(full_id) == 128
    descriptor['operations'][0]['id'] = full_id
    r = Runtime(descriptor, tmp_path/'long-id', capacity=CAPACITY, system=SYSTEM)
    r.register(full_id, lambda context, parameters: {'text': parameters['text']})
    with r:
        principal = r.authenticate(r.create_client('Long ID')['token'])
        with NativeHost(client=LocalClient(r, principal)) as host:
            catalogue = host.call('sdk', request={'method': 'describe'})['operations']
            assert all(len(op['name']) <= 128 for op in catalogue)
            alias = next(op['name'] for op in catalogue if full_id in op['description'])
            job = invoke(host, alias, parameters={'text': 'alias'})
            assert r.wait(principal, job['jobId'])['outputs'] == {'text': 'alias'}
            job = invoke(host, 'cy_submit_job', operationId=full_id, parameters={'text': 'full ID'})
            assert r.wait(principal, job['jobId'])['outputs'] == {'text': 'full ID'}
