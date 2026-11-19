from cytools_core.communication import register_operations
from cytools_core.transports._native import NativeHost
from cytools_core.transports.api import LocalClient


def test_effective_catalogue_through_native_boundary(tmp_path):
    from cytool_test import create_runtime
    runtime = create_runtime(tmp_path)
    register_operations(runtime)
    register_operations(runtime)
    runtime.start()
    actor = runtime.authenticate(runtime.create_client('Discovery')['token'])
    assert sum(op['id'] == 'ai_communication_status' for op in runtime.descriptor['operations']) == 1
    with NativeHost(client=LocalClient(runtime, actor)) as host:
        job = host.call('sdk', request={'method': 'invoke', 'name': 'op_ai_communication_status',
                                        'arguments': {'parameters': {'includeOperations': True}}})['result']
        result = runtime.wait(actor, job['jobId'])
        assert result['state'] == 'Completed', result
        data = result['outputs']
        assert data['native']['cymcp'] == '0.7.1'
        assert data['native']['version'] == '0.11.0'
        assert data['taskFiles']['exportBeforeFinish']
        assert data['operations'] == runtime.descriptor['operations']
    runtime.close()
