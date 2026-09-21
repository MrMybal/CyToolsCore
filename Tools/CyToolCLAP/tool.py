"""CyTools adapter: the model stays entirely outside CyToolsCore."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from cytools_core import Runtime, load_manifest, CyToolError
from cytools_core.transports.cli import run_cli
from cytools_core.workers import ProcessWorker
from model_config import ROOT, model_installed

def audio_root():
    return Path(os.environ.get('CYTOOLS_CLAP_AUDIO_ROOT',str(ROOT/'audio'))).resolve()

def resolve_audio(filename):
    root=audio_root()
    path=(root/filename).resolve()
    if not path.is_relative_to(root):
        raise CyToolError('AccessDenied','Audio must be inside CYTOOLS_CLAP_AUDIO_ROOT')
    if not path.is_file(): raise CyToolError('MissingInput','Audio file not found')
    if path.suffix.lower() not in ('.wav','.flac','.ogg','.mp3'):
        raise CyToolError('InvalidParameters','Supported extensions: WAV, FLAC, OGG, MP3')
    if path.stat().st_size>256*1024**2:
        raise CyToolError('InvalidParameters','Audio file exceeds 256 MiB')
    return path

def create_runtime(data_dir, **options):
    descriptor=load_manifest(ROOT/'CyTool.json')
    descriptor['backends'][0]['models'][0]['installed']=model_installed()
    runtime=Runtime(descriptor,data_dir,**options)
    worker=ProcessWorker([sys.executable,str(ROOT/'worker.py')],cwd=ROOT,idle_timeout=600)
    runtime.register_worker('clap',worker)

    def classify(context,parameters):
        if not model_installed():
            raise CyToolError('MissingModel','Run install_model.py before classification')
        for package in ('torch','transformers','numpy','scipy','soundfile'):
            if importlib.util.find_spec(package) is None:
                raise CyToolError('MissingDependency',f'Install CLAP requirements: {package} is missing')
        context.cancellation.check()
        source=resolve_audio(parameters['audio_file'])
        snapshot=context.path('input/audio'+source.suffix.lower())
        shutil.copyfile(source,snapshot)
        context.progress(5,currentStep='Audio snapshot ready')
        try:
            context.progress(10,currentStep='Loading CLAP and comparing audio/text on CPU')
            result=worker.run(context,{**parameters,'audio_file':str(snapshot)})
        finally:
            worker.release('All')
        if 'error' in result:
            error=result['error']
            raise CyToolError(error['code'],error['message'])
        context.cancellation.check()
        context.observe_resources({'ramBytes':result['worker_memory_bytes']},
            {'backend':'transformers-cpu','model':result['model_revision'],'measurement':result['memory_measurement']})
        result['report_file']=str(context.path('outputs/classification.json'))
        Path(result['report_file']).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        context.progress(100,currentStep='Classification ready; model worker stopped')
        return result

    runtime.register('classify_audio',classify)
    return runtime

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    argv=sys.argv[1:]
    if '--data-dir' not in argv:
        argv=['--data-dir',str(ROOT/'.cytools'),*argv]
    raise SystemExit(run_cli(create_runtime,argv))
