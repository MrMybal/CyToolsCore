"""Reference tool with no AI or GPU requirement."""
from importlib.resources import files
from cytools_core import Runtime, load_manifest, CyToolError


def create_runtime(data_dir, **options):
    runtime=Runtime(load_manifest(files('cytool_test').joinpath('CyTool.json')),data_dir,**options)

    def echo(ctx,p): return {'text':p['text']}

    def sleep(ctx,p):
        ctx.cancellation.sleep(p['seconds'])
        return {'sleptSeconds':p['seconds']}

    def generate_file(ctx,p):
        path=ctx.path('outputs/'+p['name'])
        path.write_text(p['text'],encoding='utf-8')
        return {'file':str(path),'mimeType':'text/plain','sizeBytes':path.stat().st_size}

    def allocate_ram(ctx,p):
        buffer=bytearray(p['bytes'])
        # Commit pages for a real (bounded) allocation, then release on return.
        for offset in range(0,len(buffer),4096): buffer[offset]=1
        ctx.observe_resources({'ramBytes':len(buffer)})
        ctx.cancellation.sleep(p['seconds'])
        return {'allocatedBytes':len(buffer)}

    def simulate_vram(ctx,p):
        ctx.cancellation.sleep(p['seconds'])
        return {'simulated':True,'reservedBytes':p['bytes']}

    def fail(ctx,p): raise CyToolError('SimulatedFailure',p['message'],recoverable=True)

    def progress_test(ctx,p):
        for step in range(p['steps']):
            ctx.cancellation.sleep(p['seconds']/p['steps'])
            ctx.progress(100*(step+1)/p['steps'],currentStep='Testing',currentStepIndex=step+1,stepCount=p['steps'])
        return {'steps':p['steps']}

    for name,handler in {'echo':echo,'sleep':sleep,'generate_file':generate_file,'allocate_ram':allocate_ram,
                         'simulate_vram':simulate_vram,'fail':fail,'progress_test':progress_test}.items():
        estimator=None
        if name=='allocate_ram': estimator=lambda p,b,m:{'ramBytes':p['bytes']}
        if name=='simulate_vram': estimator=lambda p,b,m:{'vramBytes':{'simulation':p['bytes']}}
        runtime.register(name,handler,estimate=estimator)
    return runtime
