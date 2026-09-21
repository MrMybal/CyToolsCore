import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from cytools_core.shared_installation import InstallationStorage, register_operations
from cytools_core import CyToolError


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setenv('CYTOOLS_SETTINGS_DIR', str(tmp_path/'settings'))
    return InstallationStorage(tmp_path/'tool')


def test_shared_cache_and_private_environments(storage, tmp_path):
    assert storage.status()['downloadMode']=='local'
    storage.configure(download_mode='shared',shared_root=str(tmp_path/'shared'))
    other=InstallationStorage(tmp_path/'other')
    assert other.configuration()['sharedRoot']==str(tmp_path/'shared')
    assert other.configuration()['downloadMode']=='local'
    other.configure(download_mode='shared')
    assert storage.environment()['PIP_CACHE_DIR']==other.environment()['PIP_CACHE_DIR']
    assert 'HF_HOME' not in storage.environment()
    assert storage.status()['pythonMode']=='tool-local'
    assert not (storage.tool_root/'data/models').exists()


def test_bad_mode_and_relative_path_do_not_save(storage):
    with pytest.raises(ValueError): storage.configure(download_mode='unknown')
    with pytest.raises(ValueError): storage.configure(download_mode='shared',shared_root='relative')
    assert not storage.local_settings.exists()


def test_cuda_registry_selection_and_compiler_change(storage,tmp_path,monkeypatch):
    root=tmp_path/'CUDA'; (root/'bin').mkdir(parents=True); (root/'include').mkdir()
    compiler=root/'bin'/('nvcc.exe' if os.name=='nt' else 'nvcc')
    compiler.write_bytes(b'fixture'); (root/'include/cuda.h').write_text('fixture')
    monkeypatch.setattr('cytools_core.shared_installation.subprocess.run',lambda *a,**kw:SimpleNamespace(stdout='Cuda compilation tools, release 12.8, V12.8.93'))
    record=storage.register_cuda(str(root))
    assert record['version']=='12.8.93'
    storage.select_cuda(record['key'])
    assert storage.environment()['CUDA_HOME']==str(root)
    compiler.write_bytes(b'updated compiler')
    with pytest.raises(CyToolError,match='changed'): storage.environment()
    storage.select_cuda('')
    assert 'CUDA_HOME' not in storage.environment()


def test_content_lock_and_license_gate(storage):
    sha='a'*64
    with storage.artifact_lock(sha):
        with pytest.raises(CyToolError):
            with storage.artifact_lock(sha): pass
    with pytest.raises(ValueError):
        with storage.artifact_lock('../escape'): pass
    result=storage.download('https://example.com/model',sha256=sha,license_accepted=False)
    assert result['state']=='LicenseAcceptanceRequired'


def test_access_required_is_structured_without_credentials(storage,monkeypatch):
    def fail(*a,**kw): raise CyToolError('AuthenticationRequired','HTTP 403')
    monkeypatch.setattr('cytools_core.downloads.DownloadManager.download',fail)
    result=storage.download('https://huggingface.co/org/repo/resolve/main/model',sha256='b'*64)
    assert result['state']=='AccessRequired'
    assert 'Connect' in result['action']


def test_status_operation_uses_existing_runtime(storage,tmp_path):
    from cytools_core.scaffold import create_project
    from cytools_core import Runtime,load_manifest
    app=create_project(tmp_path/'sample','Sample','cy.test.sample')
    runtime=Runtime(load_manifest(app/'CyTool.json'),tmp_path/'jobs')
    runtime.register('echo',lambda c,p:p)
    register_operations(runtime,storage.tool_root)
    with runtime:
        actor=runtime.authenticate(runtime.create_client()['token'])
        session=runtime.create_session(actor)['sessionId']
        job=runtime.submit(actor,session,'installation_storage_status',{})
        result=runtime.wait(actor,job['jobId'])
        assert result['state']=='Completed',result
        assert result['outputs']['pythonMode']=='tool-local'
