"""Official MCP SDK v1 adapter; descriptors drive tool discovery automatically."""
import asyncio
import json
import copy


def _envelope_schema(spec, field='parameters'):
    """Preserve local JSON pointers when nesting a schema in parameters."""
    spec=copy.deepcopy(spec)
    def visit(node):
        if isinstance(node,dict):
            node.pop('$id',None)
            for key,value in node.items():
                if key in ('$ref','$dynamicRef') and isinstance(value,str) and value.startswith('#/'):
                    node[key]='#/properties/'+field+'/'+value[2:]
                elif key in ('$ref','$dynamicRef') and value=='#':
                    node[key]='#/properties/'+field
                else: visit(value)
        elif isinstance(node,list):
            for value in node: visit(value)
    visit(spec)
    return spec


def create_server(client):
    # Optional dependency imported only when requested.
    from mcp.server.lowlevel import Server
    from mcp.types import Tool, TextContent, CallToolResult, ToolAnnotations
    from ..errors import CyToolError
    from ..schema import schema
    descriptor=client.call('DescribeTool')
    server=Server(descriptor['name'])
    operations={op['id']:op for op in descriptor['operations']}
    session_id=client.call('CreateSession',temporary=True)['sessionId']
    sessions={session_id}
    server.cytools_sessions=sessions
    server.cytools_client=client
    controls={
        'cy_describe':('DescribeTool',{}),
        'cy_status':('GetRuntimeStatus',{}),
        'cy_list_jobs':('ListJobs',{}),
        'cy_get_job':('GetJob',{'jobId':{'type':'string'}}),
        'cy_cancel_job':('CancelJob',{'jobId':{'type':'string'}}),
        'cy_events':('GetEvents',{'after':{'type':'integer','minimum':0}}),
        'cy_can_run':('CanRun',{'operationId':{'type':'string'},'parameters':{'type':'object'},'backendId':{'type':'string'},'modelId':{'type':'string'}}),
    }
    # Derive controls from the portable wire contract; do not maintain weaker
    # hand-written schemas in the MCP facade.
    request_schemas={item['if']['properties']['method']['const']:item['then']['properties']['params']
                     for item in schema('request')['allOf']}
    job_output={'type':'object','properties':{'result':_envelope_schema(schema('job'),'result')},'required':['result'],'additionalProperties':False}
    for name,method in {
        'cy_capabilities':'GetCapabilities','cy_list_operations':'ListOperations',
        'cy_describe_operation':'DescribeOperation','cy_list_backends':'ListBackends',
        'cy_list_models':'ListModels','cy_system_resources':'GetSystemResources',
        'cy_estimate':'EstimateResources','cy_diagnose':'Diagnose',
        'cy_release_resources':'ReleaseResources',
        'cy_begin_task':'CreateSession','cy_finish_task':'FinishTask',
        'cy_keep_task_alive':'KeepTaskAlive','cy_export_job':'ExportJob','cy_import_file':'ImportFile',
    }.items():controls[name]=(method,{})

    @server.list_tools()
    async def list_tools():
        tools=[]
        for op in operations.values():
            # Envelope keeps backend/model selection distinct from domain parameters.
            properties={'parameters':_envelope_schema(op['inputSchema']),'sessionId':{'type':'string','description':'Optional task ID from cy_begin_task; defaults to the connection task.'},'backendId':{'type':'string'},'modelId':{'type':'string'},
                        'priority':{'type':'string','enum':['Interactive','Critical','High','Normal','Background','Low']}}
            for key in ('queueTimeout','executionTimeout'):
                properties[key]=copy.deepcopy(request_schemas['SubmitJob']['properties'][key])
            tools.append(Tool(name='op_'+op['id'],description=op['description']+' Starts an asynchronous job; poll cy_get_job with jobId. Import external inputs with cy_import_file first. Export wanted results using cy_export_job, then call cy_finish_task after all consumers stop; task files are temporary.',
                inputSchema={'type':'object','properties':properties,'required':['parameters'],'additionalProperties':False},
                outputSchema=copy.deepcopy(job_output),
                annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=True,openWorldHint=True)))
        for name,(method,props) in controls.items():
            mutating=name in ('cy_cancel_job','cy_release_resources','cy_begin_task','cy_finish_task','cy_keep_task_alive','cy_export_job','cy_import_file')
            spec=copy.deepcopy(request_schemas[method])
            if method=='CreateSession': spec['properties']['temporary']={'const':True,'default':True}
            if method in ('FinishTask','KeepTaskAlive','ImportFile'):
                spec['required']=[key for key in spec.get('required',[]) if key!='sessionId']
            descriptions={
                'ImportFile':'Copy an absolute local source into this Tool automatically; returns path to use in operation parameters. Optional companions preserve relative bundle paths. Originals are untouched; copies belong to the task.',
                'FinishTask':'Finish the task and delete its imported copies, generated files and intermediates after workers stop. Export wanted results first and wait for downstream consumers. cancelRunning requests cancellation. Omit sessionId for the connection task.',
                'ExportJob':'Preserve a stopped job bundle in an explicit destination outside the runtime, returning durable output paths. Does not end the task.',
                'CreateSession':'Begin an additional temporary task; pass the returned sessionId to operations and controls. Idle retentionSeconds defaults to 3600; active workers never expire.',
                'KeepTaskAlive':'Renew the idle lifetime of a temporary task while other Tools consume its results.',
            }
            tools.append(Tool(name=name,description=descriptions.get(method,method+' (CyTools v1). Operation descriptions include complete input/output schemas and constraints.'), inputSchema=spec,
                outputSchema=copy.deepcopy(job_output) if name=='cy_get_job' else None,
                annotations=ToolAnnotations(readOnlyHint=not mutating,destructiveHint=mutating,openWorldHint=False)))
        return tools

    @server.call_tool()
    async def call_tool(name,arguments):
        nonlocal session_id
        arguments=dict(arguments or {})
        try:
            if name.startswith('op_') and name[3:] in operations:
                if 'sessionId' not in arguments:
                    try: await asyncio.to_thread(client.call,'KeepTaskAlive',sessionId=session_id)
                    except CyToolError as exc:
                        if exc.code!='AccessDenied': raise
                        session_id=await asyncio.to_thread(lambda:client.call('CreateSession',temporary=True)['sessionId'])
                        sessions.add(session_id)
                selected=arguments.pop('sessionId',session_id)
                if selected not in sessions: raise CyToolError('AccessDenied','Task belongs to another connection')
                result=await asyncio.to_thread(client.call,'SubmitJob',sessionId=selected,operationId=name[3:],**arguments)
            elif name in controls:
                method=controls[name][0]
                if method in ('FinishTask','KeepTaskAlive','ImportFile'):
                    arguments.setdefault('sessionId',session_id)
                    if arguments['sessionId'] not in sessions: raise CyToolError('AccessDenied','Task belongs to another connection')
                if method=='CreateSession': arguments['temporary']=True
                result=await asyncio.to_thread(client.call,method,**arguments)
                if method=='CreateSession': sessions.add(result['sessionId'])
                if method=='FinishTask' and arguments['sessionId']==session_id:
                    session_id=await asyncio.to_thread(lambda:client.call('CreateSession',temporary=True)['sessionId'])
                    sessions.add(session_id)
            else: raise CyToolError('UnknownOperation','Unknown MCP tool')
            return CallToolResult(content=[TextContent(type='text',text=json.dumps(result,ensure_ascii=False))],structuredContent={'result':result},isError=False)
        except CyToolError as exc:
            return CallToolResult(content=[TextContent(type='text',text=json.dumps(exc.to_dict()))],isError=True)
    return server


async def serve(client):
    from mcp.server.stdio import stdio_server
    server=create_server(client)
    try:
        async with stdio_server() as (reader,writer):
            await server.run(reader,writer,server.create_initialization_options())
    finally:
        import anyio
        with anyio.CancelScope(shield=True):
            for session_id in server.cytools_sessions:
                await asyncio.to_thread(client.call,'FinishTask',sessionId=session_id,cancelRunning=True)
