import json
import sys
from pathlib import Path
import pytest
from cytools_core import CyToolError, CancellationToken
from cytools_core.workers import ProcessWorker


class Context:
    def __init__(self,root,deadline=None):
        self.workspace=root
        self.cancellation=CancellationToken(deadline)


def test_worker_roundtrip_and_restart(tmp_path):
    code="import json,sys; r=json.load(sys.stdin); print(json.dumps(r['parameters']))"
    worker=ProcessWorker([sys.executable,'-c',code])
    for value in ('one','two'):
        assert worker.run(Context(tmp_path),{'text':value})=={'text':value}
        assert worker.health()['state']=='Stopped'


def test_worker_crash_and_invalid_json(tmp_path):
    worker=ProcessWorker([sys.executable,'-c','import sys; sys.exit(7)'])
    with pytest.raises(CyToolError) as error: worker.run(Context(tmp_path),{})
    assert error.value.code=='WorkerCrashed'
    assert worker.state=='Failed'
    worker.command=[sys.executable,'-c','print("not json")']
    with pytest.raises(CyToolError) as error: worker.run(Context(tmp_path),{})
    assert error.value.code=='ProtocolError'
    worker.command=[sys.executable,'-c','print("{}")']
    assert worker.run(Context(tmp_path),{})=={}


def test_worker_cancellation_silent_process(tmp_path):
    import time
    worker=ProcessWorker([sys.executable,'-c','import time; time.sleep(30)'])
    with pytest.raises(CyToolError) as error: worker.run(Context(tmp_path,time.monotonic()+.1),{})
    assert error.value.code=='Timeout'
    assert worker.process is None


def test_worker_resource_release(runtime):
    actor=runtime.authenticate(runtime.create_client('admin',['manageResources'])['token'])
    worker=ProcessWorker([sys.executable,'-c','print("{}")'])
    runtime.register_worker('test',worker)
    assert runtime.ledger.reserve('worker:test',{'ramBytes':20,'vramBytes':{'simulation':1024}})
    runtime.release_resources(actor,'Worker')
    assert runtime.ledger.snapshot()['reservations']=={}
    assert worker.state=='Stopped'
