"""Create a working standalone tool without copying runtime internals."""
import argparse
import json
import re
import sys
from pathlib import Path
from importlib.resources import files
from .schema import load_manifest


def docs_path():
    checkout=Path(__file__).resolve().parents[1]/'Docs'
    installed=Path(sys.prefix)/'share'/'cytools-core'/'Docs'
    return checkout if (checkout/'AgentGuide.md').is_file() else installed


def create_project(path, name, tool_id, *, desktop=False, mesh_viewer=False):
    if mesh_viewer and not desktop: raise ValueError('Mesh viewer requires --desktop')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,60}',name): raise ValueError('Name must be an identifier (example: CyToolExample)')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,127}',tool_id): raise ValueError('Invalid tool ID')
    root=Path(path).resolve()
    if root.exists() and any(root.iterdir()): raise ValueError('Destination must be empty; no files were overwritten')
    root.mkdir(parents=True,exist_ok=True)
    if desktop:
        app = create_project(root/'app', name, tool_id)
        for directory in ('data', 'runtime'):
            (root/directory).mkdir()
        (app/'locales').mkdir()
        (app/'generation-config.schema.json').write_text(files('cytools_core').joinpath('schemas','generation-config.schema.json').read_text('utf-8'),encoding='utf-8')
        for template, destination in (
            ('desktop.py.txt', app/'desktop.py'),
            ('ui_common.py.txt', app/'ui_common.py'),
            ('generation_config.py.txt', app/'generation_config.py'),
            ('installation_ui.py.txt', app/'installation_ui.py'),
            ('mesh_viewer.py.txt', app/'mesh_viewer.py'),
            ('standalone_log.py.txt', app/'standalone_log.py'),
            ('model_options.py.txt', app/'model_options.py'),
            ('model_options_ui.py.txt', app/'model_options_ui.py'),
            ('advanced_ui.py.txt', app/'advanced_ui.py'),
            ('mesh_viewer_ui.py.txt', app/'mesh_viewer_ui.py'),
            ('ui_translations.json.txt', app/'locales/ui.json'),
            ('launcher.cpp.txt', app/'launcher.cpp'),
            ('build_launcher.ps1.txt', app/'build_launcher.ps1'),
            ('desktop_launch.cmd.txt', root/'Lancer.cmd'),
            ('desktop_launch.sh.txt', root/(name+'.sh')),
            ('desktop_readme.md.txt', root/'LISEZ-MOI.md')):
            text = files('cytools_core').joinpath('templates', template).read_text('utf-8')
            destination.write_text(text.replace('__TOOL_NAME__', name), encoding='utf-8')
        launcher = root/(name+'.sh')
        launcher.chmod(launcher.stat().st_mode | 0o111)
        with (app/'requirements.txt').open('a', encoding='utf-8') as stream:
            stream.write('imgui-bundle==1.92.900\n')
            if mesh_viewer: stream.write('moderngl==5.12.0\ntrimesh>=4.4,<6\nnumpy>=1.26,<3\nPillow>=10,<13\n')
        if mesh_viewer:
            (app/'mesh-viewer.json').write_text('{"enabled": true}\n',encoding='utf-8')
        manifest = json.loads((app/'CyTool.json').read_text('utf-8'))
        manifest['interfaces'].append('ImGui')
        for platform in manifest['platforms']:
            platform['status'] = 'Experimental'
        manifest['executable'] = 'runtime/python/Scripts/python.exe app/tool.py'
        manifest['standaloneExecutable'] = name+'.exe'
        manifest['distributionStatus'] = 'Scaffold: build launcher and validate before delivery'
        (app/'CyTool.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        tool = (app/'tool.py').read_text('utf-8')
        tool = 'import sys\nfrom installation_ui import configure as configure_storage\nconfigure_storage()\n'+tool
        tool = tool.replace('    return runtime', "    from cytools_core.shared_installation import register_operations\n    register_operations(runtime, Path(__file__).resolve().parents[1])\n    return runtime")
        tool = tool.replace('raise SystemExit(run_cli(create_runtime))',
            "argv = sys.argv[1:]\n    if '--data-dir' not in argv:\n        argv = ['--data-dir', str(Path(__file__).resolve().parents[1]/'data/jobs'), *argv]\n    raise SystemExit(run_cli(create_runtime, argv))")
        (app/'tool.py').write_text(tool, encoding='utf-8')
        return root
    manifest={
        'schemaVersion':1,'protocolVersion':'1.0','id':tool_id,'name':name,'version':'0.1.0',
        'description':'Standalone '+name,'vendor':'Cyberalien','author':'Cyberalien','executable':'python tool.py',
        'categories':['utility'],'tags':[],'capabilities':['jobs','cancellation'],'backends':[],
        'platforms':[{'os':os,'architecture':arch,'status':status,'computeBackends':['CPU']} for os,arch,status in
                     [('Windows','x64','Supported'),('Linux','x64','Supported'),('macOS','ARM64','Experimental')]],
        'interfaces':['Native','CLI','JSONL','HTTP','MCP'],'runtimeRequirements':[],
        'concurrency':{'policy':'Sequential','maxWorkers':1},
        'operations':[{'id':'echo','name':'Echo','description':'Return the supplied text.',
            'inputSchema':{'type':'object','properties':{'text':{'type':'string','description':'Text to return','x-cy-kind':'MultilineString'}},'required':['text'],'additionalProperties':False},
            'outputSchema':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False},
            'resourceRequirements':{'ramBytes':1048576},'supportedBackends':[],'permissions':[],
            'canRunAsync':True,'canCancel':True,'supportsProgress':False}]
    }
    (root/'CyTool.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    for filename in ('tool.py','test_tool.py','AGENTS.md','README.md'):
        text=files('cytools_core').joinpath('templates',filename+'.txt').read_text('utf-8')
        (root/filename).write_text(text.replace('__TOOL_NAME__',name),encoding='utf-8')
    (root/'params.json').write_text('{"text": "Hello CyTools"}\n',encoding='utf-8')
    (root/'.gitignore').write_text('.venv/\n.cytools/\n__pycache__/\n.pytest_cache/\n',encoding='utf-8')
    (root/'requirements.txt').write_text('# Install the CyToolsCore wheel or local checkout first.\ncytools-core==0.9.0\n',encoding='utf-8')
    guide=docs_path()/'AgentGuide.md'
    if guide.is_file():
        (root/'Docs').mkdir()
        for document in docs_path().glob('*.md'):
            (root/'Docs'/document.name).write_text(document.read_text('utf-8'),encoding='utf-8')
        text=re.sub(r'\]\(([A-Za-z]+\.md)\)',r'](Docs/\1)',guide.read_text('utf-8'))
        (root/'CyToolsGuide.md').write_text(text,encoding='utf-8')
    return root


def main():
    parser=argparse.ArgumentParser(description='CyTools SDK tools')
    sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('new')
    create.add_argument('path')
    create.add_argument('--name',required=True)
    create.add_argument('--id',required=True)
    create.add_argument('--desktop',action='store_true',help='Clean app/data/runtime layout and optional ImGui frontend scaffold')
    create.add_argument('--mesh-viewer',action='store_true',help='Enable interactive mesh viewport (requires --desktop)')
    validate=sub.add_parser('validate')
    validate.add_argument('manifest')
    sub.add_parser('docs',help='Print the SDK documentation directory')
    args=parser.parse_args()
    if args.command=='new': print(create_project(args.path,args.name,args.id,desktop=args.desktop,mesh_viewer=args.mesh_viewer))
    elif args.command=='docs': print(docs_path())
    else:
        document=load_manifest(args.manifest)
        print(json.dumps({'valid':True,'toolId':document['id'],'schemaVersion':document['schemaVersion']}))

if __name__=='__main__': main()
