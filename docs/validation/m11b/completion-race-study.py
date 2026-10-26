"""Cancel exactly after authoritative worker verification, before M10 publication."""
import json,os,sys
from pathlib import Path
from m11b_helpers import application,reviewed,wait_for
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.workflow import verify_workflow_output
root=Path(sys.argv[1])
app,c,content,options,out=application(root,runtime=RuntimeSettings(crispresso=os.environ['M3_CORE_EXECUTABLE']))
observe=app.state.jobs._observe
cancelled=[]
def boundary(job,event):
    observe(job,event)
    if event.get('status')=='VERIFIED_SUCCESS':
        cancelled.append(app.state.jobs.cancel(job.view.job_id).state)
app.state.jobs._observe=boundary
response=c.post('/api/v1/jobs',json=reviewed(c,content));assert response.status_code==200,response.text
job=wait_for(c,response.json()['job_id'],timeout=180)
assert cancelled==['CANCELLING'] and job['state']=='CANCELLED'
assert job['workspace_id'] is None and not app.state.store.catalog()
# Science had already committed and verified. Do not destroy valid backend
# manifests just to manufacture an incomplete output for a publication cancel.
manifest=verify_workflow_output(out/'analysis');assert manifest.status=='COMPLETED'
evidence=dict(state=job['state'],cancel_accepted_at='VERIFIED_SUCCESS event before viewer publication',
    workspace_id=job['workspace_id'],viewer_registered=False,existing_m7_completion_preserved=True,
    independent_workflow_verifier=manifest.status,scientific_manifest_not_edited=True)
(root/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2));app.state.jobs.close()
