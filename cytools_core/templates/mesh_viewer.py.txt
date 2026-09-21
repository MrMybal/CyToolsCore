"""Optional mesh preview, owned by the Tool. No inference or Core imports.

OpenGL resources belong exclusively to the render thread. Model files are read
only; normalized coordinates, lighting and camera changes affect the preview.
"""
import math
from pathlib import Path
import threading
import numpy as np

FORMATS = {'.glb', '.gltf', '.obj', '.ply', '.stl', '.off'}


def rotation(axis, angle):
    axis = np.asarray(axis, dtype=float)
    axis /= max(np.linalg.norm(axis), 1e-15)
    x,y,z = axis; c,s = math.cos(angle), math.sin(angle)
    skew = np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return c*np.eye(3)+(1-c)*np.outer(axis,axis)+s*skew


class Camera:
    def __init__(self): self.reset()

    def reset(self):
        self.basis = rotation([0,1,0],math.radians(30)) @ rotation([1,0,0],math.radians(-12))
        self.pivot = np.zeros(3); self.distance = 3.2
        self.eye = self.pivot + self.basis[:,2]*self.distance

    def turn(self, dx, dy, *, in_place=False):
        self.basis = rotation(self.basis[:,1], -dx*.006) @ self.basis
        self.basis = rotation(self.basis[:,0], -dy*.006) @ self.basis
        # Re-orthogonalize to avoid accumulating drift after long editing sessions.
        u,_,v = np.linalg.svd(self.basis); self.basis = u@v
        if in_place: self.pivot = self.eye-self.basis[:,2]*self.distance
        else: self.eye = self.pivot+self.basis[:,2]*self.distance

    def roll(self, angle):
        self.basis = rotation(self.basis[:,2],angle) @ self.basis

    def move(self, right, up, forward):
        shift = self.basis @ np.array([right,up,-forward])
        self.eye += shift; self.pivot += shift

    def pan(self, dx, dy, height):
        scale = 2*self.distance*math.tan(math.radians(45)/2)/max(height,1)
        self.move(-dx*scale,dy*scale,0)

    def zoom(self, wheel, *, free=False):
        if free:
            self.move(0,0,wheel*max(self.distance*.12,1e-6))
        else:
            # Numeric guard only: no object-sized minimum or UI distance limit.
            self.distance = float(np.clip(self.distance*math.exp(-max(-50,min(50,wheel))*.18),1e-8,1e12))
            self.eye = self.pivot+self.basis[:,2]*self.distance

    def focus(self, point):
        point = np.asarray(point,dtype=float); back = self.eye-point
        distance = np.linalg.norm(back)
        if distance<1e-10: return
        back /= distance
        right = np.cross(self.basis[:,1],back)
        if np.linalg.norm(right)<1e-8: return
        right /= np.linalg.norm(right)
        self.basis = np.column_stack((right,np.cross(back,right),back))
        self.pivot = point; self.distance = float(distance)

    def matrices(self, aspect):
        view = np.eye(4); view[:3,:3] = self.basis.T
        view[:3,3] = -self.basis.T @ self.eye
        # Close inspection uses a small near plane; the far plane follows the camera.
        near = max(1e-10,min(.01,self.distance*.001))
        far = max(100.,float(np.linalg.norm(self.eye))+100.)
        f = 1/math.tan(math.radians(45)/2)
        projection = np.zeros((4,4)); projection[0,0] = f/aspect; projection[1,1] = f
        projection[2,2] = (far+near)/(near-far); projection[2,3] = 2*far*near/(near-far)
        projection[3,2] = -1
        return projection@view


VERTEX = '''#version 330
in vec3 position; in vec3 normal; in vec2 uv; in vec4 vertex_color;
uniform mat4 mvp;
out vec3 world; out vec3 n; out vec2 st; out vec4 vc;
void main(){world=position;n=normal;st=uv;vc=vertex_color;gl_Position=mvp*vec4(position,1.);}
'''

