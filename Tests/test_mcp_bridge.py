import asyncio
import json
import os
import sys
import threading
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from cytools_core.transports.http import make_server


def test_two_mcp_clients_share_service_with_private_jobs(runtime):
    credentials=[runtime.create_client(name) for name in ('MCP-A','MCP-B')]
    server=make_server(runtime)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url=f'http://127.0.0.1:{server.server_port}/v1'
    async def scenario():
        def params(credential):
            return StdioServerParameters(command=sys.executable,args=['-m','cytool_test','--connect',url,'mcp'],
                                         env={**os.environ,'CYTOOLS_TOKEN':credential['token']})
        async with stdio_client(params(credentials[0])) as (ar,aw), stdio_client(params(credentials[1])) as (br,bw):
            async with ClientSession(ar,aw) as a, ClientSession(br,bw) as b:
                await a.initialize()
                await b.initialize()
                first=await a.call_tool('op_sleep',{'parameters':{'seconds':.3}})
                job=json.loads(first.content[0].text)
                assert not first.isError
                hidden=await b.call_tool('cy_get_job',{'jobId':job['jobId']})
                assert hidden.isError
                second=await b.call_tool('op_echo',{'parameters':{'text':'B'}})
                assert not second.isError
                assert len(runtime.list_jobs(runtime.authenticate(credentials[0]['token'])))==1
                assert len(runtime.list_jobs(runtime.authenticate(credentials[1]['token'])))==1
                cancelled=await a.call_tool('cy_cancel_job',{'jobId':job['jobId']})
                assert not cancelled.isError
    try: asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
