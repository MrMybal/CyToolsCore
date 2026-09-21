import argparse
import asyncio
import json
import os
import sys
from ..errors import CyToolError
from .api import LocalClient


def run_cli(factory, argv=None):
    parser=argparse.ArgumentParser(description='Standalone CyTool — CyTools protocol 1.0')
    parser.add_argument('--data-dir',default='.cytools')
    parser.add_argument('--connect',help='Shared service URL, e.g. http://127.0.0.1:8766/v1')
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('describe','list-operations','list-backends','list-models','diagnose','mcp','stdio'): commands.add_parser(name)
    describe_operation=commands.add_parser('describe-operation')
    describe_operation.add_argument('operation')
    for name in ('estimate','can-run'):
        command=commands.add_parser(name)
        command.add_argument('operation');command.add_argument('--params',default='{}')
        command.add_argument('--params-file');command.add_argument('--backend',default='');command.add_argument('--model',default='')
    invoke=commands.add_parser('invoke')
    invoke.add_argument('operation')
    invoke.add_argument('--params',default='{}',help='JSON object')
    invoke.add_argument('--params-file',help='UTF-8 JSON file (preferred for shell quoting)')
    invoke.add_argument('--backend',default='')
    invoke.add_argument('--model',default='')
    invoke.add_argument('--timeout',type=float,default=300)
    serve=commands.add_parser('serve')
    serve.add_argument('--port',type=int,default=8766)
    client_cmd=commands.add_parser('create-client')
    client_cmd.add_argument('--name',required=True)
    client_cmd.add_argument('--permission',action='append',default=[])
    args=parser.parse_args(argv)
    runtime=None
    try:
        if args.connect:
            if args.command in ('serve','create-client'): raise CyToolError('InvalidParameters','This command requires a local data directory')
            from .http import HTTPClient
            token=os.environ.get('CYTOOLS_TOKEN','')
            if not token: raise CyToolError('AuthenticationRequired','Set CYTOOLS_TOKEN for the selected client')
            client=HTTPClient(args.connect,token)
        else:
            runtime=factory(args.data_dir)
            runtime.start()
            if args.command=='create-client':
                print(json.dumps(runtime.create_client(args.name,args.permission)))
                return 0
            if args.command=='serve':
                from .http import make_server
                server=make_server(runtime,args.port)
                print(f'CyTools API listening on http://127.0.0.1:{server.server_port}/v1',file=sys.stderr,flush=True)
                try: server.serve_forever()
                except KeyboardInterrupt: pass
                finally: server.server_close()
                return 0
            token=os.environ.get('CYTOOLS_TOKEN')
            actor=runtime.authenticate(token) if token else runtime.authenticate(runtime.create_client('standalone')['token'])
            client=LocalClient(runtime,actor)
        if args.command=='mcp':
            asyncio.run(__import__('cytools_core.transports.mcp',fromlist=['serve']).serve(client))
        elif args.command=='stdio':
            for line in sys.stdin:
                try:
                    request=json.loads(line)
                    if isinstance(client,LocalClient): result=client.dispatch(request)
                    else:
                        from ..schema import validate_document
                        validate_document(request,'request')
                        result={'protocolVersion':'1.0','id':request['id'],'result':client.call(request['method'],**request['params'])}
                except (ValueError,CyToolError) as exc:
                    result={'protocolVersion':'1.0','id':None,'error':CyToolError('InvalidRequest',str(exc)).to_dict()}
                print(json.dumps(result,ensure_ascii=False,allow_nan=False),flush=True)
        elif args.command=='invoke':
            import time
            parameters=json.loads(open(args.params_file,encoding='utf-8-sig').read() if args.params_file else args.params)
            session=client.call('CreateSession',temporary=False)
            job=client.call('SubmitJob',sessionId=session['sessionId'],operationId=args.operation,parameters=parameters,
                            backendId=args.backend,modelId=args.model,executionTimeout=args.timeout,queueTimeout=args.timeout)
            deadline=time.monotonic()+args.timeout+5
            while job['state'] not in ('Completed','Cancelled','Failed'):
                if time.monotonic()>deadline: raise CyToolError('Timeout','Job has not stopped; check GetJob before retrying')
                time.sleep(.03)
                job=client.call('GetJob',jobId=job['jobId'])
            print(json.dumps(job,ensure_ascii=False))
            client.call('CloseSession',sessionId=session['sessionId'])
            return 0 if job['state']=='Completed' else 1
        elif args.command in ('describe-operation','estimate','can-run'):
            method={'describe-operation':'DescribeOperation','estimate':'EstimateResources','can-run':'CanRun'}[args.command]
            params={'operationId':args.operation}
            if args.command!='describe-operation':
                from pathlib import Path
                params.update(parameters=json.loads(Path(args.params_file).read_text('utf-8-sig') if args.params_file else args.params),backendId=args.backend,modelId=args.model)
            print(json.dumps(client.call(method,**params),ensure_ascii=False,indent=2))
        else:
            method={'describe':'DescribeTool','list-operations':'ListOperations','list-backends':'ListBackends','list-models':'ListModels','diagnose':'Diagnose'}[args.command]
            print(json.dumps(client.call(method),ensure_ascii=False,indent=2))
        return 0
    except (CyToolError,ValueError,OSError,ImportError) as exc:
        error=exc if isinstance(exc,CyToolError) else CyToolError('ConfigurationError',str(exc))
        print(json.dumps({'error':error.to_dict()}),file=sys.stderr)
        return 1
    finally:
        if runtime: runtime.close()