FRAGMENT = '''#version 330
in vec3 world; in vec3 n; in vec2 st; in vec4 vc; out vec4 frag;
uniform sampler2D albedo, mr_map, normal_map, emissive_map, ao_map;
uniform vec4 factor;
uniform vec3 emissive_factor, eye, ambient;
uniform float metallic_factor, roughness_factor, exposure, alpha_cutoff;
uniform int alpha_mode, has_normal, unlit, ground, grid;
uniform vec3 light_pos[3], light_color[3]; uniform int directional;
const float PI=3.14159265359;
void main(){
    vec4 base=texture(albedo,st)*factor*vc;
    if(alpha_mode==1 && base.a<alpha_cutoff) discard;
    vec3 color=pow(max(base.rgb,vec3(0)),vec3(2.2));
    vec3 N=normalize(n); if(!gl_FrontFacing) N=-N;
    if(has_normal==1){
        vec3 q1=dFdx(world),q2=dFdy(world); vec2 t1=dFdx(st),t2=dFdy(st);
        vec3 T=q1*t2.y-q2*t1.y;
        if(length(T)>0.000001){T=normalize(T-N*dot(N,T));
            vec3 B=normalize(cross(N,T))*sign(t1.x*t2.y-t1.y*t2.x);
            N=normalize(mat3(T,B,N)*(texture(normal_map,st).xyz*2.-1.));}
    }
    if(ground==1 && grid==1){
        vec2 g=abs(fract(world.xz*2.-.5)-.5)/max(fwidth(world.xz*2.),vec2(.00001));
        color*=mix(.65,1.,min(min(g.x,g.y),1.));
    }
    float metal=clamp(metallic_factor*texture(mr_map,st).b,0.,1.);
    float rough=clamp(roughness_factor*texture(mr_map,st).g,.045,1.);
    vec3 V=normalize(eye-world);float nv=max(dot(N,V),.0001);
    vec3 f0=mix(vec3(.04),color,metal); vec3 result=vec3(0);
    for(int i=0;i<3;i++){
        vec3 delta=light_pos[i]-world;
        vec3 L=directional==1 ? normalize(light_pos[i]) : normalize(delta);
        float attenuation=directional==1 ? 1. : 8./max(dot(delta,delta),.25);
        vec3 H=normalize(V+L);float nl=max(dot(N,L),0.);
        float nh=max(dot(N,H),0.);float hv=max(dot(H,V),0.);
        float a=rough*rough;float a2=a*a;float denom=nh*nh*(a2-1.)+1.;
        float D=a2/max(PI*denom*denom,.000001);
        float k=(rough+1.)*(rough+1.)/8.;
        float G=(nv/(nv*(1.-k)+k))*(nl/(nl*(1.-k)+k));
        vec3 F=f0+(1.-f0)*pow(1.-hv,5.);
        vec3 spec=D*G*F/max(4.*nv*nl,.0001);
        result+=((1.-F)*(1.-metal)*color/PI+spec)*light_color[i]*nl*attenuation;
    }
    // Approximate environment fill; no claim of HDR image-based lighting or shadows.
    result+=ambient*(color*(1.-metal)+f0*(.3+.7*(1.-rough)))*texture(ao_map,st).r;
    result+=pow(texture(emissive_map,st).rgb,vec3(2.2))*emissive_factor;
    if(unlit==1) result=color;
    result*=exp2(exposure);result=result/(result+vec3(1.));
    frag=vec4(pow(max(result,vec3(0)),vec3(1./2.2)),alpha_mode==2?base.a:1.);
}
'''


def load_scene(path):
    import trimesh
    from trimesh.resolvers import FilePathResolver
    path = Path(path).resolve()
    if path.suffix.lower() not in FORMATS: raise ValueError('Supported meshes: GLB, glTF, OBJ, PLY, STL, OFF')
    if not path.is_file(): raise FileNotFoundError(str(path))
    class LocalResolver(FilePathResolver):
        def namespaced(self,namespace):
            candidate=(Path(self.parent)/str(namespace)).resolve()
            if not candidate.is_relative_to(path.parent):raise ValueError('Assets outside the mesh folder')
            return LocalResolver(str(candidate))

        def get(self, name):
            candidate=(Path(self.parent)/str(name)).resolve()
            if not candidate.is_relative_to(path.parent): raise ValueError('Texture/buffer outside the mesh folder')
            return super().get(name)
    resolver=LocalResolver(str(path.parent))
    loader=getattr(trimesh,'load_scene',None)
    scene=(loader(path,process=False,allow_remote=False,resolver=resolver) if loader else
           trimesh.load(str(path),force='scene',process=False,resolver=resolver))
    if not scene.geometry or scene.bounds is None: raise ValueError('No mesh geometry in file')
    return scene


