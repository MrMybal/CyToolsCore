"""One-shot CPU inference: local pinned model; no network during classification."""
import contextlib
import json
import math
import os
import sys
import time
from pathlib import Path
from labels import candidates
from model_config import MODEL_ID,REVISION,model_dir

def classify(parameters):
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    import numpy as np
    import soundfile as sf
    import torch
    import psutil
    from scipy.signal import resample_poly
    from transformers import ClapModel,ClapProcessor
    started=time.monotonic()
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    np.random.seed(0)
    torch.manual_seed(0)
    try:
        with sf.SoundFile(Path(parameters['audio_file'])) as audio:
            if not 8000<=audio.samplerate<=192000 or not 1<=audio.channels<=2:
                raise ValueError('Audio must have 1-2 channels and a sample rate between 8 and 192 kHz')
            source_rate=audio.samplerate
            total_seconds=audio.frames/source_rate
            values=audio.read(frames=int(parameters['max_seconds']*source_rate),dtype='float32',always_2d=True).mean(axis=1)
    except sf.LibsndfileError as exc:
        raise ValueError('Cannot decode audio: '+str(exc)) from exc
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('Audio is empty or contains non-finite samples')
    if source_rate!=48000:
        gcd=math.gcd(source_rate,48000)
        values=resample_poly(values,48000//gcd,source_rate//gcd).astype(np.float32)
    warnings=[]
    if float(np.max(np.abs(values)))<1e-5:
        raise ValueError('Audio contains silence; no meaningful classification is possible')
    if total_seconds>parameters['max_seconds']:
        warnings.append('Only the beginning of the file was analysed (max_seconds).')
    choices=candidates(parameters['preset'],parameters.get('candidate_labels'))
    processor=ClapProcessor.from_pretrained(str(model_dir()),local_files_only=True)
    model=ClapModel.from_pretrained(str(model_dir()),local_files_only=True,weights_only=True).eval()
    loaded=time.monotonic()
    text_inputs=processor.tokenizer([prompt for _,prompt in choices],padding=True,truncation=True,max_length=77,return_tensors='pt')
    similarities=[]
    segments=[]
    with torch.inference_mode():
        text_features=model.get_text_features(**text_inputs)
        text_features=torch.nn.functional.normalize(text_features,dim=-1)
        for start in range(0,len(values),480000):
            chunk=values[start:start+480000]
            audio_inputs=processor.feature_extractor(chunk,sampling_rate=48000,return_tensors='pt')
            audio_features=model.get_audio_features(**audio_inputs)
            audio_features=torch.nn.functional.normalize(audio_features,dim=-1)
            similarity=(audio_features@text_features.T)[0]
            similarities.append(similarity)
            best=int(similarity.argmax())
            segments.append({'start_seconds':start/48000,'end_seconds':min(start+480000,len(values))/48000,
                             'label':choices[best][0],'cosine_similarity':float(similarity[best])})
        durations=torch.tensor([s['end_seconds']-s['start_seconds'] for s in segments])
        mean=(torch.stack(similarities)*durations[:,None]).sum(dim=0)/durations.sum()
        scores=(mean*model.logit_scale_a.exp()).softmax(dim=-1)
        order=torch.argsort(mean,descending=True)[:min(parameters['top_k'],len(choices))]
        matches=[{'label':choices[i][0],'description':choices[i][1],
                  'cosine_similarity':float(mean[i]),'relative_score':float(scores[i])} for i in order.tolist()]
    memory=psutil.Process().memory_info()
    return {'model_id':MODEL_ID,'model_revision':REVISION,'device':'cpu','sample_rate':48000,
            'worker_memory_bytes':getattr(memory,'peak_wset',memory.rss),
            'memory_measurement':'peak_working_set' if hasattr(memory,'peak_wset') else 'rss_at_completion',
            'source_duration_seconds':total_seconds,'analysed_seconds':len(values)/48000,
            'candidate_count':len(choices),'matches':matches,'segments':segments,'warnings':warnings,
            'score_meaning':'Relative scores compare ONLY supplied candidates; not calibrated probabilities. No song-title recognition.',
            'timings':{'load_and_audio_seconds':loaded-started,'inference_seconds':time.monotonic()-loaded,
                       'total_seconds':time.monotonic()-started}}

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        request=json.load(sys.stdin)
        if request.get('protocolVersion')!='1.0': raise ValueError('Unknown worker protocol')
        with contextlib.redirect_stdout(sys.stderr):
            result=classify(request['parameters'])
    except Exception as exc:
        result={'error':{'code':'InvalidAudio' if isinstance(exc,ValueError) else 'InferenceFailed','message':str(exc)}}
    print(json.dumps(result,ensure_ascii=False,allow_nan=False),flush=True)
