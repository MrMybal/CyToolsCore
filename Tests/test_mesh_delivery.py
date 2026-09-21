import importlib.machinery
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from cytools_core.scaffold import create_project


def module(path):
    spec=importlib.util.spec_from_loader('test_mesh_ui',importlib.machinery.SourceFileLoader('test_mesh_ui',str(path)))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def test_mesh_scaffold_is_opt_in_and_outside_runtime(tmp_path):
    with pytest.raises(ValueError):create_project(tmp_path/'Bad','Bad','cy.bad',mesh_viewer=True)
    root=create_project(tmp_path/'Mesh','Mesh','cy.mesh',desktop=True,mesh_viewer=True)
    assert json.loads((root/'app/mesh-viewer.json').read_text())['enabled']
    assert 'moderngl==5.12.0' in (root/'app/requirements.txt').read_text()
    assert (root/'app/mesh_viewer.py').exists()


def test_completed_job_opens_real_mesh_and_poll_keeps_authenticated_principal(tmp_path,monkeypatch):
    source=Path(__file__).parents[1]/'cytools_core/templates/mesh_viewer_ui.py.txt'
    ui=module(source);mesh=tmp_path/'model.glb';mesh.write_bytes(b'fixture')
    actor=object();calls=[]
    runtime=SimpleNamespace()
    runtime.submit=lambda *a,**kw:{'jobId':'j','state':'Queued'}
    def get(principal,job_id):
        assert principal is actor
        calls.append(job_id)
        return {'jobId':job_id,'state':'Completed','outputs':{'mesh_file':str(mesh)}}
    runtime.get_job=get
    panel=ui.MeshPanel(runtime,tmp_path);runtime.submit(actor,'session','generate',{})
    panel.poll()
    assert panel.path==str(mesh) and panel.pending
    assert calls==['j'] and not panel.tracked
    panel.pending=False
    panel.observe({'jobId':'failed','state':'Failed','outputs':{'file':str(mesh)}})
    assert not panel.pending
    assert json.loads(panel.settings.read_text())['file']==str(mesh)


def test_pbr_sidecar_and_unsupported_outputs(tmp_path):
    ui=module(Path(__file__).parents[1]/'cytools_core/templates/mesh_viewer_ui.py.txt')
    mesh=tmp_path/'preview.glb';mesh.write_bytes(b'fixture')
    assert ui.mesh_outputs({'report_file':str(tmp_path/'report.json'),'material_mesh_file':''})==[str(mesh)]
    assert ui.mesh_outputs({'file':str(tmp_path/'motion.npz')})==[]
