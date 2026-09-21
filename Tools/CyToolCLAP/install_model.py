"""Download the pinned official checkpoint using CyToolsCore's resumable manager."""
import hashlib
import json
from datetime import datetime,timezone
from cytools_core.downloads import DownloadManager
from model_config import MODEL_ID,REVISION,FILES,WEIGHTS_SHA256,model_dir

def install():
    root=model_dir()
    manager=DownloadManager(root,timeout=60)
    verified={}
    for name,size in FILES.items():
        print('Downloading/verifying '+name,flush=True)
        manager.download(name,f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}',
                         size=size,sha256=WEIGHTS_SHA256 if name=='pytorch_model.bin' else None,revision=REVISION)
        with (root/name).open('rb') as stream:
            verified[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    (root/'verified.json').write_text(json.dumps({'modelId':MODEL_ID,'revision':REVISION,'sha256':verified,
        'verifiedAt':datetime.now(timezone.utc).isoformat()},indent=2),encoding='utf-8')
    print('Model installed: '+str(root),flush=True)

if __name__=='__main__': install()
