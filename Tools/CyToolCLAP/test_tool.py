import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from cytools_core import CyToolError,load_manifest,validate_parameters
from labels import candidates
from model_config import ROOT
from tool import create_runtime,resolve_audio

class ToolTests(unittest.TestCase):
    def test_manifest_and_defaults(self):
        manifest=load_manifest(ROOT/'CyTool.json')
        p=validate_parameters({'audio_file':'test.wav'},manifest['operations'][0]['inputSchema'])
        self.assertEqual(p['preset'],'general')
        self.assertEqual(p['max_seconds'],30)
        self.assertEqual(len(candidates('general')),28)

    def test_invalid_parameters(self):
        schema=load_manifest(ROOT/'CyTool.json')['operations'][0]['inputSchema']
        for p in ({},{'audio_file':'x','max_seconds':121},{'audio_file':'x','top_k':0},
                  {'audio_file':'x','candidate_labels':['one']},{'audio_file':'x','clientId':'spoof'}):
            with self.subTest(p=p),self.assertRaises(CyToolError): validate_parameters(p,schema)

    def test_path_isolation(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'CYTOOLS_CLAP_AUDIO_ROOT':directory}):
            with self.assertRaises(CyToolError) as error: resolve_audio('../outside.wav')
            self.assertEqual(error.exception.code,'AccessDenied')
            with self.assertRaises(CyToolError) as error: resolve_audio('missing.wav')
            self.assertEqual(error.exception.code,'MissingInput')

    def test_missing_model_and_private_job(self):
        with tempfile.TemporaryDirectory() as root,patch('tool.model_installed',return_value=False):
            with create_runtime(root) as runtime:
                alice=runtime.authenticate(runtime.create_client('Alice')['token'])
                bob=runtime.authenticate(runtime.create_client('Bob')['token'])
                session=runtime.create_session(alice)['sessionId']
                job=runtime.submit(alice,session,'classify_audio',{'audio_file':'missing.wav'})
                result=runtime.wait(alice,job['jobId'])
                self.assertEqual(result['error']['code'],'MissingModel')
                self.assertEqual(runtime.list_jobs(bob),[])
                self.assertEqual(runtime.ledger.snapshot()['reservations'],{})

    def test_invalid_audio_failure(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'CYTOOLS_CLAP_AUDIO_ROOT':directory}),patch('tool.model_installed',return_value=True):
            Path(directory,'broken.wav').write_bytes(b'not a WAV file')
            with create_runtime(Path(directory)/'runtime') as runtime:
                actor=runtime.authenticate(runtime.create_client()['token'])
                session=runtime.create_session(actor)['sessionId']
                job=runtime.submit(actor,session,'classify_audio',{'audio_file':'broken.wav'})
                result=runtime.wait(actor,job['jobId'],timeout=30)
                self.assertEqual(result['state'],'Failed')
                self.assertEqual(result['error']['code'],'InvalidAudio')
                self.assertEqual(result['outputs'],None)
                self.assertEqual(runtime.ledger.snapshot()['reservations'],{})

    def test_custom_candidates(self):
        self.assertEqual(candidates('general',['Sound of a bell','Sound of a train']),
                         [('Sound of a bell','Sound of a bell'),('Sound of a train','Sound of a train')])

    def test_cancellation_stops_worker(self):
        import wave
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'CYTOOLS_CLAP_AUDIO_ROOT':directory}),patch('tool.model_installed',return_value=True):
            with wave.open(str(Path(directory)/'test.wav'),'wb') as stream:
                stream.setparams((1,2,48000,48000,'NONE','not compressed'))
                stream.writeframes(b'\x01\x01'*48000)
            with create_runtime(Path(directory)/'runtime') as runtime:
                actor=runtime.authenticate(runtime.create_client()['token'])
                session=runtime.create_session(actor)['sessionId']
                job=runtime.submit(actor,session,'classify_audio',{'audio_file':'test.wav'})
                deadline=time.monotonic()+5
                while runtime.status()['runningWorkers']==0:
                    self.assertLess(time.monotonic(),deadline)
                    time.sleep(.01)
                runtime.cancel(actor,job['jobId'])
                result=runtime.wait(actor,job['jobId'],timeout=10)
                self.assertEqual(result['state'],'Cancelled')
                self.assertEqual(runtime.status()['runningWorkers'],0)
                self.assertEqual(runtime.ledger.snapshot()['reservations'],{})

if __name__=='__main__': unittest.main()
