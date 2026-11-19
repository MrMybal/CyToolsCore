"""Opt-in communication discovery for Tool hosts; no transport starts on import."""
import copy


def register_operations(runtime):
    """Expose the effective native stack and a complete, composable AI catalogue."""
    identifier = 'ai_communication_status'
    if any(op['id'] == identifier for op in runtime.descriptor['operations']):
        return
    operation = {
        'id': identifier, 'name': 'AI communication capabilities',
        'description': 'Inspect native communication, task ownership and the complete operation catalogue. '
                       'Does not connect to an AI provider or start a server.',
        'inputSchema': {'type': 'object', 'properties': {
            'includeOperations': {'type': 'boolean', 'default': False}}, 'additionalProperties': False},
        'outputSchema': {'type': 'object'}, 'resourceRequirements': {}, 'supportedBackends': [],
        'permissions': [], 'canRunAsync': True, 'canCancel': False, 'supportsProgress': False}
    from .schema import validate_manifest
    descriptor = {**runtime.descriptor, 'operations': [*runtime.descriptor['operations'], operation]}
    validate_manifest(descriptor)
    runtime.descriptor = descriptor

    def status(context, parameters):
        import json
        from .transports._native import library
        result = {
            'native': json.loads(library().cytools_native_info()),
            'schemaVersion': 1, 'protocolVersion': '1.0',
            'transports': ['cli', 'jsonl', 'http-loopback', 'mcp-stdio'],
            'operationCount': len(runtime.descriptor['operations']),
            'discovery': ['DescribeTool', 'ListOperations', 'DescribeOperation', 'GetCapabilities'],
            'execution': ['CanRun', 'EstimateResources', 'SubmitJob', 'GetJob', 'CancelJob', 'GetEvents'],
            'taskFiles': {'temporaryByDefault': True, 'absoluteInputs': True,
                          'exportBeforeFinish': True, 'methods': ['ImportFile', 'ExportJob', 'FinishTask'],
                          'cliExportOption': '--export-dir'},
        }
        if parameters.get('includeOperations', False):
            result['operations'] = copy.deepcopy(runtime.descriptor['operations'])
        return result

    runtime.register(identifier, status)
