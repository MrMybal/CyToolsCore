from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
MODEL_ID = 'laion/clap-htsat-unfused'
REVISION = '8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a'
WEIGHTS_SHA256 = '1cd3c601bc4afe0fa87be3de4c13dd2cfadd249fac1e29acf74a9b296c3219bb'
WEIGHTS_SIZE = 614525833
FILES = {'config.json':5390, 'merges.txt':456356, 'preprocessor_config.json':541,
         'pytorch_model.bin':WEIGHTS_SIZE, 'special_tokens_map.json':280,
         'tokenizer.json':2108746, 'tokenizer_config.json':384, 'vocab.json':798293}

def model_dir():
    return Path(os.environ.get('CYTOOLS_CLAP_MODEL_DIR',str(ROOT/'models'/REVISION))).resolve()

def model_installed():
    path=model_dir()
    return all((path/name).is_file() and (path/name).stat().st_size==size for name,size in FILES.items()) and (path/'verified.json').is_file()
