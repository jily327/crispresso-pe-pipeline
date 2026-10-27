"""Fault injection and repeated real GUI cancellation through the private supervisor."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest
from m11b_helpers import application,reviewed,wait_for
from test_m11b import workflow_fixture_worker
from test_m11c_process import worker_fixture,fake_core,until
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.gui.process_safety import process_identity,lease_busy,signal_owned
from peanalyzer.workflow_models import Session


@pytest.mark.parametrize('fault',['term','kill','pidfd_open','pidfd_send','census'])
def test_containment_fault_retains_lease_until_positive_proof(tmp_path,monkeypatch,fault):
    app,c,content,_,output=application(tmp_path,runtime=RuntimeSettings(crispresso=str(fake_core(tmp_path))))
    script=worker_fixture(tmp_path);original=script.read_text()
    injection='''
import errno
from peanalyzer.gui import supervision,process_safety
fault=FAULT
original_signal=process_safety.signal.pidfd_send_signal
original_open=process_safety.os.pidfd_open
original_census=supervision.census
flag=Path(FLAG)
def send(fd,sig,*args):
    if flag.exists() and (fault=='pidfd_send' or fault=='term' and sig==signal.SIGTERM or fault=='kill' and sig==signal.SIGKILL):
        raise PermissionError(errno.EPERM,'Injected containment refusal')
    return original_signal(fd,sig,*args)
def opening(pid,*args):
    if flag.exists() and fault=='pidfd_open':raise PermissionError(errno.EPERM,'Injected pidfd refusal')
    return original_open(pid,*args)
def census(root,known):
    if flag.exists() and fault=='census':
        # Do not let the injected error overtake the cancellation HTTP request.
        deadline=time.monotonic()+10
        while not (flag.parent/'cancel-sent').exists():
            if time.monotonic()>deadline:raise TimeoutError('Cancellation barrier not released')
            time.sleep(.01)
        raise PermissionError(errno.EPERM,'Injected census refusal')
    return original_census(root,known)
process_safety.signal.pidfd_send_signal=send
process_safety.os.pidfd_open=opening
supervision.census=census
'''.replace('FAULT',repr(fault)).replace('FLAG',repr(str(tmp_path/'fault')))
    # The fixture's top-level imports include signal; no production fault hooks.
    script.write_text(original.replace('raise SystemExit(worker.main())',injection+'\nraise SystemExit(worker.main())'))
    monkeypatch.setattr('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(script),'--events-fd',str(fd)])
    canary=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);owned=[]
    try:
        response=c.post('/api/v1/jobs',json=reviewed(c,content));assert response.status_code==200,response.text
        key=response.json()['job_id'];until(lambda:(output/'detached-pid').exists())
        pid=int((output/'detached-pid').read_text());owned=[process_identity(pid),process_identity(int((output/'science-pid').read_text()))]
        (tmp_path/'fault').touch();c.post('/api/v1/jobs/'+key+'/cancel',json={})
        (tmp_path/'cancel-sent').touch()
        until(lambda:any(e.status=='CONTAINMENT_ERROR' for e in app.state.jobs.jobs[key].events))
        assert process_identity(pid) is not None and lease_busy()
        state=c.get('/api/v1/jobs/'+key).json();assert state['state']=='CANCELLING' and state['error'] is None
        second=reviewed(c,content.model_copy(update={'workspace_name':'second'}))
        assert c.post('/api/v1/jobs',json=second).json()['error']['code']=='WORKER_BUSY'
        assert canary.poll() is None
        # Resolve the fault; the supervisor must retry failed deliveries itself.
        (tmp_path/'fault').unlink()
        until(lambda:not lease_busy(),timeout=15)
        job=wait_for(c,key,lambda value:value['ended_at'] is not None);assert job['state']=='CANCELLED'
        assert all(process_identity(i['pid']) is None for i in owned if i)
        events=app.state.jobs.jobs[key].events
        assert any(e.status=='CONTAINMENT_CONFIRMED' for e in events)
        assert not app.state.store.opened and canary.poll() is None
    finally:
        (tmp_path/'cancel-sent').touch()
        (tmp_path/'fault').unlink(missing_ok=True)
        for item in owned:
            if item:signal_owned(item,signal.SIGKILL)
        app.state.jobs.close();canary.terminate();canary.wait()


@pytest.mark.parametrize('attempt',range(80))
def test_signal_once_preserves_real_gui_cleanup_records(tmp_path,monkeypatch,attempt):
    case=application(tmp_path);app,c,content,_,out=case
    workflow_fixture_worker(case,monkeypatch,tmp_path,'cancel')
    script=tmp_path/'workflow_fixture_worker.py'
    # Deliberately widen the historical repeated-TERM cleanup window.
    script.write_text(script.read_text().replace('original=w.execute_stage',
        "original_json=w.atomic_json\ndef slow_json(path,value):\n    if '/failures/' in str(path) or '/sessions/' in str(path):time.sleep(.06)\n    return original_json(path,value)\nw.atomic_json=slow_json\noriginal=w.execute_stage"))
    canary=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        r=c.post('/api/v1/jobs',json=reviewed(c,content));assert r.status_code==200,r.text
        key=r.json()['job_id'];until(lambda:(out/'early-child-pid').exists())
        child=int((out/'early-child-pid').read_text())
        c.post('/api/v1/jobs/'+key+'/cancel',json={})
        job=wait_for(c,key);assert job['state']=='CANCELLED' and not job['workspace_id']
        sessions=list((out/'analysis/workflow/sessions').glob('*.json'));failures=list((out/'analysis/workflow/failures').glob('*.json'))
        assert len(sessions)==len(failures)==1
        session=Session.model_validate_json(sessions[0].read_bytes());failure=json.loads(failures[0].read_text())
        assert session.failed_stage=='demux' and failure['stage_id']=='demux'
        assert session.session_id==failure['session_id'] and failure['error_class']=='SystemExit'
        assert not (out/'.analysis.m7-lock').exists() and not (out/'analysis/workflow_manifest.json').exists()
        assert process_identity(child) is None and not lease_busy() and canary.poll() is None
        assert not app.state.store.opened
    finally:app.state.jobs.close();canary.terminate();canary.wait()


def test_supervisor_exit_without_ack_is_not_containment(tmp_path,monkeypatch):
    app,c,content,_,_=application(tmp_path)
    script=tmp_path/'unconfirmed.py'
    script.write_text("import os,sys,json,time\nevents=os.fdopen(int(sys.argv[-1]),'w',buffering=1)\njson.load(sys.stdin)\nevents.write(json.dumps({'status':'SUPERVISOR_READY'})+'\\n')\n")
    monkeypatch.setattr('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(script),'--events-fd',str(fd)])
    key=None
    try:
        r=c.post('/api/v1/jobs',json=reviewed(c,content));assert r.status_code==200;key=r.json()['job_id']
        final=wait_for(c,key)
        assert final['state']=='FAILED' and final['error']['code']=='CANCELLATION_INCOMPLETE'
        assert lease_busy() and app.state.jobs.active==key and not app.state.store.opened
    finally:
        # This fixed test worker never forked. Only auditor cleanup releases its
        # deliberately retained descriptor after proving the worker has exited.
        if key:
            job=app.state.jobs.jobs[key];job.thread.join(5)
            assert job.process.poll() is not None
            if job.lease_fd is not None:os.close(job.lease_fd);job.lease_fd=None
            app.state.jobs.active=None
        app.state.jobs.close()


def test_disappearance_during_pidfd_signal_is_expected(monkeypatch):
    from peanalyzer.gui import process_safety as p
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        birth=p.process_identity(child.pid)
        monkeypatch.setattr(p.signal,'pidfd_send_signal',lambda *args:(_ for _ in ()).throw(ProcessLookupError()))
        p.signal_owned(birth,signal.SIGTERM)
        assert p.process_identity(child.pid)['start_ticks']==birth['start_ticks']
    finally:child.kill();child.wait()
