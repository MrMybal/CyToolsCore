import copy
import threading
from types import SimpleNamespace

import pytest

from cytools_core import CyToolError, Runtime, validate_manifest
from cytools_core.transports.api import LocalClient
from conftest import CAPACITY, SYSTEM


@pytest.fixture
def grouped(tmp_path, runtime):
    descriptor = copy.deepcopy(runtime.descriptor)
    groups = {'generate': ['gpu'], 'transcribe': ['gpu'],
              'other_gpu': ['second_gpu'], 'cpu': [], 'combined': ['gpu', 'second_gpu']}
    operations = []
    for name, exclusive in groups.items():
        operation = copy.deepcopy(descriptor['operations'][0])
        operation.update(id=name, name=name, exclusiveGroups=exclusive,
                         resourceRequirements={'ramBytes': 1}, supportedBackends=[])
        operations.append(operation)
    # Same group must serialize distinct backends, not just identical operations.
    operations[0]['supportedBackends'] = ['generator']
    operations[1]['supportedBackends'] = ['recognizer']
    descriptor.update(operations=operations, backends=[
        {'id': name, 'name': name, 'threadSafe': True,
         'concurrentInference': True, 'maxConcurrentInference': 4}
        for name in ('generator', 'recognizer')],
        concurrency={'policy': 'Concurrent', 'maxWorkers': 4})
    r = Runtime(descriptor, tmp_path/'grouped', capacity=CAPACITY, system=SYSTEM)
    gates, started, order = {}, {}, []
    def handler(context, parameters):
        text = parameters['text']
        order.append(text)
        started[text].set()
        if text in gates:
            assert gates[text].wait(5), 'Test gate was not released'
        if text == 'fail':
            raise CyToolError('ExampleFailure', 'Example backend failed')
        return parameters
    for operation in operations:
        r.register(operation['id'], handler)
    actor = r.authenticate(r.create_client()['token'])
    client = LocalClient(r, actor)
    session = client.call('CreateSession')['sessionId']
    def submit(operation, text, *, block=False, **kwargs):
        started[text] = threading.Event()
        if block:
            gates[text] = threading.Event()
        return client.call('SubmitJob', sessionId=session, operationId=operation,
                           parameters={'text': text}, **kwargs)
    r.start()
    try:
        yield SimpleNamespace(runtime=r, client=client, actor=actor, session=session,
                              submit=submit, gates=gates, started=started, order=order)
    finally:
        for gate in gates.values():
            gate.set()
        r.close()


def test_shared_group_waits_without_occupying_worker_or_blocking_other_groups(grouped):
    h = grouped
    first = h.submit('generate', 'first', block=True)
    assert h.started['first'].wait(2)
    second = h.submit('transcribe', 'second')
    # A queued GPU operation must not consume an execution slot or any RAM.
    other = h.submit('other_gpu', 'other', block=True)
    cpu = h.submit('cpu', 'cpu')
    assert h.started['other'].wait(2)
    assert h.runtime.wait(h.actor, cpu['jobId'])['state'] == 'Completed'
    assert not h.started['second'].is_set()
    assert h.client.call('GetJob', jobId=second['jobId'])['state'] == 'Queued'
    assert second['jobId'] not in h.runtime.ledger.snapshot()['reservations']
    status = h.client.call('GetRuntimeStatus')
    assert status['runningJobs'] == 2 and status['queuedJobs'] == 1
    can_run = h.client.call('CanRun', operationId='transcribe', parameters={'text': 'check'})
    assert can_run['canRun'] and can_run['waitingForConcurrency']
    assert not can_run['waitingForResources']
    assert h.client.call('DescribeOperation', operationId='transcribe')['exclusiveGroups'] == ['gpu']
    h.gates['first'].set()
    assert h.runtime.wait(h.actor, second['jobId'])['state'] == 'Completed'
    h.gates['other'].set()
    for job in (first, other):
        h.runtime.wait(h.actor, job['jobId'])
    assert not h.client.call('CanRun', operationId='generate', parameters={'text': 'check'})['waitingForConcurrency']


def test_group_priority_and_cancelled_queued_job(grouped):
    h = grouped
    first = h.submit('generate', 'first', block=True)
    assert h.started['first'].wait(2)
    low = h.submit('generate', 'low', priority='Low')
    cancelled = h.submit('transcribe', 'cancelled', priority='Interactive')
    high = h.submit('transcribe', 'high', priority='Critical')
    with h.runtime._cv:
        h.client.call('CancelJob', jobId=cancelled['jobId'])
        assert h.client.call('GetRuntimeStatus')['queuedJobs'] == 2
    h.gates['first'].set()
    for job in (first, low, high, cancelled):
        h.runtime.wait(h.actor, job['jobId'])
    assert h.order == ['first', 'high', 'low']
    assert not h.started['cancelled'].is_set()


