"""Small public fixtures with provenance; no private user audio is downloaded."""
import csv
import hashlib
import io
import json
import urllib.request
from cytools_core.downloads import DownloadManager
from model_config import ROOT

def get_text(url):
    with urllib.request.urlopen(url,timeout=30) as stream: return stream.read().decode('utf-8')

def download():
    destination=ROOT/'audio'
    manager=DownloadManager(destination)
    rows=list(csv.DictReader(io.StringIO(get_text('https://raw.githubusercontent.com/karolpiczak/ESC-50/master/meta/esc50.csv'))))
    sources=[]
    for category,label in [('dog','Chien qui aboie'),('rain','Pluie')]:
        row=next(row for row in rows if row['category']==category)
        url='https://raw.githubusercontent.com/karolpiczak/ESC-50/master/audio/'+row['filename']
        name=category+'.wav'
        manager.download(name,url)
        sources.append({'file':name,'expected_label':label,'url':url,'dataset':'ESC-50','original_metadata':row,
            'license':'CC BY-NC 3.0 (dataset; original Freesound terms also apply)',
            'reference':'https://github.com/karolpiczak/ESC-50'})
    index=json.loads(get_text('https://raw.githubusercontent.com/librosa/librosa/main/librosa/util/example_data/index.json'))
    registry=dict(line.split() for line in get_text('https://raw.githubusercontent.com/librosa/librosa/main/librosa/util/example_data/registry.txt').splitlines() if line.strip())
    for key,label in [('trumpet','Trompette'),('pistachio','Piano')]:
        name=index[key]['path']+'.ogg'
        url='https://librosa.org/data/audio/'+name
        manager.download(key+'.ogg',url,sha256=registry[name])
        license_text=get_text('https://librosa.org/data/audio/'+index[key]['path']+'.txt')
        sources.append({'file':key+'.ogg','expected_label':label,'url':url,'dataset':'librosa examples',
                        'license_and_attribution':license_text,'reference':'https://librosa.org/doc/main/recordings.html'})
    for source in sources:
        with (destination/source['file']).open('rb') as stream: source['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    (destination/'SOURCES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'file':s['file'],'expected':s['expected_label']} for s in sources],ensure_ascii=False))

if __name__=='__main__': download()
