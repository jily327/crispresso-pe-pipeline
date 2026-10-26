"""Browser qualification fixtures; no test controls enter application routes."""
import json
import os
from pathlib import Path
import shutil
import sys
import uvicorn
from m7_fixtures import fixture
from m8_fixtures import fixture as nuclease
from peanalyzer import workflow as w
from peanalyzer.gui.app import create_app
from peanalyzer.gui.execution import RuntimeSettings
import peanalyzer.gui.jobs as jobs

root=Path(os.environ['M11C_E2E_ROOT']);root.mkdir(parents=True,exist_ok=True)
names=['pe-resume','nuclease-resume','force','stale','completed','cancel','detached','kill']
paths=[]
for name in names:
    output=root/name/'workflow';paths.append(output)
    if os.environ.get('M11C_REUSE_FIXTURES')=='1':continue
    options=nuclease(root/name/'inputs',[[('WT',12),('deletion',4),('net_zero',4)]]) if name=='nuclease-resume' else fixture(root/name/'inputs',samples=1,copies=2)
    options.update(output=output,crispresso=os.environ['M3_CORE_EXECUTABLE'],title='Recovery '+name)
    w.execute_workflow(**options)
    plan=w.load(output/'workflow/plan.json',w.Plan)
    if name!='completed':
        (output/'workflow_manifest.json').unlink()
        node=next(n for n in plan.nodes if n.stage_kind=='report')
        (output/w.stage_manifest_path(node)).unlink()
        if name!='force':shutil.rmtree(output/'report')
    if name in ('cancel','detached','kill'):(root/name/'pause-report').write_text('pause')
    if name in ('detached','kill'):(root/name/'detach-test').write_text('test-only')
(root/'server-pid').write_text(str(os.getpid()))
app=create_app(token='e2e-local-token',recovery_workspaces=paths,
    runtime=RuntimeSettings(crispresso=os.environ['M3_CORE_EXECUTABLE']))
jobs.worker_command=lambda fd:[sys.executable,str(Path(__file__).with_name('m11c_recovery_worker.py')),'--events-fd',str(fd)]
uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('M11C_E2E_PORT','8767')),access_log=False)
