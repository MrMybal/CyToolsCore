"""Run after dotnet build Examples/DotNetClient; no provider account needed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from cytool_test import create_runtime
from cytools_core.transports.http import make_server

root=Path(__file__).resolve().parents[1]
assembly=root/'Examples/DotNetClient/bin/Debug/net8.0/DotNetClient.dll'
with tempfile.TemporaryDirectory(prefix='cytools-dotnet-') as directory:
    with create_runtime(directory) as runtime:
        credentials=runtime.create_client('CSharpIntegrationTest')
        server=make_server(runtime)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            result=subprocess.run(['dotnet',str(assembly),f'http://127.0.0.1:{server.server_port}/v1'],
                capture_output=True,text=True,timeout=30,env={**os.environ,'CYTOOLS_TOKEN':credentials['token']})
            assert result.returncode==0,result.stderr
            job=json.loads(result.stdout)
            assert job['state']=='Completed' and job['outputs']=={'text':'Hello from C#'}
            print(json.dumps({'client':'C# .NET 8','transport':'HTTP CyTools 1.0','state':job['state'],'outputs':job['outputs']}))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
