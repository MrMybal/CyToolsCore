"""Generate the descriptor used by this reference integration."""
import json
from model_config import ROOT, MODEL_ID, REVISION, WEIGHTS_SHA256, WEIGHTS_SIZE

def obj(properties,required=None):
    return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}
S={'type':'string'}
N={'type':'number','minimum':0}
match=obj({'label':S,'description':S,'cosine_similarity':{'type':'number','minimum':-1.001,'maximum':1.001},'relative_score':{'type':'number','minimum':0,'maximum':1}})
segment=obj({'start_seconds':N,'end_seconds':N,'label':S,'cosine_similarity':{'type':'number'}})
inputs=obj({'audio_file':{'type':'string','minLength':1,'maxLength':1024,'x-cy-kind':'File','description':'File inside the configured audio root.'},
    'preset':{'enum':['general','sounds','music'],'default':'general'},
    'candidate_labels':{'type':'array','items':{'type':'string','minLength':1,'maxLength':256},'minItems':2,'maxItems':128,'uniqueItems':True,'description':'Optional English descriptions, replacing the preset.'},
    'top_k':{'type':'integer','minimum':1,'maximum':10,'default':5},
    'max_seconds':{'type':'number','exclusiveMinimum':0,'maximum':120,'default':30}},['audio_file'])
outputs=obj({'model_id':S,'model_revision':S,'device':{'const':'cpu'},'sample_rate':{'const':48000},
    'worker_memory_bytes':{'type':'integer','minimum':0},'memory_measurement':S,
    'source_duration_seconds':N,'analysed_seconds':N,'candidate_count':{'type':'integer','minimum':2},
    'matches':{'type':'array','items':match,'minItems':1,'maxItems':10},'segments':{'type':'array','items':segment},
    'warnings':{'type':'array','items':S},'score_meaning':S,
    'timings':obj({'load_and_audio_seconds':N,'inference_seconds':N,'total_seconds':N}),
    'report_file':{'type':'string','x-cy-kind':'File'}})
platforms=[{'os':'Windows','architecture':'x64','status':'Supported','computeBackends':['CPU']},
           {'os':'Linux','architecture':'x64','status':'Experimental','computeBackends':['CPU']},
           {'os':'macOS','architecture':'ARM64','status':'Experimental','computeBackends':['CPU']}]
descriptor={'schemaVersion':1,'protocolVersion':'1.0','id':'cy.tool.clap','name':'CyToolCLAP','version':'0.1.0',
    'description':'Local CLAP zero-shot sound and music classification. Compares audio with candidate descriptions; does not identify song titles.',
    'vendor':'Cyberalien','author':'Cyberalien','categories':['audio','classification'],'tags':['CLAP','sound','music'],
    'executable':'python tool.py','capabilities':['jobs','cancellation','progress','audio-classification'],
    'interfaces':['Native','CLI','JSONL','HTTP','MCP'],'platforms':platforms,'runtimeRequirements':[],
    'concurrency':{'policy':'Sequential','maxWorkers':1},'idleUnloadPolicy':'AfterJob',
    'backends':[{'id':'transformers-cpu','name':'Transformers / PyTorch CPU','threadSafe':False,
        'shareableModelInstance':False,'concurrentInference':False,'maxConcurrentInference':1,
        'models':[{'id':'clap-htsat-unfused','name':MODEL_ID,'version':REVISION,'source':'https://huggingface.co/'+MODEL_ID,
                   'license':'Apache-2.0','location':'Local','runsLocally':True,'installed':False,
                   'computeBackends':['CPU'],'files':[{'path':'pytorch_model.bin','sha256':WEIGHTS_SHA256,'sizeBytes':WEIGHTS_SIZE}],
                   'downloadSize':617900000}]}],
    'operations':[{'id':'classify_audio','name':'Identify sound or musical content',
        'description':'Rank candidate sound/music descriptions for a local audio file. Returns similarities, relative scores and a JSON report; no song-title fingerprinting.',
        'inputSchema':inputs,'outputSchema':outputs,'supportedBackends':['transformers-cpu'],'permissions':[],
        'canRunAsync':True,'canCancel':True,'supportsProgress':True,
        'resourceRequirements':{'ramBytes':6*1024**3,'cpuThreads':4,'diskBytes':300*1024**2,'networkRequired':False},
        'outputs':[{'id':'report_file','type':'File','mimeType':'application/json','fileExtension':'.json','description':'Isolated job classification report'}]}]}
(ROOT/'CyTool.json').write_text(json.dumps(descriptor,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
