"""Linux process ownership tests against the actual hardened private worker."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest
from m11b_helpers import application,reviewed,wait_for
from peanalyzer.gui.process_safety import acquire_lease,lease_busy,process_identity,signal_owned


def record(name, **evidence):
    if os.environ.get('M11C_RESULTS_DIR'):
        root=Path(os.environ['M11C_RESULTS_DIR'])/'process';root.mkdir(parents=True,exist_ok=True)
        (root/(name+'.json')).write_text(json.dumps(evidence,indent=2)+'\n')


def until(fn,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=fn()
        if result:return result
        time.sleep(.03)
    raise AssertionError('process barrier timeout')


def worker_fixture(root):
    script=root/'contained_worker.py'
    script.write_text('''import os,sys,time,signal,subprocess
from pathlib import Path
from peanalyzer import workflow as w
from peanalyzer.gui import worker
original=w.execute_stage
def stage(plan,node,completed,argv):
    if node.stage_kind=='demux':
        root=Path(plan.output).parent
        # The detached grandchild is adopted by the actual scientific subreaper.
        code="""import os,signal,time,sys
from pathlib import Path
if os.fork():os._exit(0)
os.setsid()
if os.fork():os._exit(0)
signal.signal(signal.SIGTERM,signal.SIG_IGN)
Path(sys.argv[1]).write_text(str(os.getpid()))
while True:time.sleep(.02)
"""
        subprocess.Popen([sys.executable,'-c',code,str(root/'detached-pid')])
        (root/'science-pid').write_text(str(os.getpid()))
        while True:time.sleep(.02)
    return original(plan,node,completed,argv)
w.execute_stage=stage
raise SystemExit(worker.main())
''')
    return script


def fake_core(root):
    p=root/'CRISPResso';p.write_text('#!/bin/sh\nprintf "CRISPResso 2.3.4\\n"\n');p.chmod(0o755);return p


def test_host_lease_survives_acquiring_process_exit(tmp_path):
    # Explicit inherited descriptor keeps the same flock open-file description.
    fd=acquire_lease()
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],pass_fds=(fd,))
    try:
        os.close(fd);assert lease_busy()
        with pytest.raises(ValueError,match='WORKER_BUSY'):acquire_lease()
    finally:child.terminate();child.wait()
    assert not lease_busy()


def test_pid_reuse_guard_never_signals_wrong_identity():
    p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        identity=process_identity(p.pid);identity['start_ticks']+=1
        signal_owned(identity,signal.SIGKILL);assert p.poll() is None
    finally:p.terminate();p.wait()


def test_detached_term_ignoring_descendant_is_reaped_before_cancelled(tmp_path,monkeypatch):
    from peanalyzer.gui.execution import RuntimeSettings
    app,c,content,_,output=application(tmp_path,runtime=RuntimeSettings(crispresso=str(fake_core(tmp_path))))
    script=worker_fixture(tmp_path)
    monkeypatch.setattr('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(script),'--events-fd',str(fd)])
    canary=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
    try:
        response=c.post('/api/v1/jobs',json=reviewed(c,content));assert response.status_code==200,response.text
        key=response.json()['job_id'];until(lambda:(output/'detached-pid').exists())
        pid=int((output/'detached-pid').read_text());assert process_identity(pid)
        assert lease_busy()
        c.post('/api/v1/jobs/'+key+'/cancel',json={})
        # The TERM-ignoring escaped descendant requires bounded KILL escalation.
        final=wait_for(c,key,timeout=20)
        assert final['state']=='CANCELLED' and not process_identity(pid)
        assert not lease_busy() and canary.poll() is None
        assert not (output/'.analysis.m7-lock').exists()
        assert not (output/'analysis/workflow_manifest.json').exists()
        record('detached-cancellation',state=final['state'],detached_alive_after=bool(process_identity(pid)),
            lease_busy_after=lease_busy(),unrelated_canary_alive=canary.poll() is None,
            invocation_lock_present=False,completion_present=False,detached_fixture='double-fork setsid SIGTERM ignored')
    finally:
        app.state.jobs.close();canary.terminate();canary.wait()


def test_server_sigkill_cleans_tree_and_blocks_second_science(tmp_path):
    script=worker_fixture(tmp_path);core=fake_core(tmp_path)
    server=tmp_path/'server.py'
    server.write_text('''import sys,time,json
from pathlib import Path
from m11b_helpers import application,reviewed
from peanalyzer.gui.execution import RuntimeSettings
import peanalyzer.gui.jobs as jobs
root=Path(sys.argv[1]);script=sys.argv[2];core=sys.argv[3]
jobs.worker_command=lambda fd:[sys.executable,script,'--events-fd',str(fd)]
app,c,content,_,out=application(root/'case',runtime=RuntimeSettings(crispresso=core))
r=c.post('/api/v1/jobs',json=reviewed(c,content));assert r.status_code==200,r.text
(root/'accepted').write_text(r.text)
while True:time.sleep(.03)
''')
    env=dict(os.environ);env['PYTHONPATH']=os.pathsep.join([str(Path(__file__).parent.resolve()),*sys.path])
    p=subprocess.Popen([sys.executable,str(server),str(tmp_path),str(script),str(core)],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    canary=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
    try:
        output=tmp_path/'case/outputs'
        until(lambda:(output/'detached-pid').exists())
        escaped=int((output/'detached-pid').read_text());science=int((output/'science-pid').read_text())
        os.kill(p.pid,signal.SIGKILL);p.wait()
        assert lease_busy()  # TERM-ignoring detached child still occupies the lease.
        with pytest.raises(ValueError,match='WORKER_BUSY'):acquire_lease()
        until(lambda:not lease_busy(),timeout=20)
        assert not process_identity(escaped) and not process_identity(science)
        assert canary.poll() is None
        assert not (output/'.analysis.m7-lock').exists()
        assert not (output/'analysis/workflow_manifest.json').exists()
        from peanalyzer.gui.recovery import inspect
        from peanalyzer.gui.execution import RuntimeSettings
        _,pf,state=inspect(output/'analysis',RuntimeSettings(crispresso=str(core)))
        assert state=='RESUMABLE' and pf
        record('server-sigkill',server_signal='SIGKILL',busy_during_cleanup=True,
            scientific_child_alive_after=bool(process_identity(science)),detached_alive_after=bool(process_identity(escaped)),
            lease_busy_after=lease_busy(),unrelated_canary_alive=canary.poll() is None,
            invocation_lock_present=False,completion_present=False,recovery_classification=state)
    finally:
        if p.poll() is None:p.terminate();p.wait(timeout=20)
        canary.terminate();canary.wait()
        if p.stdout:p.stdout.close()
