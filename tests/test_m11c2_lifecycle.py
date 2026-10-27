"""Pre-cancel diagnostics, authoritative terminal decisions and delivery retries."""
import json
import os
from pathlib import Path
import signal
import sys
import pytest
from m11b_helpers import application,reviewed,wait_for
from test_m11c_process import until,fake_core
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.gui.process_safety import lease_busy
from peanalyzer.gui.jobs import TERMINAL


def diagnostic_worker(tmp_path,monkeypatch,behavior):
    """Inject faults into the real supervisor, before any cancellation request."""
    script=tmp_path/'diagnostic_worker.py'
    script.write_text('''import errno,os,sys,time
from pathlib import Path
from peanalyzer import workflow as w
from peanalyzer.gui import worker,supervision
root=Path('''+repr(str(tmp_path))+''')
behavior='''+repr(behavior)+'''
original_census=supervision.census
def census(*args):
    if (root/'fault').exists():
        (root/'fault-hit').touch()
        raise PermissionError(errno.EPERM,'Injected pre-cancel census failure')
    return original_census(*args)
supervision.census=census
original_supervise=supervision.supervise
def supervise(*args,**kwargs):
    return original_supervise(*args,**kwargs,uncertainty_timeout=1 if behavior=='persistent' else 30,grace=.2)
supervision.supervise=supervise
original=w.execute_stage
def execute(plan,node,completed,argv):
    if node.stage_kind=='demux':
        (root/'science-ready').touch()
        while not (root/'release-science').exists():time.sleep(.01)
        if behavior=='failure':raise RuntimeError('Real stage failure after diagnostic')
    return original(plan,node,completed,argv)
w.execute_stage=execute
# Lightweight metrics retains the real pipeline, final verifier and registration.
from peanalyzer.metrics import collect_metrics
def metrics(**kwargs):
    output=Path(kwargs.pop('output'));output.mkdir(parents=True);kwargs.pop('core')
    result=collect_metrics(**kwargs,comparator_root=output/'comparator')
    (output/'result.json').write_text(result.model_dump_json(indent=2)+'\\n')
    (output/'execution_failures.json').write_text('{}\\n')
    return result
w.run_metrics=metrics
raise SystemExit(worker.main())
''')
    monkeypatch.setattr('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(script),'--events-fd',str(fd)])


def evidence(name,events,final):
    if os.environ.get('M11C_RESULTS_DIR'):
        root=Path(os.environ['M11C_RESULTS_DIR'])/'m11c2';root.mkdir(exist_ok=True)
        (root/(name+'.json')).write_text(json.dumps(dict(events=[e.model_dump() for e in events],final=final),indent=2)+'\n')


@pytest.mark.parametrize('behavior',['success','cancel','failure','persistent'])
def test_diagnostic_during_run_has_single_authoritative_terminal_result(tmp_path,monkeypatch,behavior):
    app,c,content,_,out=application(tmp_path,runtime=RuntimeSettings(crispresso=str(fake_core(tmp_path))))
    diagnostic_worker(tmp_path,monkeypatch,behavior);job=None
    try:
        r=c.post('/api/v1/jobs',json=reviewed(c,content));assert r.status_code==200,r.text
        key=r.json()['job_id'];job=app.state.jobs.jobs[key]
        until(lambda:(tmp_path/'science-ready').exists());(tmp_path/'fault').touch()
        until(lambda:any(e.status=='CONTAINMENT_ERROR' for e in job.events))
        running=c.get('/api/v1/jobs/'+key).json()
        assert running['state']=='RUNNING' and running['cancellable'] and running['error'] is None
        assert not app.state.store.opened and lease_busy()
        if behavior=='cancel':
            cancelling=c.post('/api/v1/jobs/'+key+'/cancel',json={}).json()
            assert cancelling['state']=='CANCELLING'
        if behavior=='persistent':
            final=wait_for(c,key,timeout=10)
            assert final['state']=='FAILED' and final['error']['code']=='CANCELLATION_INCOMPLETE'
            assert job.process.poll() is None and lease_busy() and not app.state.store.opened
            second=reviewed(c,content.model_copy(update={'workspace_name':'second'}))
            assert c.post('/api/v1/jobs',json=second).json()['error']['code']=='WORKER_BUSY'
        (tmp_path/'fault').unlink();(tmp_path/'release-science').touch()
        until(lambda:not lease_busy(),timeout=30);job.thread.join(5)
        final=wait_for(c,key)
        expected={'success':'COMPLETED','cancel':'CANCELLED','failure':'FAILED','persistent':'FAILED'}[behavior]
        assert final['state']==expected
        assert bool(final['workspace_id'])==bool(app.state.store.opened)==(behavior=='success')
        if behavior in {'success','cancel'}:assert final['error'] is None
        if behavior=='failure':assert 'Real stage failure' in final['error']['detail']
        terminals=[e for e in job.events if e.status in TERMINAL and e.stage_id is None]
        assert len(terminals)==1 and terminals[0].status==expected
        assert all(e.state not in TERMINAL for e in job.events if e.status=='CONTAINMENT_ERROR')
        evidence(behavior,job.events,final)
    finally:
        (tmp_path/'fault').unlink(missing_ok=True);(tmp_path/'release-science').touch()
        app.state.jobs.close()
        if job and job.thread:job.thread.join(10)


@pytest.mark.parametrize('first',sorted(TERMINAL))
def test_terminal_guard_rejects_all_later_observations_and_terminal_decisions(tmp_path,monkeypatch,first):
    from peanalyzer.gui.jobs import Job
    from peanalyzer.gui.job_models import JobView
    app,_,_,_,_=application(tmp_path)
    view=JobView(job_id='test',draft_id='test',revision=1,state='RUNNING',analysis_name='Guard',analysis_mode='precise_edit',
        target_name='T1',output_proposal='out',plan_identity_sha256='a'*64,scientific_identity_sha256='b'*64,
        execution_spec_sha256='c'*64,input_metadata=[],warnings=[],stages=[],total_stages=0,started_at='test')
    job=Job(view,b'{}');store=app.state.jobs
    with store.lock:assert store._finish(job,first)
    frozen=job.view.model_dump();events=list(job.events)
    for state in TERMINAL:
        with store.lock:assert not store._finish(job,state)
    for status in ['WORKER_READY','RUNNING','VERIFIED_SUCCESS','CONTAINMENT_ERROR','CONTAINMENT_FAILED','CONTAINMENT_CONFIRMED']:
        store._observe(job,dict(status=status))
    assert job.view.model_dump()==frozen and job.events==events


@pytest.mark.parametrize('sig',[signal.SIGTERM,signal.SIGKILL])
def test_failed_delivery_retries_are_rate_limited_success_is_once_per_birth(monkeypatch,sig):
    from peanalyzer.gui import supervision as s
    attempts=[];success=[]
    def send(item,signum):
        attempts.append((item['pid'],item['start_ticks'],signum))
        if len(attempts)==1:raise PermissionError('Transient signal failure')
        success.append(attempts[-1])
    monkeypatch.setattr(s,'signal_owned',send);phases=s.SignalPhases();birth=dict(pid=42,start_ticks=10)
    with pytest.raises(PermissionError):phases.send(birth,sig,0)
    for now in [.01,.05,.1,.24]:phases.send(birth,sig,now)
    assert len(attempts)==1
    phases.send(birth,sig,.25)
    for now in [.26,.5,10]:phases.send(birth,sig,now)
    phases.send(dict(pid=42,start_ticks=11),sig,10)
    assert len(attempts)==3 and success==[(42,10,sig),(42,11,sig)]


def test_exit_before_retry_does_not_signal_reused_pid(monkeypatch):
    from peanalyzer.gui import supervision as s,process_safety as p
    import subprocess
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    phases=s.SignalPhases();birth=p.process_identity(child.pid)
    try:
        monkeypatch.setattr(s,'signal_owned',lambda *a:(_ for _ in ()).throw(PermissionError()))
        with pytest.raises(PermissionError):phases.send(birth,signal.SIGTERM,0)
        child.terminate();child.wait();monkeypatch.setattr(s,'signal_owned',p.signal_owned)
        monkeypatch.setattr(p.signal,'pidfd_send_signal',lambda *a:pytest.fail('Exited birth signalled'))
        phases.send(birth,signal.SIGTERM,1)
    finally:
        if child.poll() is None:child.kill();child.wait()
