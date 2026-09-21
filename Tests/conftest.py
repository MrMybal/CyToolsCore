import pytest
from cytool_test import create_runtime

SYSTEM={'os':'Windows','osVersion':'test','architecture':'x64','cpuThreads':8,'cpuCores':4,
        'ramFreeBytes':64*1024**3,'ramTotalBytes':64*1024**3,'diskFreeBytes':1024**4,'computeBackends':['CPU'],'gpus':[]}
CAPACITY={'ramBytes':64*1024**3,'diskBytes':1024**4,'cpuThreads':8,'vramBytes':{'simulation':16*1024**3}}

@pytest.fixture
def runtime(tmp_path):
    with create_runtime(tmp_path,system=SYSTEM,capacity=CAPACITY) as runtime:
        yield runtime

@pytest.fixture
def actor(runtime):
    return runtime.authenticate(runtime.create_client('Alice')['token'])

@pytest.fixture
def session(runtime,actor):
    return runtime.create_session(actor)['sessionId']
