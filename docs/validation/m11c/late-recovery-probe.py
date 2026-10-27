"""Independent post-acceptance TOCTOU and forced-recovery cancellation probes.
Uses synthetic browser qualification output only; no production hooks.
"""
import argparse,json,sys,time
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from peanalyzer.gui.app import create_app
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer import workflow as w
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--synthetic-workspace',required=True,type=Path,help='Completed disposable synthetic workflow; this probe intentionally mutates it')
parser.add_argument('--core',required=True)
parser.add_argument('--tests-root',required=True,type=Path)
parser.add_argument('--evidence',required=True,type=Path)
args=parser.parse_args()
sys.path.insert(0,str(args.tests_root.resolve()))
from m11b_helpers import wait_for
from test_m11b_integration import full_science
root=args.synthetic_workspace.resolve()
w.verify_workflow_output(root)
expected=full_science(root)
app=create_app(token='test',recovery_workspaces=[root],runtime=RuntimeSettings(crispresso=args.core))
c=TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
def preview(force):
    reg=c.get('/api/v1/recovery/workspaces').json()[0]['registration_id']
    v=c.post('/api/v1/recovery',json={'registration_id':reg}).json()
    if force:v=c.post('/api/v1/recovery/'+v['recovery_id']+'/preview',json={'revision':v['revision'],'force':force}).json()
    assert v['executable'],v
    return v

def accept(v):
    r=c.post('/api/v1/recovery/'+v['recovery_id']+'/execute',json=dict(revision=v['revision'],recovery_plan_sha256=v['recovery_plan_sha256'],confirmed=True))
    assert r.status_code==200,r.text
    return r.json()['job_id']

def until(path):
    end=time.monotonic()+30
    while not path.exists():
        assert time.monotonic()<end,path
        time.sleep(.02)

(root/'workflow_manifest.json').unlink()
(root.parent/'pause-report').write_text('test')
(root.parent/'report-ready').unlink(missing_ok=True)
with patch('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(args.tests_root.resolve()/'m11c_recovery_worker.py'),'--events-fd',str(fd)]):
    key=accept(preview(['report']));until(root.parent/'report-ready')
    c.post('/api/v1/jobs/'+key+'/cancel',json={});job=wait_for(c,key)
    assert job['state']=='CANCELLED' and job['workspace_id'] is None
    assert not (root/'workflow_manifest.json').exists()
(root.parent/'pause-report').unlink()
key=accept(preview([]));assert wait_for(c,key)['state']=='COMPLETED'
assert full_science(root)==expected
# A fresh forced plan is accepted, but its worker waits BEFORE recovery preflight.
(root/'workflow_manifest.json').unlink()
script=root.parent/'late_probe_worker.py'
script.write_text('''import sys,time
from pathlib import Path
from peanalyzer.gui import recovery,worker
original=recovery.run_recovery
def paused(spec,emit):
    parent=Path(spec.output).parent
    (parent/'acceptance-ready').write_text('ready')
    while (parent/'acceptance-pause').exists():time.sleep(.02)
    original(spec,emit)
recovery.run_recovery=paused
raise SystemExit(worker.main())
''')
(root.parent/'acceptance-pause').write_text('test')
(root.parent/'acceptance-ready').unlink(missing_ok=True)
with patch('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(script),'--events-fd',str(fd)]):
    key=accept(preview(['report']));until(root.parent/'acceptance-ready')
    (root/'late-foreign-file').write_text('must survive')
    before={str(p.relative_to(root)):w.sha(p) for p in root.rglob('*') if p.is_file()}
    (root.parent/'acceptance-pause').unlink()
    job=wait_for(c,key)
    assert job['state']=='FAILED' and job['error']['code']=='RECOVERY_PLAN_CHANGED',job
    assert before=={str(p.relative_to(root)):w.sha(p) for p in root.rglob('*') if p.is_file()}
    assert (root/'report/report_manifest.json').is_file()
app.state.jobs.close()
evidence=dict(forced_report_cancellation='CANCELLED',no_completion_registration=True,reinspection_and_resume='COMPLETED',
    forced_cancel_science_parity=True,post_acceptance_workspace_mutation='RECOVERY_PLAN_CHANGED',
    failed_before_invalidation=True,all_preflight_failure_workspace_file_hashes_unchanged=True,foreign_file_preserved=True)
args.evidence.write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps(evidence))
