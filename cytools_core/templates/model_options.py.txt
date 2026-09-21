"""Tool-owned local model/LoRA catalogue and explicit per-job selections.

No ML/UI imports. The upstream Runtime still owns scheduling, identity and jobs.
"""
from contextvars import ContextVar
import copy
import hashlib
import json
import math
from pathlib import Path
import uuid

APP=Path(__file__).resolve().parent
ROOT=APP.parent
_selection=ContextVar('cytools-model-selection',default={})
def read(path,default):
    try:return json.loads(Path(path).read_text('utf-8-sig'))
    except (OSError,ValueError):return default
def capabilities():return read(APP/'model-capabilities.json',{'operations':{},'formats':{}})
def catalog():
    path=ROOT/'data/settings/model-library.json'
    if not path.exists():return {'schemaVersion':1,'models':[]}
    if path.stat().st_size>4*1024**2:raise ValueError('Model library exceeds 4 MiB')
    value=json.loads(path.read_text('utf-8-sig'))
    from cytools_core.schema import schema
    from jsonschema import Draft202012Validator
    Draft202012Validator(schema('model-library')).validate(value)
    if len({x['id'] for x in value['models']})!=len(value['models']):raise ValueError('Duplicate model IDs')
    return value
def save_catalog(value):
    path=ROOT/'data/settings/model-library.json';path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(value,indent=2,ensure_ascii=False),'utf-8');temp.replace(path)
def validate_asset(item):
    spec=capabilities()['formats'].get(item['format'])
    if spec is None:raise ValueError('Unsupported model format for this Tool')
    if spec.get('bases') and item.get('base') not in spec['bases']:raise ValueError('Select a matching base variant: '+', '.join(spec['bases']))
    path=Path(item['path']).resolve()
    if not path.exists():raise ValueError('Model path does not exist')
    if spec.get('suffix') and (not path.is_file() or path.suffix.lower()!=spec['suffix']):raise ValueError('Expected '+spec['suffix'])
    for name in spec.get('required',[]):
        if not (path/name).is_file():raise ValueError('Missing model file: '+name)
    for pattern in spec.get('weights',[]):
        if not any(path.glob(pattern)):raise ValueError('Missing weights: '+pattern)
    if spec.get('singleOnnx') and len(list(path.glob('*.onnx')))!=1:raise ValueError('Select a folder containing exactly one ONNX voice and its JSON config')
    if spec.get('singleOnnx'):
        voice=next(path.glob('*.onnx'))
        if not voice.with_suffix('.onnx.json').is_file():raise ValueError('Missing ONNX voice JSON config')
    if spec.get('suffix')=='.gguf':
        with path.open('rb') as stream:
            if stream.read(4)!=b'GGUF':raise ValueError('Invalid GGUF file')
    if spec.get('pipeline'):
        config=read(path/'model_index.json',{})
        if config.get('_class_name') not in spec['pipeline']:raise ValueError('Incompatible pipeline class')
    for filename,expected in spec.get('configMatch',{}).items():
        config=read(path/filename,{})
        if any(config.get(k)!=v for k,v in expected.items()):raise ValueError('Incompatible architecture config: '+filename)
    if spec.get('targetSizes'):
        target=read(path/'transformer/config.json',{}).get('target_size')
        if target!=spec['targetSizes'][item['base']]:raise ValueError('The checkpoint resolution does not match its base variant')
    if item.get('kind')=='lora':
        # SafeTensors header check, no pickle/code execution and no tensor allocation.
        with path.open('rb') as stream:
            length=int.from_bytes(stream.read(8),'little')
            if not 2<=length<=16*1024*1024:raise ValueError('Invalid SafeTensors header')
            header=json.loads(stream.read(length))
        keys=[k for k in header if k!='__metadata__']
        if not any('lora' in k.lower() for k in keys):raise ValueError('No LoRA tensors found')
    return path
def add_asset(name,path,format_id,base='',license_text='',source=''):
    spec=capabilities()['formats'].get(format_id,{})
    item={'id':uuid.uuid4().hex,'name':name.strip(),'path':str(Path(path).resolve()),'format':format_id,
          'kind':spec.get('kind','model'),'base':base,'license':license_text or 'Unknown','source':source,
          'validation':'Structure checked; inference compatibility must be verified with this derivative.'}
    if not item['name']:raise ValueError('A model name is required')
    validate_asset(item)
    from cytools_core.storage import RuntimeLock
    settings=ROOT/'data/settings';settings.mkdir(parents=True,exist_ok=True)
    lock=RuntimeLock(settings/'model-library.lock.sqlite')
    try:
        library=catalog();library['models'].append(item);save_catalog(library)
    finally:lock.close()
    return item
