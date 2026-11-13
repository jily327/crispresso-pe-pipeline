"""Genuine pinned-image failure and retry; never substituted by a fake backend."""
import json
import os
from pathlib import Path
import shlex
import pytest
from m7_fixtures import fixture
from peanalyzer import workflow as w
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.gui.recovery import inspect


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('V101_DOCKER_INTEGRATION')!='1',reason='requires local qualified CRISPResso 2.3.4 container; V101_DOCKER_INTEGRATION=1')
def test_real_nonempty_crispresso_partial_failure_and_repeated_recovery(tmp_path):
    options=fixture(tmp_path/'inputs',samples=1,copies=1,reads=20)
    flag=tmp_path/'fail';flag.touch()
    driver=tmp_path/'interrupt_backend.py'
    driver.write_text('''import os,sys,subprocess,time,signal
from pathlib import Path
flag=Path(sys.argv[1]);args=sys.argv[2:]
if '--version' in args or not flag.exists():os.execvp('CRISPResso',['CRISPResso',*args])
p=subprocess.Popen(['CRISPResso',*args],start_new_session=True)
end=time.monotonic()+45
while time.monotonic()<end:
    files=[f for f in Path('output').rglob('*') if f.is_file() and f.stat().st_size]
    if files:
        os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=15)
        Path('fault-injection.json').write_text(__import__('json').dumps({'nonempty_backend_files':[str(f) for f in files]}))
        sys.exit(37)
    if p.poll() is not None:raise RuntimeError('backend exited before partial-output barrier')
    time.sleep(.01)
os.killpg(p.pid,signal.SIGKILL);p.wait();raise RuntimeError('partial-output barrier timed out')
''')
    wrapper=tmp_path/'CRISPResso'
    wrapper.write_text('#!/bin/sh\nexec env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock exec --user "$(id -u):$(id -g)" --workdir "$PWD" peanalyzer-crispresso-234 python '+shlex.quote(str(driver))+' '+shlex.quote(str(flag))+' "$@"\n')
    wrapper.chmod(0o755);options['crispresso']=str(wrapper)
    for resume in (False,True):
        with pytest.raises(w.WorkflowError,match='BACKEND_EXECUTION_FAILED'):
            w.execute_workflow(**options,resume=resume)
        assert not (options['output']/'metrics/bc001/T1').exists()
        assert not (options['output']/'workflow_manifest.json').exists()
        _,pf,state=inspect(options['output'],RuntimeSettings(crispresso=str(wrapper)),[])
        assert state=='RESUMABLE' and pf
    attempts=list(tmp_path.glob('.workflow.metrics-attempt-*/output'))
    assert len(attempts)==2
    for attempt in attempts:
        proofs=list(attempt.rglob('fault-injection.json'))
        assert proofs and all(json.loads(p.read_text())['nonempty_backend_files'] for p in proofs)
        (attempt/'foreign.txt').write_text('user data remains')
    flag.unlink()
    w.resume_workflow(**options)
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'
    result=json.loads((options['output']/'metrics/bc001/T1/result.json').read_text())
    assert result['target_metrics']['total_precise_pe']['numerator']==1
    assert result['target_metrics']['total_precise_pe']['denominator']==20
    assert all((p/'foreign.txt').read_text()=='user data remains' for p in attempts)


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get('V101_DOCKER_INTEGRATION')!='1',reason='requires local qualified Docker image; V101_DOCKER_INTEGRATION=1')
def test_gui_cancel_during_genuine_nonempty_core_then_resume(tmp_path):
    """Pause actual Core after its first write, then cancel through the real API.

    The qualification-only container watches a lease held by its local wrapper.
    This contains owner SIGKILL as well as ordinary cancellation signals.
    """
    import subprocess
    import time
    from m11b_helpers import application,reviewed,wait_for
    from peanalyzer.metrics.production import RUNTIME_DIGEST
    control=tmp_path/'control';control.mkdir()
    pause=control/'pause';pause.touch();ready=control/'ready.json'
    driver=control/'pause_core.py'
    driver.write_text('''import os,sys,signal,subprocess,time,json,fcntl
from pathlib import Path
pause,ready,lease=map(Path,sys.argv[1:4]);args=sys.argv[4:]
owner=open(lease,'r+')
def owner_alive():
    try:fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return True
    fcntl.flock(owner,fcntl.LOCK_UN);return False
p=None
def terminate(signum,frame):
    if p is not None and p.poll() is None:
        os.killpg(p.pid,signal.SIGCONT);os.killpg(p.pid,signal.SIGTERM)
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
    (ready.parent/'stopped.json').write_text(json.dumps({'owner_alive':owner_alive(),'backend_returncode':p.returncode if p else None}))
    sys.exit(143)
signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
if not owner_alive():terminate(signal.SIGTERM,None)
p=subprocess.Popen(['CRISPResso',*args],start_new_session=True)
end=time.monotonic()+60
paused=False
while p.poll() is None:
    if not owner_alive():terminate(signal.SIGTERM,None)
    if not pause.exists() or paused:time.sleep(.01);continue
    if time.monotonic()>=end:raise RuntimeError('Core partial-output barrier timeout')
    files=[f for f in Path('output').rglob('*') if f.is_file() and f.stat().st_size]
    if files:
        os.killpg(p.pid,signal.SIGSTOP);os.waitpid(p.pid,os.WUNTRACED)
        temporary=ready.with_suffix('.tmp')
        temporary.write_text(json.dumps({'nonempty_files':[str(f) for f in files],'cwd':os.getcwd()}));temporary.rename(ready)
        paused=True
    time.sleep(.01)
sys.exit(p.returncode)
''')
    docker=['env','-u','DOCKER_HOST','-u','DOCKER_CONTEXT','-u','DOCKER_TLS','-u','DOCKER_TLS_VERIFY','-u','DOCKER_CERT_PATH','docker','--host=unix:///var/run/docker.sock']
    base=docker+['run','--rm','--init','--sig-proxy=false','--network','none','--user',f'{os.getuid()}:{os.getgid()}','-v','/tmp:/tmp','-v','/workspace:/workspace:ro']
    wrapper=control/'CRISPResso'
    import sys
    wrapper.write_text('#!'+sys.executable+'\n'+f'base={base!r}\ncontrol={str(control)!r}\nimage={RUNTIME_DIGEST!r}\ndriver={str(driver)!r}\npause={str(pause)!r}\nready={str(ready)!r}\n'+'''import os,sys,subprocess,fcntl
from pathlib import Path
cidfile=Path(control)/('cid.'+str(os.getpid()))
lease=Path(control)/('lease.'+str(os.getpid()))
owner=os.open(lease,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC,0o600)
fcntl.flock(owner,fcntl.LOCK_EX)
version=sys.argv[1:]==['--version']
command=base+['--workdir',os.getcwd(),'--cidfile',str(cidfile)]
command+=['--entrypoint','CRISPResso',image] if version else ['--entrypoint','python',image,driver,pause,ready,str(lease)]
child=subprocess.Popen(command+sys.argv[1:])
code=child.wait()
if version:cidfile.unlink(missing_ok=True)
sys.exit(code)
''')
    wrapper.chmod(0o755)
    app,c,content,_,out=application(tmp_path/'gui',runtime=RuntimeSettings(crispresso=str(wrapper)))
    try:
        response=c.post('/api/v1/jobs',json=reviewed(c,content));assert response.status_code==200,response.text
        key=response.json()['job_id'];end=time.monotonic()+120
        while not ready.exists():
            job=c.get('/api/v1/jobs/'+key).json()
            assert job['state'] not in {'FAILED','COMPLETED','CANCELLED'},job
            assert time.monotonic()<end,'actual Core did not reach nonempty-output barrier'
            time.sleep(.03)
        assert json.loads(ready.read_text())['nonempty_files']
        ids=[p.read_text().strip() for p in control.glob('cid.*')]
        assert len(ids)==1
        observed=json.loads(subprocess.check_output(docker+['container','inspect',ids[0]],text=True))[0]
        assert observed['Config']['Image']==RUNTIME_DIGEST
        assert c.post('/api/v1/jobs/'+key+'/cancel',json={}).status_code==200
        cancelled=wait_for(c,key,timeout=120)
        assert cancelled['state']=='CANCELLED' and not cancelled['workspace_id'],cancelled
        end=time.monotonic()+15
        while True:
            inspected=subprocess.run(docker+['container','inspect',ids[0]],capture_output=True,text=True)
            if inspected.returncode:break
            state=json.loads(inspected.stdout)[0]['State']
            if not state['Running']:
                assert state['Pid']==0,state
                break
            assert time.monotonic()<end,('Docker-backed Core survived cancellation',state)
            time.sleep(.05)
        assert (control/'stopped.json').exists(),'container guard did not confirm its backend stopped'
        assert json.loads((control/'stopped.json').read_text())['owner_alive'] is False
        workspace=out/'analysis'
        assert not (workspace/'workflow_manifest.json').exists()
        attempts=list(out.glob('.analysis.metrics-attempt-*/output'))
        assert attempts and any(f.stat().st_size for p in attempts for f in p.rglob('CRISPResso_RUNNING_LOG.txt'))
        assert not (workspace/'metrics/bc001/T1').exists()
        pause.unlink()
        view=c.post('/api/v1/jobs/'+key+'/recovery',json={}).json()
        assert view['classification']=='RESUMABLE' and view['executable'],view
        response=c.post(f"/api/v1/recovery/{view['recovery_id']}/execute",json=dict(revision=view['revision'],recovery_plan_sha256=view['recovery_plan_sha256'],confirmed=True))
        assert response.status_code==200,response.text
        result=wait_for(c,response.json()['job_id'],timeout=240)
        assert result['state']=='COMPLETED',result
        assert w.verify_workflow_output(workspace).status=='COMPLETED'
        metric=json.loads((workspace/'metrics/bc001/T1/result.json').read_text())['target_metrics']['total_precise_pe']
        assert (metric['numerator'],metric['denominator'])==(2,24)
    finally:
        app.state.jobs.close()
        # Cleanup only explicitly recorded containers created by this test.
        for path in control.glob('cid.*'):
            cid=path.read_text().strip()
            if len(cid)==64 and all(c in '0123456789abcdef' for c in cid):
                subprocess.run(docker+['stop','--time','2',cid],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
