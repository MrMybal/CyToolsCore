"""Run with ProcessWorker([sys.executable, absolute_path_to_this_file])."""
import json
import sys

request=json.load(sys.stdin)
if request.get('protocolVersion')!='1.0':
    print('Unsupported worker protocol',file=sys.stderr)
    raise SystemExit(2)
print(json.dumps({'text':request['parameters']['text']}))