@pytest.mark.parametrize('termination', ['cancel', 'execution_timeout', 'failure'])
def test_group_retained_until_handler_exits_then_released(grouped, termination):
    h = grouped
    label = 'fail' if termination == 'failure' else 'first'
    options = {'executionTimeout': .2} if termination == 'execution_timeout' else {}
    first = h.submit('generate', label, block=True, **options)
    assert h.started[label].wait(2)
    second = h.submit('transcribe', 'second')
    if termination == 'cancel':
        h.client.call('CancelJob', jobId=first['jobId'])
    elif termination == 'execution_timeout':
        assert h.runtime._tokens[first['jobId']].event.wait(2)
    # Run a barrier job on another group while the first handler ignores cancellation.
    cpu = h.submit('cpu', 'barrier')
    assert h.runtime.wait(h.actor, cpu['jobId'])['state'] == 'Completed'
    assert not h.started['second'].is_set()
    assert first['jobId'] in h.runtime.ledger.snapshot()['reservations']
    h.gates[label].set()
    result = h.runtime.wait(h.actor, first['jobId'])
    assert result['error']['code'] == {'cancel': 'Cancelled', 'execution_timeout': 'Timeout',
                                      'failure': 'ExampleFailure'}[termination]
    assert h.runtime.wait(h.actor, second['jobId'])['state'] == 'Completed'
    assert h.runtime.ledger.snapshot()['reservations'] == {}


def test_queue_timeout_does_not_release_another_jobs_group(grouped):
    h = grouped
    first = h.submit('generate', 'first', block=True)
    assert h.started['first'].wait(2)
    timed = h.submit('transcribe', 'timed', queueTimeout=.05)
    assert h.runtime.wait(h.actor, timed['jobId'])['error']['code'] == 'Timeout'
    second = h.submit('transcribe', 'second')
    cpu = h.submit('cpu', 'barrier')
    h.runtime.wait(h.actor, cpu['jobId'])
    assert not h.started['second'].is_set() and not h.started['timed'].is_set()
    assert first['jobId'] in h.runtime.ledger.snapshot()['reservations']
    h.gates['first'].set()
    h.runtime.wait(h.actor, second['jobId'])


def test_multiple_groups_acquired_together_without_holding_free_groups(grouped):
    h = grouped
    first = h.submit('generate', 'first', block=True)
    assert h.started['first'].wait(2)
    combined = h.submit('combined', 'combined', block=True)
    other = h.submit('other_gpu', 'other', block=True)
    assert h.started['other'].wait(2)
    assert not h.started['combined'].is_set()
    h.gates['first'].set()
    h.runtime.wait(h.actor, first['jobId'])
    assert not h.started['combined'].is_set()
    h.gates['other'].set()
    assert h.started['combined'].wait(2)
    second = h.submit('generate', 'second')
    cpu = h.submit('cpu', 'barrier')
    h.runtime.wait(h.actor, cpu['jobId'])
    assert not h.started['second'].is_set()
    h.gates['combined'].set()
    for job in (other, combined, second):
        h.runtime.wait(h.actor, job['jobId'])


@pytest.mark.parametrize('groups', ['gpu', [''], ['gpu', 'gpu'], [5], ['gpu/0'], ['a'*129]])
def test_invalid_exclusive_groups_rejected(runtime, groups):
    descriptor = copy.deepcopy(runtime.descriptor)
    descriptor['operations'][0]['exclusiveGroups'] = groups
    with pytest.raises(CyToolError) as error:
        validate_manifest(descriptor)
    assert error.value.code == 'InvalidDescriptor'


def test_groups_do_not_override_global_worker_limit_or_backend_safety(grouped):
    h = grouped
    h.runtime.descriptor['concurrency']['maxWorkers'] = 1
    first = h.submit('generate', 'first', block=True)
    assert h.started['first'].wait(2)
    assert h.client.call('CanRun', operationId='cpu', parameters={'text': 'check'})['waitingForConcurrency']
    h.runtime.descriptor['concurrency'].update(maxWorkers=4, policy='Sequential')
    assert h.client.call('CanRun', operationId='cpu', parameters={'text': 'check'})['waitingForConcurrency']
    h.runtime.descriptor['concurrency']['policy'] = 'Concurrent'
    # Give the independent operation the first backend: its own safety still wins.
    h.runtime.descriptor['operations'][2]['supportedBackends'] = ['generator']
    h.runtime.descriptor['backends'][0]['concurrentInference'] = False
    assert h.client.call('CanRun', operationId='other_gpu', parameters={'text': 'check'})['waitingForConcurrency']
    h.gates['first'].set()
    h.runtime.wait(h.actor, first['jobId'])


