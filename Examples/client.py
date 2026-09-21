"""python Examples/client.py URL; credentials in CYTOOLS_TOKEN."""
import os
import sys
import time
from cytools_core.transports.http import HTTPClient

client=HTTPClient(sys.argv[1],os.environ['CYTOOLS_TOKEN'])
print(client.call('DescribeTool')['name'])
session=client.call('CreateSession')
job=client.call('SubmitJob',sessionId=session['sessionId'],operationId='echo',parameters={'text':'Python client'})
while job['state'] not in ('Completed','Failed','Cancelled'):
    time.sleep(.05)
    job=client.call('GetJob',jobId=job['jobId'])
print(job)
client.call('CloseSession',sessionId=session['sessionId'])
raise SystemExit(0 if job['state']=='Completed' else 1)
