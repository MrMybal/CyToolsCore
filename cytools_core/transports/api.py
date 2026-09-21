"""Single authenticated dispatch table shared by local and network adapters."""
import copy
from ..errors import CyToolError
from ..schema import validate_document
from ..resources import system_resources


class LocalClient:
    def __init__(self, runtime, principal):
        self.runtime, self.principal = runtime, principal

    def call(self, method, **p):
        validate_document({'protocolVersion':'1.0','id':0,'method':method,'params':p},'request')
        r, actor = self.runtime,self.principal
        if method=='DescribeTool': return copy.deepcopy(r.descriptor)
        if method=='GetCapabilities': return copy.deepcopy(r.descriptor.get('capabilities',[]))
        if method=='ListOperations': return copy.deepcopy(r.descriptor['operations'])
        if method=='DescribeOperation': return r.operation(p['operationId'])
        if method=='ListBackends': return copy.deepcopy(r.descriptor.get('backends',[]))
        if method=='ListModels': return [dict(copy.deepcopy(m),backendId=b['id']) for b in r.descriptor.get('backends',[]) for m in b.get('models',[]) if not p.get('backendId') or b['id']==p['backendId']]
        if method=='GetRuntimeStatus':
            status=r.status()
            # Reservation IDs of other users are not exposed by the public API.
            status['resources'].pop('reservations',None)
            return status
        if method=='GetSystemResources': return system_resources(r.root)
        if method=='Diagnose':
            return {'system':system_resources(r.root),'operations':[
                {'operationId':o['id'],'handlerRegistered':o['id'] in r._handlers} for o in r.descriptor['operations']],
                'note':'Use CanRun with concrete parameters/backend/model for resource and dependency checks.'}
        if method in ('EstimateResources','CanRun'):
            fn=r.estimate_resources if method=='EstimateResources' else r.can_run
            return fn(p['operationId'],p.get('parameters',{}),p.get('backendId',''),p.get('modelId',''))
        if method=='CreateSession': return r.create_session(actor,temporary=p.get('temporary',True),retention_seconds=p.get('retentionSeconds',3600))
        if method=='FinishTask': return r.finish_task(actor,p['sessionId'],cancel_running=p.get('cancelRunning',False))
        if method=='KeepTaskAlive': return r.keep_task_alive(actor,p['sessionId'])
        if method=='ImportFile': return r.import_file(actor,p['sessionId'],p['source'],companions=p.get('companions',[]))
        if method=='ExportJob': return r.export_job(actor,p['jobId'],p['destination'])
        if method=='CloseSession': return r.close_session(actor,p['sessionId'])
        if method=='SubmitJob': return r.submit(actor,p['sessionId'],p['operationId'],p.get('parameters',{}),
            backend_id=p.get('backendId',''),model_id=p.get('modelId',''),priority=p.get('priority','Normal'),
            queue_timeout=p.get('queueTimeout'),execution_timeout=p.get('executionTimeout'))
        if method=='GetJob': return r.get_job(actor,p['jobId'])
        if method=='ListJobs': return r.list_jobs(actor)
        if method=='CancelJob': return r.cancel(actor,p['jobId'])
        if method=='ShareJob': return r.share_job(actor,p['jobId'],p.get('visibility','Owner'),p.get('sharedWith',[]))
        if method=='GetEvents': return r.events(actor,p.get('after',0))
        if method=='ReleaseResources': return r.release_resources(actor,p['level'])
        raise CyToolError('UnknownMethod',f'Unknown method: {method}')

    def dispatch(self, request):
        response={'protocolVersion':'1.0','id':request.get('id') if isinstance(request,dict) else None}
        try:
            validate_document(request,'request')
            response['result']=self.call(request['method'],**request['params'])
        except CyToolError as exc: response['error']=exc.to_dict()
        except (KeyError,TypeError,ValueError) as exc: response['error']=CyToolError('InvalidParameters',str(exc)).to_dict()
        except Exception: response['error']=CyToolError('InternalError','Request failed').to_dict()
        return response
