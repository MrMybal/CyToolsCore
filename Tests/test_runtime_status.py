import json
import threading
from types import SimpleNamespace

import pytest

from cytools_core.schema import validate_document
from cytools_core.transports.api import LocalClient


class CustomWorker:
    """The existing adapter contract requires release(), not a state attribute."""

    def release(self, level):
        pass


@pytest.mark.parametrize('kind,running,unknown', [
    ('resident_stopped', 0, 0),
    ('resident_running', 1, 0),
    ('resident_exited', 0, 0),
    ('starting', 1, 0),
    ('idle', 1, 0),
    ('failed', 0, 0),
    ('failed_but_alive', 1, 0),
    ('health_alive', 1, 0),
    ('health_loaded', 1, 0),
    ('health_stopped', 0, 0),
    ('health_failed', 0, 0),
    ('health_error', 0, 1),
    ('health_invalid', 0, 1),
    ('unobservable', 0, 1),
])
def test_status_with_custom_worker(runtime, actor, kind, running, unknown):
    worker = CustomWorker()
    if kind.startswith('resident_'):
        worker.process = None if kind == 'resident_stopped' else SimpleNamespace(
            poll=lambda: None if kind == 'resident_running' else 0)
    elif kind in ('starting', 'idle', 'failed', 'failed_but_alive'):
        worker.state = {'starting': 'Starting', 'idle': 'Idle'}.get(kind, 'Failed')
        if kind == 'failed_but_alive':
            worker.process = SimpleNamespace(poll=lambda: None)
    elif kind.startswith('health_'):
        def health():
            if kind == 'health_error':
                raise RuntimeError('Adapter could not read its status')
            return {
                'health_alive': {'alive': True},
                'health_loaded': {'loaded': True},
                'health_stopped': {'state': 'Stopped'},
                'health_failed': {'state': 'Failed'},
                'health_invalid': None,
            }[kind]
        worker.health = health
    runtime.register_worker('custom', worker)
    assert runtime.reserve_worker('custom', {'ramBytes': 12})
    client = LocalClient(runtime, actor)
    response = client.dispatch({'protocolVersion': '1.0', 'id': 15,
                                'method': 'GetRuntimeStatus', 'params': {}})
    validate_document(response, 'response')
    assert 'error' not in response, response
    status = response['result']
    assert status['runningWorkers'] == running
    assert status['unknownWorkers'] == unknown
    assert status['acceptingJobs'] is True
    assert 'reservations' not in status['resources']
    assert 'worker:custom' not in json.dumps(status)
    # Observation must never unload workers or release their reservations.
    assert runtime.ledger.snapshot()['reservations']['worker:custom']['ramBytes'] == 12


def test_status_does_not_hold_scheduler_lock_during_adapter_health(runtime):
    acquired = threading.Event()
    worker = CustomWorker()

    def use_runtime():
        with runtime._cv:
            acquired.set()

    def health():
        thread = threading.Thread(target=use_runtime, daemon=True)
        thread.start()
        assert acquired.wait(2), 'Adapter health called while scheduler lock is held'
        thread.join(2)
        return {'alive': True}

    worker.health = health
    runtime.register_worker('callback', worker)
    assert runtime.status()['runningWorkers'] == 1


def test_status_does_not_probe_health_when_process_is_observable(runtime):
    worker = CustomWorker()
    worker.process = None

    def health():
        pytest.fail('Resident health can unload a model; do not call it for simple metrics')

    worker.health = health
    runtime.register_worker('resident', worker)
    assert runtime.status()['runningWorkers'] == 0
