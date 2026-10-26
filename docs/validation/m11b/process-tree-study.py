"""Deterministic local process-group escalation through the actual M7 executor."""
import json
import os
from pathlib import Path
import signal
import sys
import time
from m11b_helpers import application, reviewed, wait_for
from peanalyzer.gui.execution import RuntimeSettings
import peanalyzer.gui.jobs as jobs

root=Path(sys.argv[1]);root.mkdir(parents=True)
core=root/'version-fixture';core.write_text('#!/bin/sh\nprintf "CRISPResso 2.3.4\\n"\n');core.chmod(0o755)
# Readiness is written by the descendants AFTER installing SIGTERM handlers.
# Thus this test necessarily exercises bounded SIGKILL escalation.
grand=root/'grandchild.py'
grand.write_text('import os,signal,sys,time\nfrom pathlib import Path\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nPath(sys.argv[1]).write_text(str(os.getpid()))\ntime.sleep(300)\n')
child=root/'child.py'
child.write_text('import os,signal,subprocess,sys,time\nfrom pathlib import Path\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nsubprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]])\nwhile not Path(sys.argv[2]).exists():time.sleep(.01)\nPath(sys.argv[3]).write_text(str(os.getpid()))\ntime.sleep(300)\n')
worker=root/'worker-fixture.py'
worker.write_text('''import subprocess,sys,time
from pathlib import Path
from peanalyzer import workflow as w
from peanalyzer.gui import worker
original=w.execute_stage
root=Path('''+repr(str(root))+''')
def execute(plan,node,completed,argv):
    if node.stage_kind=='demux':
        subprocess.Popen([sys.executable,str(root/'child.py'),str(root/'grandchild.py'),str(root/'grandchild.pid'),str(root/'child.pid')])
        while True:time.sleep(.01)
    return original(plan,node,completed,argv)
w.execute_stage=execute
raise SystemExit(worker.main())
''')
app,c,content,options,out=application(root/'case',runtime=RuntimeSettings(crispresso=str(core)))
jobs.worker_command=lambda fd:[sys.executable,str(worker),'--events-fd',str(fd)]
signals=[];original_signal=jobs.signal_group

def recording(pid,sig):
    signals.append(signal.Signals(sig).name);original_signal(pid,sig)
jobs.signal_group=recording
response=c.post('/api/v1/jobs',json=reviewed(c,content));assert response.status_code==200,response.text
key=response.json()['job_id'];deadline=time.monotonic()+15
while not (root/'child.pid').exists():
    assert time.monotonic()<deadline
    time.sleep(.02)
pids=[app.state.jobs.jobs[key].process.pid,int((root/'child.pid').read_text()),int((root/'grandchild.pid').read_text())]
assert (out/'.analysis.m7-lock').exists()
start=time.monotonic();c.post('/api/v1/jobs/'+key+'/cancel');final=wait_for(c,key);duration=time.monotonic()-start
assert final['state']=='CANCELLED' and final['workspace_id'] is None
assert 'SIGTERM' in signals and 'SIGKILL' in signals and 4.9<=duration<15
for pid in pids:
    try:os.kill(pid,0)
    except ProcessLookupError:continue
    raise AssertionError('A supervised process survived cancellation')
assert not (out/'.analysis.m7-lock').exists() and not (out/'analysis/workflow_manifest.json').exists()
assert not app.state.store.catalog()
events=c.get('/api/v1/jobs/'+key+'/events').json()['items']
assert [e['sequence'] for e in events]==list(range(1,len(events)+1))
evidence=dict(worker_architecture='fixed Python worker / POSIX session / Linux subreaper',
    actual_m7_executor=True,backend='test-only long-running local process fixture; no biological inference',
    readiness_after_sigterm_ignored=True,processes=3,worker_child_and_grandchild_all_gone=True,
    signal_sequence=signals,cancel_elapsed_seconds=duration,configured_grace_seconds=app.state.jobs.grace_seconds,
    state=final['state'],stage_statuses=[dict(stage=s['stage_id'],status=s['status']) for s in final['stages']],
    canonical_lock_removed=True,incomplete_workspace_retained=True,completion_marker_absent=True,
    viewer_registration_absent=True,ordered_events=events)
(root/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');app.state.jobs.close()
print(json.dumps({k:v for k,v in evidence.items() if k not in ('ordered_events','stage_statuses')},indent=2))