def resolve(parameters,operation):
    from cytools_core import CyToolError
    spec=capabilities()['operations'].get(operation,{})
    entries={i['id']:i for i in catalog()['models']};value={'operation':operation,'loras':[]}
    identifier=parameters.get('model_profile','')
    if identifier:
        item=entries.get(identifier)
        if not item or item['kind']!='model' or item['format'] not in spec.get('models',[]):raise CyToolError('InvalidModel','Model profile is incompatible with this operation')
        if item.get('base') and parameters.get(spec.get('baseParameter',''),item['base'])!=item['base']:raise CyToolError('InvalidModel','Select the matching base model')
        value['model']={**item,'path':str(validate_asset(item))}
    for adapter in parameters.get('loras',[]):
        item=entries.get(adapter['id'])
        if not item or item['kind']!='lora' or item['format'] not in spec.get('loras',[]):raise CyToolError('InvalidLoRA','LoRA is incompatible with this operation')
        strength=float(adapter['strength'])
        if not math.isfinite(strength) or not -4<=strength<=4:raise CyToolError('InvalidLoRA','Invalid adapter strength')
        value['loras'].append({**item,'path':str(validate_asset(item)),'strength':strength})
    return value
def current():return _selection.get()
def custom_path():return current().get('model',{}).get('path','')
def activate_worker(parameters):_selection.set(parameters.get('_cy_selection',{}))
def decorate_config(namespace,path_names=(),installed_names=(),missing_names=()):
    # Only functions specifically approved by the engine adapter are replaced.
    for name in path_names:
        original=namespace[name]
        def path(*a,_original=original,**kw):return Path(custom_path()) if custom_path() else _original(*a,**kw)
        namespace[name]=path
    for name in installed_names:
        original=namespace[name]
        def installed(*a,_original=original,**kw):return True if custom_path() else _original(*a,**kw)
        namespace[name]=installed
    for name in missing_names:
        original=namespace[name]
        def missing(*a,_original=original,**kw):return [] if custom_path() else _original(*a,**kw)
        namespace[name]=missing

def extend_manifest(manifest):
    manifest=copy.deepcopy(manifest)
    for op in manifest['operations']:
        spec=capabilities()['operations'].get(op['id'])
        if not spec:continue
        props=op['inputSchema'].setdefault('properties',{})
        if spec.get('models'):props['model_profile']={'type':'string','default':'','description':'ID from the local model library; empty uses the selected built-in model.'}
        if spec.get('loras'):props['loras']={'type':'array','maxItems':8,'default':[],'items':{'type':'object','additionalProperties':False,'required':['id','strength'],'properties':{'id':{'type':'string'},'strength':{'type':'number','minimum':-4,'maximum':4}}}}
    if capabilities().get('formats'):
        from cytools_core.schema import schema
        entry=schema('model-library')['properties']['models']['items']
        definitions=[('model_library_list','List compatible model formats, device capabilities and registered local model/LoRA references.',
                      {'type':'object','properties':{},'additionalProperties':False},
                      {'type':'object','properties':{'capabilities':{'type':'object'},'library':schema('model-library')},'required':['capabilities','library'],'additionalProperties':False}),
                     ('model_library_register','Register an existing compatible local model or LoRA by reference; does not download or copy weights. Registration is shared by clients of this local Tool.',
                      {'type':'object','properties':{key:{'type':'string','description':description} for key,description in {
                          'name':'Display name','path':'Absolute local path visible on the Tool host','format':'Format ID from model_library_list',
                          'base':'Compatible base variant ID','license':'License identifier or terms','source':'Original source URL or repository'}.items()},
                       'required':['name','path','format'],'additionalProperties':False},
                      {'type':'object','properties':{'model':entry},'required':['model'],'additionalProperties':False})]
        # Reserved extension operations are regenerated with the current contract.
        identifiers={definition[0] for definition in definitions}
        manifest['operations']=[op for op in manifest['operations'] if op['id'] not in identifiers]
        known={op['id'] for op in manifest['operations']}
        for identifier,description,inputs,outputs in definitions:
            if identifier not in known:
                manifest['operations'].append({'id':identifier,'name':identifier,'description':description,'inputSchema':inputs,'outputSchema':outputs,
                    'outputs':[{'id':key,'type':'Object','description':key} for key in outputs['properties']],
                    'platforms':copy.deepcopy(manifest.get('platforms',[])),
                    'canRunAsync':True,'canCancel':False,'supportsProgress':False,'supportedBackends':[],
                    'permissions':[],'resourceRequirements':{'ramBytes':64*1024**2,'cpuThreads':1}})
    return manifest

