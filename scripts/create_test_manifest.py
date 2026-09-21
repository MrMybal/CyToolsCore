import json
from pathlib import Path

def obj(properties,required=()): return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}
def number(default,maximum=60): return {'type':'number','minimum':0,'maximum':maximum,'default':default}
text={'type':'string','maxLength':65536}
ops=[]
def op(name,description,inputs,outputs):
    ops.append({'id':name,'name':name,'description':description,'inputSchema':inputs,'outputSchema':outputs,
                'canRunAsync':True,'canCancel':True,'supportsProgress':name=='progress_test','supportedBackends':[],'permissions':[]})
op('echo','Return the supplied text.',obj({'text':text},['text']),obj({'text':text},['text']))
op('sleep','Wait cooperatively; demonstrates cancellation.',obj({'seconds':number(.1)}),obj({'sleptSeconds':{'type':'number'}},['sleptSeconds']))
op('generate_file','Create a UTF-8 file inside the isolated job workspace.',obj({'name':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$','default':'result.txt'},'text':text},['text']),obj({'file':{'type':'string','x-cy-kind':'File'},'mimeType':{'type':'string'},'sizeBytes':{'type':'integer'}},['file','mimeType','sizeBytes']))
op('allocate_ram','Allocate up to 64 MiB of real RAM temporarily.',obj({'bytes':{'type':'integer','minimum':0,'maximum':67108864,'default':1048576},'seconds':number(.1)}),obj({'allocatedBytes':{'type':'integer'}},['allocatedBytes']))
op('simulate_vram','Reserve simulated VRAM. Requires a simulation device in an injected resource budget; never allocates GPU memory.',obj({'bytes':{'type':'integer','minimum':1,'default':10737418240},'seconds':number(.1)}),obj({'simulated':{'const':True},'reservedBytes':{'type':'integer'}},['simulated','reservedBytes']))
op('fail','Raise a structured test error.',obj({'message':{'type':'string','default':'Expected test failure'}}),obj({}))
op('progress_test','Report step-by-step progress.',obj({'steps':{'type':'integer','minimum':1,'maximum':100,'default':5},'seconds':number(.1)}),obj({'steps':{'type':'integer'}},['steps']))
descriptor={'schemaVersion':1,'protocolVersion':'1.0','id':'cy.tool.test','name':'CyToolTest','displayName':'CyToolTest',
    'description':'Reference standalone CyTool without AI dependencies','vendor':'Cyberalien','author':'Cyberalien','version':'0.1.0',
    'executable':'cytool-test','categories':['development','test'],'tags':['reference'],'capabilities':['jobs','multi-client','cancellation','progress'],
    'operations':ops,'backends':[],'platforms':[{'os':os,'architecture':arch,'status':status,'computeBackends':['CPU']} for os,arch,status in [('Windows','x64','Supported'),('Linux','x64','Supported'),('macOS','ARM64','Experimental')]],
    'runtimeRequirements':[{'id':'python','version':'>=3.11','required':False}], 'interfaces':['Native','CLI','JSONL','HTTP','MCP'],
    'concurrency':{'policy':'Concurrent','maxWorkers':4},'idleUnloadPolicy':'AfterJob','documentation':'Docs/CreatingYourFirstCyTool.md'}
path=Path(__file__).resolve().parents[1]/'cytool_test'/'CyTool.json'
path.write_text(json.dumps(descriptor,indent=2)+'\n',encoding='utf-8')
