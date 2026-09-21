"""Maintainer utility to regenerate the initial v1 contract; shipped JSON is canonical."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'cytools_core' / 'schemas'
S = {'type': 'string'}
B = {'type': 'boolean'}
N = {'type': 'number', 'minimum': 0}
I = {'type': 'integer', 'minimum': 0}
ID = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_.-]{0,127}$'}
def array(items): return {'type': 'array', 'items': items}
def enum(*items): return {'type': 'string', 'enum': list(items)}
def obj(props, required=()): return {'type': 'object', 'properties': props, 'required': list(required)}
def ref(name): return {'$ref': '#/$defs/' + name}
defs = {}
defs['parameter'] = obj({'x-cy-kind':enum('String','MultilineString','Boolean','Integer','Float','Enum','File','Files','Directory','Image','Audio','Video','Object','Array','Reference','Seed'),
    'x-cy-ui':obj({'help':S,'advanced':B,'hidden':B,'runtimeGenerated':B,'step':N,'visibleWhen':{'type':'object'}}),
    'properties':{'type':'object','additionalProperties':ref('parameter')},
    '$defs':{'type':'object','additionalProperties':ref('parameter')},
    'items':{'anyOf':[ref('parameter'),B]}, 'allOf':array(ref('parameter')), 'anyOf':array(ref('parameter')),
    'oneOf':array(ref('parameter')),'if':ref('parameter'),'then':ref('parameter'),'else':ref('parameter')})
defs['memory'] = obj({k: N for k in ['minimum', 'recommended', 'estimatedLoaded', 'estimatedRuntime', 'estimatedPeak', 'observedPeak']})
defs['platform'] = obj({'os': S, 'architecture': S, 'status': enum('Supported','Experimental','Unsupported','Unknown'), 'minimumOSVersion': S,
    'computeBackends': array(S), 'notes': S, 'tested': array(obj({'osVersion': S, 'device': S, 'driver': S, 'runtime': S, 'date': S, 'status': S}))}, ['os','architecture','status'])
defs['resources'] = obj({'ramBytes': N, 'vramBytes': {'type':'object','additionalProperties':N}, 'diskBytes': N,
    'temporaryDiskBytes': N, 'cpuThreads': I, 'networkRequired': B, 'durationSeconds': N,
    'preferredDevice': S, 'fallbackOptions': array(obj({'status': S, 'parameters': {'type':'object'}, 'description': S})),
    'cpu': obj({'supported': B, 'minimumCores': I, 'recommendedCores': I, 'minimumThreads': I, 'recommendedThreads': I, 'instructions': array(S)}),
    'gpu': obj({'supported': B, 'required': B, 'vendors': array(S), 'computeBackends': array(S)}),
    'ram': ref('memory'), 'vram': ref('memory')})
defs['profile'] = obj({**{k:S for k in ['toolVersion','backendId','modelVersion','platform','computeBackend','precision','quantization','parametersProfile']}, 'estimated': ref('resources'), 'observed':ref('resources')})
defs['dependency'] = obj({'id': ID, 'version': S, 'required': B, 'source': S, 'installed': B, 'path': S,
    'executable': S, 'platforms': array(ref('platform'))}, ['id'])
defs['modelFile'] = obj({'path': S, 'url': S, 'sha256': {'type':'string','pattern':'^[a-fA-F0-9]{64}$'}, 'sizeBytes': I, 'etag': S, 'revision': S}, ['path'])
defs['model'] = obj({'id': ID, 'name': S, 'version': S, 'source': S, 'license': S, 'location':enum('Local','Remote','Hybrid'),
    'runsLocally': B, 'installed': B, 'files': array(ref('modelFile')), 'downloadSize': I, 'installedSize': I,
    'platforms': array(ref('platform')), 'computeBackends': array(S), 'precisions': array(S), 'quantizations':array(S),
    'resourceProfiles':array(ref('profile')), 'capabilities':array(S), 'resourceRequirements':ref('resources')}, ['id','name','version'])
defs['backend'] = obj({'id': ID, 'name': S, 'version': S, 'models':array(ref('model')), 'platforms': array(ref('platform')),
    'shareableModelInstance': B, 'threadSafe': B, 'concurrentInference': B, 'maxConcurrentInference': {'type':'integer','minimum':1},
    'dependencies':array(ref('dependency')), 'resourceRequirements':ref('resources')}, ['id','name'])
defs['output'] = obj({'id':ID, 'type': S, 'description':S, 'optional':B, 'mimeType':S, 'fileExtension':S, 'metadata':{'type':'object'}}, ['id','type'])
defs['operation'] = obj({'id':ID, 'name':S, 'description':S, 'inputSchema':ref('parameter'), 'outputSchema':ref('parameter'),
    'outputs':array(ref('output')), 'supportedBackends':array(ID), 'resourceRequirements':ref('resources'), 'permissions':array(S),
    'platforms':array(ref('platform')), 'canRunAsync':B, 'canCancel':B, 'supportsProgress':B, 'supportsPreview':B,
    'supportsStreaming':B, 'estimatedDurationSeconds':N}, ['id','name','description','inputSchema','outputSchema'])
defs['error'] = obj({'code': S, 'message':S, 'technicalDetails':{}, 'recoverable':B, 'suggestedAction':{'type':['string','null']}, 'underlyingError':{}}, ['code','message','recoverable'])
defs['progress'] = obj({'percent':{'type':'number','minimum':0,'maximum':100}, 'currentStep':S, 'currentStepIndex':I, 'stepCount':I,
    'etaSeconds':N, 'currentFile':S, 'previewAvailable':B, 'statusMessage':S})
defs['job'] = obj({**{k:S for k in ['jobId','clientId','sessionId','workspaceId','workspace','toolId','operationId','backendId','modelId','createdAt']},
    'startedAt':{'type':['string','null']}, 'finishedAt':{'type':['string','null']}, 'parameters':{'type':'object'},
    'priority':enum('Interactive','Critical','High','Normal','Background','Low'),
    'state':enum('Created','Queued','WaitingForResources','Preparing','LoadingModel','Running','Paused','Cancelling','Cancelled','Completed','Failed'),
    'progress':ref('progress'), 'outputs':{}, 'error':{'anyOf':[ref('error'), {'type':'null'}]},
    'visibility':enum('Owner','Shared','Global'), 'sharedWith':array(S), 'resourceEstimate':ref('resources')},
    ['jobId','clientId','sessionId','workspaceId','toolId','operationId','parameters','priority','state','createdAt','progress','outputs','error'])
defs['event'] = obj({'sequence': I, 'type':S,'timestamp':S,'toolId':S,'clientId':S,'sessionId':S,'jobId':S,'workerId':S,'data':{}}, ['sequence','type','timestamp','toolId','data'])
defs['worker'] = obj({'workerId':S,'state':enum('Stopped','Starting','Idle','Loading','Ready','Busy','Unloading','Stopping','Failed'),
    'pid':{'type':['integer','null']},'alive':B,'lastResponseMonotonic':{'type':['number','null']},'heartbeatSupported':B,
    'releaseLevels':array(enum('Temporary','Job','Model','Worker','All'))},['state'])
tool = obj({'schemaVersion': {'type':'integer'}, 'protocolVersion': {'type':'string','pattern':'^[0-9]+\\.[0-9]+$'}, 'id':ID,
    **{k:S for k in ['name','displayName','description','vendor','author','version','executable','license','documentation','homepage','repository']},
    'categories':array(S), 'tags':array(S), 'capabilities':array(S), 'operations':array(ref('operation')), 'backends':array(ref('backend')),
    'platforms':array(ref('platform')), 'runtimeRequirements':array(ref('dependency')), 'interfaces':array(S),
    'concurrency': obj({'policy':enum('Exclusive','Sequential','Concurrent','SharedModelSequential','SharedModelConcurrent','MultiWorker','MultiGPU'),
        'maxWorkers':{'type':'integer','minimum':1,'maximum':256}}, ['policy']),
    'idleUnloadPolicy':enum('Never','AfterJob','After1Minute','After5Minutes','After15Minutes','WhenResourcesNeeded','Custom'),
    'extensions':{'type':'object'}}, ['schemaVersion','protocolVersion','id','name','version','description','operations','platforms','concurrency'])
request = obj({'protocolVersion':{'const':'1.0'}, 'id':{'type':['string','integer']}, 'method':enum('DescribeTool','GetCapabilities','ListOperations','DescribeOperation','ListBackends','ListModels','GetRuntimeStatus','GetSystemResources','EstimateResources','CanRun','Diagnose','CreateSession','CloseSession','SubmitJob','GetJob','ListJobs','CancelJob','ShareJob','GetEvents','ReleaseResources'), 'params':{'type':'object'}}, ['protocolVersion','id','method','params'])
response = obj({'protocolVersion':{'const':'1.0'},'id':{'type':['string','integer','null']},'result':{},'error':ref('error')},['protocolVersion','id'])
response['oneOf'] = [{'required':['result'],'not':{'required':['error']}},{'required':['error'],'not':{'required':['result']}}]
method_params = {
    'DescribeOperation': obj({'operationId':S},['operationId']),
    'ListModels': obj({'backendId':S}),
    'EstimateResources': obj({'operationId':S,'parameters':{'type':'object'},'backendId':S,'modelId':S},['operationId','parameters']),
    'CanRun': obj({'operationId':S,'parameters':{'type':'object'},'backendId':S,'modelId':S},['operationId','parameters']),
    'CloseSession': obj({'sessionId':S},['sessionId']),
    'SubmitJob': obj({'sessionId':S,'operationId':S,'parameters':{'type':'object'},'backendId':S,'modelId':S,
        'priority':defs['job']['properties']['priority'], 'queueTimeout':{'type':'number','exclusiveMinimum':0},
        'executionTimeout':{'type':'number','exclusiveMinimum':0}},['sessionId','operationId','parameters']),
    'GetJob':obj({'jobId':S},['jobId']), 'CancelJob':obj({'jobId':S},['jobId']),
    'ShareJob':obj({'jobId':S,'visibility':enum('Owner','Shared','Global'),'sharedWith':array(S)},['jobId','visibility']),
    'GetEvents':obj({'after':I}), 'ReleaseResources':obj({'level':enum('Temporary','Job','Model','Worker','All')},['level'])}
request['allOf']=[]
for method in request['properties']['method']['enum']:
    params=method_params.get(method,obj({}))
    params['additionalProperties']=False
    request['allOf'].append({'if':{'properties':{'method':{'const':method}}},'then':{'properties':{'params':params}}})
ROOT.mkdir(parents=True,exist_ok=True)
for name, document in {'tool':tool,'parameter':ref('parameter'),'worker':ref('worker'),'job':ref('job'),'event':ref('event'),'resources':ref('resources'),'request':request,'response':response}.items():
    used={}
    def collect(value):
        if isinstance(value,dict):
            pointer=value.get('$ref','')
            if pointer.startswith('#/$defs/'):
                key=pointer.split('/')[-1]
                if key not in used:
                    used[key]=defs[key]
                    collect(defs[key])
            for child in value.values(): collect(child)
        elif isinstance(value,list):
            for child in value: collect(child)
    collect(document)
    result = {'$schema':'https://json-schema.org/draft/2020-12/schema', '$id':f'urn:cytools:v1:{name}', **document, '$defs':used}
    (ROOT/(name+'.schema.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