class Viewer:
    def __init__(self,path):
        self.path=str(Path(path).resolve()); self.camera=Camera()
        self.image=None;self.depth=None;self.frame_matrix=None;self.error='';self.triangles=0;self.frames=0
        self.size=(900,600);self.wireframe=False;self.grid=True;self.scene=0;self.lighting=0;self.exposure=0.
        self.light_positions=[[3.,4.,4.],[-4.,2.,2.],[1.,3.,-4.]]
        self.light_colors=[[1.,.9,.8],[.65,.8,1.],[1.,1.,1.]]
        self.light_energy=[5.,2.,6.]
        self._condition=threading.Condition();self._request=None;self._stop=False;self._last=None
        self.thread=threading.Thread(target=self._run,name='CyToolsMeshPreview',daemon=True)
        self.thread.start();self.request()

    def request(self):
        width,height=self.size
        state=(tuple(self.camera.eye),tuple(self.camera.matrices(width/height).ravel()),width,height,
               self.wireframe,self.grid,self.scene,self.lighting,self.exposure,
               tuple(tuple(v) for v in self.light_positions),tuple(tuple(v) for v in self.light_colors),tuple(self.light_energy))
        with self._condition:
            if state!=self._last:
                self._last=state;self._request=state;self._condition.notify()

    def pick(self,x,y):
        # A coherent immutable frame tuple is published after the render finishes.
        frame=getattr(self,'_frame',None)
        if frame is None:return
        _,depth,matrix=frame;h,w=depth.shape;x=int(x);y=int(y)
        if not(0<=x<w and 0<=y<h) or depth[y,x]>=.999999:return
        point=np.linalg.inv(matrix)@np.array([2*(x+.5)/w-1,1-2*(y+.5)/h,2*float(depth[y,x])-1,1.])
        if abs(point[3])>1e-15:self.camera.focus(point[:3]/point[3]);self.request()

    def close(self):
        with self._condition:self._stop=True;self._condition.notify()
        self.thread.join(timeout=10)
        return not self.thread.is_alive()

    def _run(self):
        ctx=None
        try:
            import moderngl
            from PIL import Image
            scene=load_scene(self.path)
            center=scene.bounds.mean(axis=0);radius=max(float(np.linalg.norm(scene.bounds[1]-scene.bounds[0])/2),1e-12)
            ctx=moderngl.create_standalone_context(require=330)
            program=ctx.program(vertex_shader=VERTEX,fragment_shader=FRAGMENT)
            for unit,name in enumerate(('albedo','mr_map','normal_map','emissive_map','ao_map')):program[name].value=unit
            resources=[];draws=[]
            def texture(image,default):
                image=Image.new('RGBA',(1,1),default) if image is None else image.convert('RGBA')
                image=image.copy();image.thumbnail((4096,4096))
                image=image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                tex=ctx.texture(image.size,4,image.tobytes());tex.build_mipmaps();resources.append(tex)
                return tex
            def prepare(vertices,normal,uv,colors,faces,material,ground=False):
                data=np.column_stack((vertices,normal,uv,colors)).astype('f4')
                vbo=ctx.buffer(data.tobytes());ibo=ctx.buffer(np.asarray(faces,dtype='u4').tobytes())
                vao=ctx.vertex_array(program,[(vbo,'3f 3f 2f 4f','position','normal','uv','vertex_color')],ibo)
                resources.extend((vao,vbo,ibo))
                base=getattr(material,'baseColorTexture',None)
                if base is None:base=getattr(material,'image',None)
                normal_map=getattr(material,'normalTexture',None)
                maps=[texture(base,(255,255,255,255)),texture(getattr(material,'metallicRoughnessTexture',None),(255,255,255,255)),
                      texture(normal_map,(128,128,255,255)),texture(getattr(material,'emissiveTexture',None),(255,255,255,255)),
                      texture(getattr(material,'occlusionTexture',None),(255,255,255,255))]
                factor=getattr(material,'baseColorFactor',None)
                factor=np.ones(4) if factor is None else np.asarray(factor,dtype=float)/255.
                metallic=getattr(material,'metallicFactor',None);roughness=getattr(material,'roughnessFactor',None)
                emissive=getattr(material,'emissiveFactor',None)
                return {'vao':vao,'maps':maps,'factor':tuple(factor),'metallic':0. if metallic is None else float(metallic),
                        'roughness':.7 if roughness is None else float(roughness),'normal':int(normal_map is not None),
                        'emissive':tuple(np.zeros(3) if emissive is None else emissive),
                        'alpha':{'MASK':1,'BLEND':2}.get(getattr(material,'alphaMode','OPAQUE'),0),
                        'cutoff':float(getattr(material,'alphaCutoff',None) or .5),'ground':int(ground),
                        'center':np.asarray(vertices).mean(axis=0)}
            for node in scene.graph.nodes_geometry:
                if self._stop:return
                transform,name=scene.graph[node];mesh=scene.geometry[name]
                if not hasattr(mesh,'faces') or not len(mesh.faces):continue
                vertices=(np.asarray(mesh.vertices)@transform[:3,:3].T+transform[:3,3]-center)/radius
                normal=getattr(getattr(mesh,'_cache',None),'cache',{}).get('vertex_normals')
                if normal is None:
                    # NumPy fallback avoids adding SciPy just for viewport normals.
                    normal=np.zeros_like(np.asarray(mesh.vertices),dtype=float)
                    triangles=np.asarray(mesh.vertices)[mesh.faces]
                    face_normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
                    for column in range(3):np.add.at(normal,mesh.faces[:,column],face_normals)
                normal=np.asarray(normal)@np.linalg.pinv(transform[:3,:3])
                normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
                uv=getattr(mesh.visual,'uv',None)
                if uv is None:uv=np.zeros((len(vertices),2))
                colors=np.ones((len(vertices),4))
                if getattr(mesh.visual,'kind','') in ('vertex','face'):
                    colors=np.asarray(mesh.visual.to_color().vertex_colors if hasattr(mesh.visual,'to_color') else mesh.visual.vertex_colors,dtype=float)/255.
                material=getattr(mesh.visual,'material',None)
                if material is not None and hasattr(material,'to_pbr'):material=material.to_pbr()
                draws.append(prepare(vertices,normal,uv,colors,mesh.faces,material));self.triangles+=len(mesh.faces)
            if not draws:raise ValueError('No triangle mesh in file')
            floor_y=float((scene.bounds[0,1]-center[1])/radius)-.002
            floor=prepare([[-50,floor_y,-50],[-50,floor_y,50],[50,floor_y,50],[50,floor_y,-50]],
                          [[0,1,0]]*4,[[0,0]]*4,[[.55,.55,.55,1]]*4,[[0,1,2],[0,2,3]],None,True)
            ctx.enable(moderngl.DEPTH_TEST|moderngl.BLEND)
            ctx.blend_func=moderngl.SRC_ALPHA,moderngl.ONE_MINUS_SRC_ALPHA
            fbo=None;dimensions=None
            while True:
                with self._condition:
                    self._condition.wait_for(lambda:self._stop or self._request is not None)
                    if self._stop:return
                    state=self._request;self._request=None
                eye,matrix,w,h,wire,grid,environment,lighting,exposure,positions,colors,energy=state
                if dimensions!=(w,h):
                    if fbo:
                        for attachment in fbo.color_attachments:attachment.release()
                        fbo.depth_attachment.release();fbo.release()
                    fbo=ctx.framebuffer([ctx.texture((w,h),4)],ctx.depth_texture((w,h)));dimensions=(w,h)
                fbo.use();ctx.viewport=(0,0,w,h)
                bg=[(.035,.045,.065),(.65,.68,.72),(.33,.48,.65)][environment]
                fbo.clear(*bg,1.,depth=1.)
                program['mvp'].write(np.asarray(matrix).reshape(4,4).T.astype('f4').tobytes())
                program['eye'].value=eye;program['exposure'].value=exposure
                program['ambient'].value=[(.14,.16,.2),(.35,.35,.35),(.25,.3,.38)][environment]
                program['unlit'].value=int(lighting==3);program['directional'].value=int(lighting==1)
                pos=np.asarray(positions,dtype='f4');power=np.asarray(colors,dtype='f4')*np.asarray(energy,dtype='f4')[:,None]
                if lighting==1:power[1:]=0
                if lighting==2:pos[0]=eye;power[0]=[4,4,4];power[1:]=0
                program['light_pos'].write(pos.tobytes());program['light_color'].write(power.tobytes())
                def draw(item):
                    for unit,tex in enumerate(item['maps']):tex.use(unit)
                    program['factor'].value=item['factor'];program['metallic_factor'].value=item['metallic']
                    program['roughness_factor'].value=item['roughness'];program['has_normal'].value=item['normal']
                    program['emissive_factor'].value=item['emissive'];program['alpha_mode'].value=item['alpha']
                    program['alpha_cutoff'].value=item['cutoff'];program['ground'].value=item['ground'];program['grid'].value=int(grid)
                    item['vao'].render(moderngl.TRIANGLES)
                ctx.wireframe=False
                if grid:draw(floor)
                ctx.wireframe=wire
                ordered=sorted(draws,key=lambda d:(d['alpha']==2,-float(np.linalg.norm(d['center']-np.asarray(eye)))))
                for item in ordered:draw(item)
                image=np.frombuffer(fbo.read(components=3,alignment=1),dtype=np.uint8).reshape(h,w,3)
                depth=np.frombuffer(fbo.depth_attachment.read(),dtype=np.float32).reshape(h,w)
                image=np.flipud(image).copy();depth=np.flipud(depth).copy()
                self._frame=(image,depth,np.asarray(matrix).reshape(4,4));self.image=image;self.frames+=1
        except Exception as exc:self.error=type(exc).__name__+': '+str(exc)
        finally:
            if ctx:ctx.release()