def test_group_not_held_when_resource_reservation_cannot_start(grouped):
    h = grouped
    h.runtime.descriptor['operations'][0]['resourceRequirements'] = {'ramBytes': CAPACITY['ramBytes']}
    cpu = h.submit('cpu', 'cpu', block=True)
    assert h.started['cpu'].wait(2)
    blocked = h.submit('generate', 'blocked')
    # Same group, smaller reservation: it is admissible while the large job waits.
    small = h.submit('transcribe', 'small')
    assert h.runtime.wait(h.actor, small['jobId'])['state'] == 'Completed'
    assert not h.started['blocked'].is_set()
    assert blocked['jobId'] not in h.runtime.ledger.snapshot()['reservations']
    h.gates['cpu'].set()
    assert h.runtime.wait(h.actor, blocked['jobId'])['state'] == 'Completed'


def test_mcp_http_clients_share_groups_and_status(grouped):
    import asyncio
    import json
    import os
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from cytools_core.transports.http import make_server

    h = grouped
    h.runtime.register_worker('resident', SimpleNamespace(process=None, release=lambda level: None))
    credential = h.runtime.create_client('MCP client')
    remote_actor = h.runtime.authenticate(credential['token'])
    first = h.submit('generate', 'first', block=True)
    assert h.started['first'].wait(2)
    h.started['remote'] = threading.Event()
    h.started['remote_cpu'] = threading.Event()
    server = make_server(h.runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def scenario():
        parameters = StdioServerParameters(command=sys.executable, args=[
            '-m', 'cytool_test', '--connect', f'http://127.0.0.1:{server.server_port}/v1', 'mcp'],
            env={**os.environ, 'CYTOOLS_TOKEN': credential['token']})
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                contract = await session.call_tool('cy_describe_operation', {'operationId': 'transcribe'})
                assert json.loads(contract.content[0].text)['exclusiveGroups'] == ['gpu']
                result = await session.call_tool('op_transcribe', {'parameters': {'text': 'remote'}})
                assert not result.isError
                remote = json.loads(result.content[0].text)
                status = await session.call_tool('cy_status', {})
                assert not status.isError, status
                value = json.loads(status.content[0].text)
                assert value['runningJobs'] == 1 and value['queuedJobs'] == 1
                assert value['runningWorkers'] == 0 and value['unknownWorkers'] == 0
                assert 'reservations' not in value['resources']
                result = await session.call_tool('op_cpu', {'parameters': {'text': 'remote_cpu'}})
                cpu = json.loads(result.content[0].text)
                assert h.runtime.wait(remote_actor, cpu['jobId'])['state'] == 'Completed'
                assert not h.started['remote'].is_set()
                private = await session.call_tool('cy_get_job', {'jobId': first['jobId']})
                assert private.isError
                h.gates['first'].set()
                assert h.runtime.wait(remote_actor, remote['jobId'])['state'] == 'Completed'

    try:
        asyncio.run(scenario())
    finally:
        h.gates['first'].set()
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_groups_include_operations_added_before_start(tmp_path, runtime):
    descriptor = copy.deepcopy(runtime.descriptor)
    descriptor['operations'] = descriptor['operations'][:1]
    r = Runtime(descriptor, tmp_path/'extended', capacity=CAPACITY, system=SYSTEM)
    entered, release, second_entered = threading.Event(), threading.Event(), threading.Event()
    def first_handler(context, parameters):
        entered.set()
        assert release.wait(5)
        return parameters
    def second_handler(context, parameters):
        second_entered.set()
        return parameters
    r.register('echo', first_handler)
    r.descriptor['operations'][0]['exclusiveGroups'] = ['gpu']
    added = copy.deepcopy(r.descriptor['operations'][0])
    added.update(id='extension')
    r.descriptor['operations'].append(added)
    r.register('extension', second_handler)
    assert r.can_run('extension', {'text': 'check'})['canRun']
    try:
        r.start()
        actor = r.authenticate(r.create_client()['token'])
        session = r.create_session(actor)['sessionId']
        first = r.submit(actor, session, 'echo', {'text': 'first'})
        assert entered.wait(2)
        second = r.submit(actor, session, 'extension', {'text': 'second'})
        assert r.can_run('extension', {'text': 'check'})['waitingForConcurrency']
        assert not second_entered.is_set()
        release.set()
        for job in (first, second):
            assert r.wait(actor, job['jobId'])['state'] == 'Completed'
    finally:
        release.set()
        r.close()


def test_groups_modified_before_start_are_revalidated(tmp_path, runtime):
    descriptor = copy.deepcopy(runtime.descriptor)
    descriptor['operations'] = descriptor['operations'][:1]
    r = Runtime(descriptor, tmp_path/'invalid-extension', capacity=CAPACITY, system=SYSTEM)
    try:
        r.register('echo', lambda context, parameters: parameters)
        r.descriptor['operations'][0]['exclusiveGroups'] = 'gpu'
        with pytest.raises(CyToolError) as error:
            r.start()
        assert error.value.code == 'InvalidDescriptor'
    finally:
        r.close()
