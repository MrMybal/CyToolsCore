"""Compatibility helpers; MCP protocol and server run in CyMCPSDK C++."""
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
    from ._native import NativeHost
    return NativeHost(client=client)


async def serve(client):
    import asyncio
    with create_server(client) as host:
        await asyncio.to_thread(host.call, 'serve_mcp')
