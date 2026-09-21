"""Dear ImGui mesh viewport; bound only to this UI's authenticated runtime calls."""
import json
from pathlib import Path
import sys
import time
import uuid

_instance=None
FORMATS={'.glb','.gltf','.obj','.ply','.stl','.off'}


def mesh_outputs(value):
    if not isinstance(value,dict):return []
    result=[]
    # Prefer the material/rigged mesh over auxiliary point clouds or source files.
    for key in ('material_mesh_file','rigged_mesh','mesh_file','mesh','file'):
        path=value.get(key)
        if isinstance(path,str) and Path(path).suffix.lower() in FORMATS and Path(path).is_file():result.append(path)
    report=value.get('report_file')
    if not result and isinstance(report,str):
        candidate=Path(report).parent/'preview.glb'
        if candidate.is_file():result.append(str(candidate))
    return list(dict.fromkeys(result))


class MeshPanel:
    def __init__(self,runtime,root):
        self.runtime=runtime;self.root=Path(root);self.renderer=None;self.pending=False
        self.path='';self.error='';self.mode=0;self.keyboard=0;self.scene=0;self.lighting=0
        self.grid=True;self.wire=False;self.exposure=0.;self.dialog=None;self.focused=False
        self.tracked={};self.finished=set();self.last_poll=0.;self.test_started=time.monotonic();self.loaded_test_frames=0
        self.settings=self.root/'data/settings/mesh-viewer.json'
        self.test_path=next((arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--ui-test-viewer=')),'')
        self.test=bool(self.test_path)
        try:
            settings=json.loads(self.settings.read_text('utf-8'))
            self.path=settings.get('file','');self.scene=int(settings.get('scene',0));self.lighting=int(settings.get('lighting',0))
            self.keyboard=int(settings.get('keyboard',0))
        except (OSError,ValueError,TypeError):pass
        self.scene=max(0,min(2,self.scene));self.lighting=max(0,min(3,self.lighting));self.keyboard=max(0,min(1,self.keyboard))
        if not self.path:
            try:
                saved=json.loads((self.root/'data/settings/desktop.json').read_text('utf-8'))
                matches=mesh_outputs(saved.get('last_outputs',{})) or mesh_outputs(saved.get('outputs',{}))
                if matches:self.path=matches[0]
            except (OSError,ValueError):pass
        if self.test_path:self.path=self.test_path
        self.pending=bool(self.path)
        if runtime is not None:
            original_submit=runtime.submit;original_get=runtime.get_job
            def submit(principal,session_id,operation_id,parameters,**kwargs):
                if self.renderer:self.renderer.close();self.renderer=None
                job=original_submit(principal,session_id,operation_id,parameters,**kwargs)
                self.tracked[job['jobId']]=principal
                return job
            def get(principal,job_id,*args,**kwargs):
                job=original_get(principal,job_id,*args,**kwargs)
                self.observe(job)
                return job
            runtime.submit=submit;runtime.get_job=get

    def observe(self,job):
        if job['state'] not in ('Completed','Failed','Cancelled'):return
        self.tracked.pop(job['jobId'],None)
        if job['jobId'] in self.finished:return
        self.finished.add(job['jobId'])
        if job['state']=='Completed':
            matches=mesh_outputs(job.get('outputs',{}))
            if matches:self.open(matches[0])

    def poll(self):
        if time.monotonic()-self.last_poll<.2:return
        self.last_poll=time.monotonic()
        for job_id,principal in list(self.tracked.items()):
            try:self.runtime.get_job(principal,job_id)
            except Exception as exc:self.error=str(exc)

    def save(self):
        if self.test:return
        self.settings.parent.mkdir(parents=True,exist_ok=True)
        temp=self.settings.with_name(self.settings.name+'.'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps({'file':self.path,'scene':self.scene,'lighting':self.lighting,'keyboard':self.keyboard}),'utf-8')
        temp.replace(self.settings)

    def open(self,path):
        path=str(Path(path).resolve())
        if self.renderer:
            self.renderer.close();self.renderer=None
        self.path=path;self.error='';self.pending=True
        self.save()

    def tab(self):
        from ui_common import raw,tr,label
        ui=raw()
        flags=ui.TabItemFlags_.set_selected if self.pending or self.test else 0
        opened,_=ui.begin_tab_item(label('3D Viewer'),flags=flags)
        if not opened:return
        self.pending=False
        try:self.draw(ui,tr,label)
        finally:ui.end_tab_item()

    def draw(self,ui,tr,label):
        from imgui_bundle import immvision,portable_file_dialogs as pfd
        immvision.use_rgb_color_order()
        if ui.button(label('Open mesh')):
            self.dialog=pfd.open_file(tr('Open mesh'),str(self.root/'data'),[tr('3D meshes'),'*.glb *.gltf *.obj *.ply *.stl *.off'])
        ui.same_line()
        if ui.button(label('Frame mesh (F)')) and self.renderer:self.renderer.camera.reset()
        ui.same_line();_,self.wire=ui.checkbox(label('Wireframe'),self.wire)
        ui.same_line();_,self.grid=ui.checkbox(label('Ground / grid'),self.grid)
        ui.set_next_item_width(160);_,self.mode=ui.combo(label('Navigation'),self.mode,[tr('Orbit'),tr('Free camera')])
        ui.same_line();ui.set_next_item_width(150)
        changed,self.scene=ui.combo(label('Scene'),self.scene,[tr('Dark studio'),tr('Light studio'),tr('Outdoor')])
        if changed:self.save()
        ui.same_line();ui.set_next_item_width(180)
        changed,self.lighting=ui.combo(label('Lighting'),self.lighting,[tr('Studio: three lights'),tr('Sun'),tr('Camera light'),tr('Unlit')])
        if changed:self.save()
        if ui.collapsing_header(label('Lighting and controls')):
            ui.set_next_item_width(160)
            changed,self.keyboard=ui.combo(label('Keyboard layout'),self.keyboard,['WASD','ZQSD'])
            if changed:self.save()
            _,self.exposure=ui.slider_float(label('Exposure'),self.exposure,-6.,6.,'%.1f EV')
            if self.renderer:
                for i in range(1 if self.lighting in (1,2) else 3):
                    ui.push_id('light'+str(i));ui.text(tr(('Key light','Fill light','Rim light')[i]))
                    _,self.renderer.light_positions[i]=ui.drag_float3(label('Direction' if self.lighting==1 else 'Position'),self.renderer.light_positions[i],.05)
                    _,self.renderer.light_colors[i]=ui.color_edit3(label('Color'),self.renderer.light_colors[i])
                    _,self.renderer.light_energy[i]=ui.slider_float(label('Intensity'),self.renderer.light_energy[i],0.,20.)
                    ui.pop_id()
            ui.text_wrapped(tr('WASD / ZQSD or arrows: move. Space / Ctrl: up/down. Q/E (A/E on AZERTY): roll. Shift: faster. Alt: precision. F: frame mesh.'))
        ui.text_wrapped(tr('Left drag: orbit. Right drag: look. Middle drag or Shift+left: pan. Wheel: zoom. Double-click a surface: orbit around that point.'))
        if self.dialog is not None and self.dialog.ready(0):
            files=self.dialog.result();self.dialog=None
            if files:self.open(files[0])
        if not self.path:
            ui.text_wrapped(tr('Generate a mesh or open an existing file. Finished meshes open here automatically.'));return
        ui.text_disabled(Path(self.path).name)
        # Release the preview GPU context while this UI is running a model job.
        if self.tracked:
            if self.renderer:self.renderer.close();self.renderer=None
            ui.text_wrapped(tr('Preview paused while a job is running.'));return
        if self.renderer is None:
            try:
                from mesh_viewer import Viewer
                self.renderer=Viewer(self.path)
            except Exception as exc:self.error=str(exc)
        viewer=self.renderer
        if self.error or (viewer and viewer.error):
            ui.text_wrapped(tr('Preview failed: ')+(self.error or viewer.error));return
        if viewer is None or viewer.image is None:
            ui.text(tr('Loading 3D model...'));return
        avail=ui.get_content_region_avail()
        width=max(240,int(avail.x));height=max(220,int(avail.y)-38)
        scale=min(1.,1600/width,1100/height)
        viewer.size=(max(1,int(width*scale)),max(1,int(height*scale)))
        viewer.wireframe=self.wire;viewer.grid=self.grid;viewer.scene=self.scene;viewer.lighting=self.lighting;viewer.exposure=self.exposure
        mouse=immvision.image_display('##cytools-mesh-viewport',viewer.image,image_display_size=(width,height),refresh_image=True)
        hovered=mouse[0]>=0;io=ui.get_io()
        if ui.is_mouse_clicked(0) or ui.is_mouse_clicked(1) or ui.is_mouse_clicked(2):self.focused=hovered
        if hovered:
            ui.set_item_key_owner(ui.Key.mouse_wheel_y)
            if ui.is_mouse_double_clicked(0):viewer.pick(*mouse)
            if ui.is_mouse_down(2) or (ui.is_mouse_down(0) and io.key_shift):viewer.camera.pan(io.mouse_delta.x,io.mouse_delta.y,height)
            elif ui.is_mouse_down(1):viewer.camera.turn(io.mouse_delta.x,io.mouse_delta.y,in_place=True)
            elif ui.is_mouse_down(0):viewer.camera.turn(io.mouse_delta.x,io.mouse_delta.y,in_place=self.mode==1)
            if io.mouse_wheel:viewer.camera.zoom(io.mouse_wheel,free=self.mode==1)
        if (hovered or self.focused) and not io.want_text_input:
            keys=ui.Key
            down=lambda name: int(ui.is_key_down(getattr(keys,name)))
            forward='w' if self.keyboard==0 else 'z';left='a' if self.keyboard==0 else 'q';roll='q' if self.keyboard==0 else 'a'
            dt=min(io.delta_time,.1);speed=max(viewer.camera.distance,.00001)*dt*(3. if io.key_shift else .15 if io.key_alt else .7)
            viewer.camera.move((down('d')+down('right_arrow')-down(left)-down('left_arrow'))*speed,
                               (down('space')-int(io.key_ctrl))*speed,
                               (down(forward)+down('up_arrow')-down('s')-down('down_arrow'))*speed)
            viewer.camera.roll((down(roll)-down('e'))*dt)
            if ui.is_key_pressed(keys.f):viewer.camera.reset()
        viewer.request()
        ui.text(tr('Triangles: ')+str(viewer.triangles));ui.same_line()
        ui.text_disabled(tr('PBR preview. Mesh files are unchanged.'))
        if self.test:self.loaded_test_frames+=1

    def check_test(self,runner):
        if not self.test:return
        if self.renderer and self.renderer.error:raise RuntimeError(self.renderer.error)
        if self.error:raise RuntimeError(self.error)
        if time.monotonic()-self.test_started>45:raise RuntimeError('Mesh viewport test timed out')
        if self.loaded_test_frames>=8:
            report=self.root/'data/reports/mesh-viewer-test.json';report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text(json.dumps({'file':self.path,'triangles':self.renderer.triangles,'frames':self.renderer.frames,'viewportFrames':self.loaded_test_frames}),'utf-8')
            runner.app_shall_exit=True

    def close(self):
        if self.dialog:self.dialog.kill()
        if self.renderer:self.renderer.close();self.renderer=None


def install(runtime,root):
    global _instance
    config=Path(root)/'app/mesh-viewer.json'
    if not config.is_file():return None
    if not json.loads(config.read_text('utf-8')).get('enabled'):return None
    _instance=MeshPanel(runtime,root)
    return _instance


def draw_tab():
    if _instance is not None:_instance.tab()
