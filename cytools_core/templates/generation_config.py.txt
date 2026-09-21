"""Versioned generation recipes, without UI or model imports."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid
from cytools_core import validate_parameters

def secret_key(key):
    key=re.sub(r'[^a-z]','',str(key).lower())
    return any(s in key for s in ('password','passwd','motdepasse','jeton','accesstoken','authtoken','apikey','credential','authorization')) or key in ('token','secret') or key.startswith('tokenmasked')

def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items() if not secret_key(k)}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if value is None or isinstance(value,(str,int,float,bool)): return value
    raise ValueError('Configuration contains a non-JSON value')

def recipe(manifest,operation,parameters,*,backend='',model='',ui_state=None,job_id=None):
    descriptor=next((o for o in manifest['operations'] if o['id']==operation),None)
    if descriptor is None: raise ValueError('Unknown operation')
    parameters=clean(parameters)
    try:
        parameters=validate_parameters(parameters,descriptor['inputSchema']); valid=True; reason=''
    except Exception as exc: valid=False; reason=str(exc)
    return {'format':'cytools-generation-config','schemaVersion':1,'toolId':manifest['id'],
            'toolVersion':manifest['version'],'createdAt':datetime.now(timezone.utc).isoformat(),
            'operationId':operation,'parameters':parameters,'backendId':backend,'modelId':model,
            'validParameters':valid,'validationMessage':reason,'uiState':clean(ui_state or {}),'jobId':job_id}

def save(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temp.replace(path)
    return path

def load(path,manifest):
    path=Path(path)
    if path.stat().st_size>4*1024**2: raise ValueError('Configuration is larger than 4 MiB')
    value=json.loads(path.read_text('utf-8-sig'))
    from jsonschema import Draft202012Validator
    schema_path=Path(__file__).with_name('generation-config.schema.json')
    Draft202012Validator(json.loads(schema_path.read_text('utf-8'))).validate(value)
    if value.get('format')!='cytools-generation-config' or value.get('schemaVersion')!=1: raise ValueError('Unsupported configuration format/version')
    if value.get('toolId')!=manifest['id']: raise ValueError('Configuration belongs to a different Tool')
    if not isinstance(value.get('parameters'),dict) or not isinstance(value.get('uiState',{}),dict): raise ValueError('Invalid configuration fields')
    if not any(o['id']==value.get('operationId') for o in manifest['operations']): raise ValueError('Unknown operation')
    # A draft is loadable, but replay always validates the current operation schema.
    return clean(value)

def submit_config(runtime,principal,session,path):
    value=load(path,runtime.descriptor)
    return runtime.submit(principal,session,value['operationId'],value['parameters'],
                          backend_id=value.get('backendId',''),model_id=value.get('modelId',''))

def cli():
    import argparse
    import sys
    if sys.stdout: sys.stdout.reconfigure(encoding='utf-8')
    from tool import create_runtime
    parser=argparse.ArgumentParser(description='Replay a CyTools generation configuration')
    parser.add_argument('configuration'); parser.add_argument('--data-dir',required=True)
    parser.add_argument('--timeout',type=float,default=3600)
    args=parser.parse_args()
    with create_runtime(args.data_dir) as runtime:
        actor=runtime.authenticate(runtime.create_client('Configuration replay')['token'])
        session=runtime.create_session(actor, temporary=False)['sessionId']
        job=submit_config(runtime,actor,session,args.configuration)
        result=runtime.wait(actor,job['jobId'],timeout=args.timeout)
        print(json.dumps(result,ensure_ascii=False))
        return 0 if result['state']=='Completed' else 1

if __name__=='__main__': raise SystemExit(cli())