def __getattr__(name):
    if name not in ('Runtime','ProcessWorker'):raise AttributeError(name)
    from cytools_core import Runtime as CoreRuntime
    from cytools_core.workers import ProcessWorker as CoreWorker
    class Runtime(CoreRuntime):
        def __init__(self,descriptor,*a,**kw):
            super().__init__(extend_manifest(descriptor),*a,**kw)
            if capabilities().get('formats'):
                self.register('model_library_list',lambda context,parameters:{'capabilities':capabilities(),'library':catalog()})
                def register_asset(context,p):
                    from cytools_core import CyToolError
                    try:return {'model':add_asset(p['name'],p['path'],p['format'],p.get('base',''),p.get('license',''),p.get('source',''))}
                    except (ValueError,OSError) as exc:raise CyToolError('InvalidModel',str(exc)) from exc
                self.register('model_library_register',register_asset)
        def register(self,operation,handler,*,estimate=None):
            if operation not in capabilities()['operations']:return super().register(operation,handler,estimate=estimate)
            def invoke(context,parameters):
                selected=resolve(parameters,operation);token=_selection.set(selected);context.model_selection=selected
                try:
                    if selected.get('model') or selected['loras']:
                        context.path('outputs/model-selection.json').write_text(json.dumps(selected,indent=2),'utf-8')
                        context.log('Model selection: '+json.dumps(selected,ensure_ascii=False))
                    result=handler(context,parameters)
                    if selected.get('model') and isinstance(result,dict):
                        asset=selected['model']
                        for key,value in (('model_id','local:'+asset['id']),('model_repository',asset.get('source','')),('model_revision','local-unverified')):
                            if key in result:result[key]=value
                        report=result.get('report_file')
                        if report:
                            report_path=Path(report).resolve()
                            if report_path.is_relative_to(context.workspace.resolve()) and report_path.is_file():
                                data=json.loads(report_path.read_text('utf-8'))
                                if isinstance(data,dict):
                                    for key in ('model_id','model_repository','model_revision'):
                                        if key in data and key in result:data[key]=result[key]
                                    data['model_selection']=selected
                                    report_path.write_text(json.dumps(data,indent=2,ensure_ascii=False),'utf-8')
                    return result
                finally:_selection.reset(token)
            def resources(parameters,backend,model):
                selected=resolve(parameters,operation);token=_selection.set(selected)
                try:
                    result=copy.deepcopy(estimate(parameters,backend,model))
                    # Extra adapter memory is reserved before the job starts.
                    size=sum(Path(x['path']).stat().st_size*4 for x in selected['loras'])
                    result['ramBytes']=result.get('ramBytes',0)+size
                    if selected.get('model'):
                        path=Path(selected['model']['path'])
                        weights=path.stat().st_size if path.is_file() else sum(f.stat().st_size for f in path.rglob('*') if f.is_file() and f.suffix in ('.safetensors','.bin','.ckpt','.pth','.onnx'))
                        result['ramBytes']=max(result['ramBytes'],weights*2+2*1024**3+size)
                    for device in result.get('vramBytes',{}):result['vramBytes'][device]+=size
                    return result
                finally:_selection.reset(token)
            return super().register(operation,invoke,estimate=resources if estimate else None)

    class ProcessWorker(CoreWorker):
        def run(self,context,parameters):
            selected=getattr(context,'model_selection',{})
            return super().run(context,{**parameters,'_cy_selection':selected})

    globals().update(Runtime=Runtime,ProcessWorker=ProcessWorker)
    return globals()[name]

def apply_diffusers_loras(pipeline,parameters,transformer_only=False):
    selected=parameters.get('_cy_selection',{}).get('loras',[])
    if not selected:return
    names=[];weights=[]
    for index,item in enumerate(selected):
        name='cytools_'+str(index);path=Path(item['path'])
        if transformer_only:
            pipeline.transformer.load_lora_adapter(str(path.parent),weight_name=path.name,adapter_name=name,local_files_only=True)
        else:pipeline.load_lora_weights(str(path.parent),weight_name=path.name,adapter_name=name,local_files_only=True)
        targets=[getattr(pipeline,component,None) for component in ('transformer','text_encoder','text_encoder_2')]
        if not any(name in getattr(target,'peft_config',{}) for target in targets if target is not None):raise ValueError('The adapter contains no compatible LoRA keys for this engine')
        names.append(name);weights.append(item['strength'])
    if transformer_only:pipeline.transformer.set_adapters(names,weights=weights)
    else:pipeline.set_adapters(names,adapter_weights=weights)

def cli():
    import argparse
    parser=argparse.ArgumentParser(description='Local CyTools model library (references only)')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('list');commands.add_parser('capabilities')
    add=commands.add_parser('add');add.add_argument('--name',required=True);add.add_argument('--path',required=True);add.add_argument('--format',required=True);add.add_argument('--base',default='');add.add_argument('--license',default='Unknown');add.add_argument('--source',default='')
    args=parser.parse_args()
    result=catalog() if args.command=='list' else capabilities() if args.command=='capabilities' else add_asset(args.name,args.path,args.format,args.base,args.license,args.source)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':cli()
