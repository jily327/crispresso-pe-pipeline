"""Adversarial acceptance and real process supervision, without expensive science."""
import copy
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
import pytest
from m11b_helpers import application, reviewed, wait_for
from peanalyzer.gui.execution import ExecutionSpec, revalidate_execution, materialize
from peanalyzer.gui.job_models import JobSubmission
from peanalyzer.gui.workspace import ViewerError
from peanalyzer.workflow_storage import digest, WorkflowError


@pytest.fixture
def case(tmp_path):
    value=application(tmp_path)
    yield value
    value[0].state.jobs.close()


@pytest.fixture
def held(case,monkeypatch):
    app,client,content,*_=case;release=threading.Event();original=app.state.jobs._supervise
    def delayed(job):
        release.wait(10)
        original(job)
    monkeypatch.setattr(app.state.jobs,'_supervise',delayed)
    yield release
    release.set()


def submit(case):
    app,client,content,*_=case;request=reviewed(client,content)
    response=client.post('/api/v1/jobs',json=request)
    assert response.status_code==200,response.text
    return request,response.json()


@pytest.mark.parametrize('extra',['targets','samples','crispresso','command','module','force','resume','output','runtime_digest'])
def test_submission_rejects_scientific_or_command_replacements(case,extra):
    app,c,content,*_=case;r=reviewed(c,content);r[extra]='untrusted'
    assert c.post('/api/v1/jobs',json=r).status_code==422
    assert not app.state.jobs.jobs


@pytest.mark.parametrize('change',['revision','plan_identity_sha256','scientific_identity_sha256','missing_validation','missing_output'])
def test_submission_stale_guards(case,change):
    app,c,content,*_=case
    if change=='missing_output':content.output_root=None;content.workspace_name=''
    r=reviewed(c,content)
    if change=='revision':r[change]+=1
    elif change in ('plan_identity_sha256','scientific_identity_sha256'):r[change]='0'*64
    elif change=='missing_validation':app.state.drafts.drafts[r['draft_id']].validation=None
    assert c.post('/api/v1/jobs',json=r).status_code==409
    assert not app.state.jobs.jobs


@pytest.mark.parametrize('phase',['before_review','before_submit','after_acceptance'])
def test_raw_change_fails_before_worker_writes(case,held,phase):
    app,c,content,options,out=case;r=reviewed(c,content)
    if phase=='after_acceptance':
        response=c.post('/api/v1/jobs',json=r);assert response.status_code==200
    options['r1'].write_bytes(options['r1'].read_bytes()+b'changed')
    if phase=='before_review':assert c.get(f"/api/v1/drafts/{r['draft_id']}/preview?revision={r['revision']}").status_code==409
    elif phase=='before_submit':assert c.post('/api/v1/jobs',json=r).status_code==409
    else:
        held.set();job=wait_for(c,response.json()['job_id'])
        assert job['state']=='FAILED' and job['error']['code']=='INPUT_CHANGED'
    assert list(out.iterdir())==[]


@pytest.mark.parametrize('phase',['before_submit','after_acceptance'])
@pytest.mark.parametrize('kind',['file','directory','workspace','symlink','parent'])
def test_output_races_fail_without_modifying_foreign_content(case,held,tmp_path,phase,kind):
    app,c,content,options,out=case;r=reviewed(c,content)
    if phase=='after_acceptance':response=c.post('/api/v1/jobs',json=r);assert response.status_code==200
    target=out/'analysis'
    if kind=='file':target.write_text('foreign')
    elif kind in ('directory','workspace'):
        target.mkdir();(target/('workflow_manifest.json' if kind=='workspace' else 'sentinel')).write_text('foreign')
    elif kind=='symlink':target.symlink_to(options['r1'])
    else:out.rename(tmp_path/'old-output');out.mkdir();(out/'sentinel').write_text('foreign')
    before={str(p):p.read_bytes() for p in out.rglob('*') if p.is_file()}
    if phase=='before_submit':assert c.post('/api/v1/jobs',json=r).status_code==409
    else:
        held.set();job=wait_for(c,response.json()['job_id']);assert job['state']=='FAILED'
        assert job['finished_stages']==0
    assert {str(p):p.read_bytes() for p in out.rglob('*') if p.is_file()}==before
    assert not app.state.store.opened


def test_accepted_spec_is_immutable_busy_and_early_cancel(case,held):
    app,c,content,_,out=case;r,job=submit(case)
    assert job['scientific_identity_sha256']==r['scientific_identity_sha256']
    assert job['plan_identity_sha256']==r['plan_identity_sha256']
    accepted=app.state.jobs.jobs[job['job_id']]
    spec=ExecutionSpec.model_validate_json(accepted.payload)
    assert digest(spec)==job['execution_spec_sha256']
    for method,path,body in [('PATCH','',dict(revision=1,content=content.model_dump())),('POST','/validate',dict(revision=1)),('DELETE','?revision=1',None)]:
        response=c.request(method,'/api/v1/drafts/'+r['draft_id']+path,json=body)
        assert response.status_code==409 and response.json()['error']['code']=='DRAFT_LOCKED'
    second=reviewed(c,content.model_copy(update={'workspace_name':'second'}))
    assert c.post('/api/v1/jobs',json=second).json()['error']['code']=='WORKER_BUSY'
    assert c.post('/api/v1/jobs/'+job['job_id']+'/cancel').json()['state']=='CANCELLING'
    assert c.post('/api/v1/jobs/'+job['job_id']+'/cancel').json()['state']=='CANCELLING'
    held.set();final=wait_for(c,job['job_id']);assert final['state']=='CANCELLED'
    assert list(out.iterdir())==[] and not app.state.store.opened
    assert c.post('/api/v1/jobs/'+job['job_id']+'/cancel').json()==final
    assert app.state.jobs.active is None


def fixture_worker(monkeypatch,tmp_path,behavior='child'):
    """Test-only launch substitution; production exposes no command hook over HTTP."""
    p=tmp_path/'fixture_worker.py'
    p.write_text('''import json,os,signal,subprocess,sys,time
from pathlib import Path
from peanalyzer.cli import sigterm_cleanup
fd=int(sys.argv[-1]);events=os.fdopen(fd,'w',buffering=1)
envelope=json.load(sys.stdin);spec=envelope['spec'];out=Path(spec['output'])
def emit(**value):events.write(json.dumps(value)+'\\n')
def action():
    with sigterm_cleanup():
        return fixture()
def fixture():
    emit(status='WORKER_READY')
    emit(status='RUNNING',stage_id='demux',stage_kind='demux')
    behavior='''+repr(behavior)+'''
    if behavior=='failure':
        emit(status='WORKER_ERROR',code='FIXTURE_BACKEND_ERROR',stage_id='demux',message='Specific backend failure')
        sys.exit(1)
    if behavior=='false_success':
        emit(status='VERIFIED_SUCCESS')
        sys.exit(0)
    if behavior=='unverified':sys.exit(0)
    child=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(100)'])
    (out.parent/'child-pid').write_text(str(child.pid))
    while True:time.sleep(.02)
from peanalyzer.gui.supervision import supervise
def execute():
    try:return action() or 0
    except SystemExit as exc:return int(exc.code or 0)
raise SystemExit(supervise(execute,lambda event:emit(**event),int(os.environ['PEANALYZER_SUPERVISOR_PARENT']),int(os.environ['PEANALYZER_SUPERVISOR_PARENT_START']),grace=.15))
''')
    monkeypatch.setattr('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(p),'--events-fd',str(fd)])
    return p


def test_cancel_process_tree_escalation_events_and_new_job(case,monkeypatch,tmp_path):
    app,c,*_=case;fixture_worker(monkeypatch,tmp_path);app.state.jobs.grace_seconds=.15
    _,j=submit(case);key=j['job_id'];out=case[-1]
    wait_for(c,key,lambda j:j['current_stage_id']=='demux')
    for _ in range(100):
        if (out/'child-pid').exists():break
        time.sleep(.02)
    pid=int((out/'child-pid').read_text());os.kill(pid,0)
    c.post('/api/v1/jobs/'+key+'/cancel')
    assert c.get('/api/v1/jobs').json()[0]['state']=='CANCELLING'
    final=wait_for(c,key);assert final['state']=='CANCELLED' and not app.state.store.opened
    with pytest.raises(ProcessLookupError):os.kill(pid,0)
    first=c.get('/api/v1/jobs/'+key+'/events?after=0&limit=2').json()
    rest=c.get('/api/v1/jobs/'+key+'/events?after=2').json()
    events=first['items']+rest['items'];assert [e['sequence'] for e in events]==list(range(1,len(events)+1))
    assert len([e for e in events if e['status']=='CANCEL_REQUESTED'])==1
    assert next(s for s in final['stages'] if s['stage_id']=='demux')['status']=='CANCELLED'
    fixture_worker(monkeypatch,tmp_path,'failure')
    r=reviewed(c,case[2].model_copy(update={'workspace_name':'next'}))
    response=c.post('/api/v1/jobs',json=r);assert response.status_code==200
    assert wait_for(c,response.json()['job_id'])['error']['code']=='FIXTURE_BACKEND_ERROR'


@pytest.mark.parametrize('behavior,code',[('failure','FIXTURE_BACKEND_ERROR'),('false_success','WORKSPACE_NOT_FOUND'),('unverified','WORKER_EXITED')])
def test_worker_failure_and_false_completion_are_not_published(case,monkeypatch,tmp_path,behavior,code):
    fixture_worker(monkeypatch,tmp_path,behavior)
    _,j=submit(case);final=wait_for(case[1],j['job_id'])
    assert final['state']=='FAILED' and final['error']['code']==code
    assert not final['workspace_id'] and not case[0].state.store.catalog()
    if behavior=='failure':assert final['error']['stage_id']=='demux' and 'Specific backend failure' in final['error']['detail']


@pytest.mark.parametrize('boundary',['token','origin','host'])
@pytest.mark.parametrize('route',['/api/v1/jobs','/api/v1/jobs/unknown','/api/v1/jobs/unknown/events','/api/v1/jobs/unknown/cancel'])
def test_job_endpoints_preserve_local_security(case,boundary,route):
    headers={'X-Viewer-Token':'wrong'} if boundary=='token' else {'Origin':'https://foreign.test'} if boundary=='origin' else {'Host':'foreign.test'}
    method='POST' if route.endswith('cancel') else 'GET'
    response=case[1].request(method,route,headers=headers)
    assert response.status_code==(401 if boundary=='token' else 403)


def test_job_not_found_cannot_control_arbitrary_process(case):
    for key in [str(os.getpid()),'../outside','unknown']:
        assert case[1].post('/api/v1/jobs/'+key+'/cancel').status_code in (404,405,409)


def test_completion_cancel_race_rejects_publication_if_cancel_wins(case,held,monkeypatch,tmp_path):
    fixture_worker(monkeypatch,tmp_path,'false_success')
    _,j=submit(case)
    case[1].post('/api/v1/jobs/'+j['job_id']+'/cancel');held.set()
    assert wait_for(case[1],j['job_id'])['state']=='CANCELLED'
    assert not case[0].state.store.opened


def test_spec_compiler_and_materialization_identity(case,held):
    app,c,content,_,out=case;_,j=submit(case)
    spec=ExecutionSpec.model_validate_json(app.state.jobs.jobs[j['job_id']].payload)
    refs=revalidate_execution(spec);options=materialize(spec,refs)
    for role in ('samples','targets','config','barcodes'):
        assert options[role].read_bytes()==spec.compiled['files'][options[role].name].encode()
    assert spec.compiled['science']['catalog_sha256']==next(f['value'] for f in j['input_metadata'] if f['name']=='barcodes.csv')
    c.post('/api/v1/jobs/'+j['job_id']+'/cancel');held.set();wait_for(c,j['job_id'])


def test_setup_remains_zero_execution_with_run_enabled(case):
    from m11a1_guards import zero_execution
    app,c,content,options,out=case
    before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in out.parent.rglob('*') if p.is_file()}
    with zero_execution() as attempts:
        request=reviewed(c,content)
        assert c.get('/api/v1/setup/capabilities').json()['run_available'] is True
        assert c.get('/api/v1/jobs').json()==[]
    assert attempts==[] and not app.state.jobs.jobs
    assert before=={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in out.parent.rglob('*') if p.is_file()}


def workflow_fixture_worker(case,monkeypatch,tmp_path,behavior):
    from peanalyzer.gui.execution import RuntimeSettings
    executable=tmp_path/'qualified-version-fixture'
    executable.write_text('#!/bin/sh\nprintf "CRISPResso 2.3.4\\n"\n');executable.chmod(0o755)
    case[0].state.jobs.runtime=RuntimeSettings(crispresso=str(executable))
    script=tmp_path/'workflow_fixture_worker.py'
    script.write_text('''import os,subprocess,sys,time
from pathlib import Path
from peanalyzer import workflow as w
from peanalyzer.gui import worker
original=w.execute_stage
behavior='''+repr(behavior)+'''
def execute(plan,node,completed,argv):
    if node.stage_kind=='demux':
        if behavior=='mutate':
            result=original(plan,node,completed,argv)
            p=Path(plan.inputs['r1'].source_path);p.write_bytes(p.read_bytes()+b'changed')
            return result
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(100)'])
        temporary=Path(plan.output).parent/'early-child-pid.tmp'
        temporary.write_text(str(child.pid))
        os.replace(temporary,Path(plan.output).parent/'early-child-pid')
        while True:time.sleep(.02)
    return original(plan,node,completed,argv)
w.execute_stage=execute
raise SystemExit(worker.main())
''')
    monkeypatch.setattr('peanalyzer.gui.jobs.worker_command',lambda fd:[sys.executable,str(script),'--events-fd',str(fd)])


def test_actual_workflow_early_cancel_releases_canonical_lock(case,monkeypatch,tmp_path):
    workflow_fixture_worker(case,monkeypatch,tmp_path,'cancel')
    app,c,_,_,out=case;_,job=submit(case);key=job['job_id']
    wait_for(c,key,lambda j:j['current_stage_id']=='demux')
    for _ in range(100):
        if (out/'early-child-pid').exists():break
        time.sleep(.02)
    pid=int((out/'early-child-pid').read_text());assert (out/'.analysis.m7-lock').exists()
    c.post('/api/v1/jobs/'+key+'/cancel');final=wait_for(c,key)
    assert final['state']=='CANCELLED' and not final['workspace_id']
    assert not (out/'.analysis.m7-lock').exists() and not (out/'analysis/workflow_manifest.json').exists()
    assert (out/'analysis/workflow/sessions').is_dir()
    assert list((out/'analysis/workflow/failures').glob('*.json'))
    with pytest.raises(ProcessLookupError):os.kill(pid,0)


def test_workflow_input_change_during_execution_preserves_backend_error(case,monkeypatch,tmp_path):
    workflow_fixture_worker(case,monkeypatch,tmp_path,'mutate')
    _,job=submit(case);final=wait_for(case[1],job['job_id'])
    assert final['state']=='FAILED' and final['error']['code']=='SOURCE_CHANGED'
    assert final['error']['stage_id']=='demux'
    assert not (case[-1]/'analysis/workflow_manifest.json').exists()
    assert not (case[-1]/'.analysis.m7-lock').exists()


def test_final_viewer_verification_failure_and_cancel_race(case,monkeypatch,tmp_path):
    fixture_worker(monkeypatch,tmp_path,'false_success')
    entered=threading.Event();release=threading.Event()
    def verify(label,path):
        entered.set();release.wait(5)
        raise ViewerError('WORKSPACE_CHANGED','Mutation before final viewer publication')
    monkeypatch.setattr(case[0].state.store,'register_completed',verify)
    _,job=submit(case);assert entered.wait(5)
    # Publication has started; cancellation is idempotent and cannot relabel an
    # already exited process. The actual verification error wins deterministically.
    response=case[1].post('/api/v1/jobs/'+job['job_id']+'/cancel').json()
    assert response['cancellable'] is False and response['state']!='CANCELLING'
    release.set();final=wait_for(case[1],job['job_id'])
    assert final['state']=='FAILED' and final['error']['code']=='WORKSPACE_CHANGED'
    assert not final['workspace_id']


@pytest.mark.parametrize('mutation',['samples','targets','config','barcodes','science'])
def test_private_execution_spec_recompilation_detects_metadata_drift(case,held,mutation):
    app,c,*_=case;_,j=submit(case)
    payload=json.loads(app.state.jobs.jobs[j['job_id']].payload)
    if mutation=='science':payload['compiled']['science']['statistics']='stats'
    else:
        name={'samples':'samples.csv','targets':'targets.csv','config':'config.json','barcodes':'barcodes.csv'}[mutation]
        payload['compiled']['files'][name]+='changed'
    with pytest.raises(WorkflowError,match='SCIENTIFIC_IDENTITY_CHANGED'):
        revalidate_execution(ExecutionSpec.model_validate(payload))
    c.post('/api/v1/jobs/'+j['job_id']+'/cancel');held.set();wait_for(c,j['job_id'])


@pytest.mark.parametrize('phase',['before_submit','after_acceptance'])
def test_external_archive_change_fails_closed(case,held,phase):
    from peanalyzer.demux import demultiplex
    from peanalyzer.validation import load_config
    from peanalyzer.gui.drafts import SetupReferences
    app,c,content,options,out=case;archive=out.parent/'archive'
    demultiplex(r1=options['r1'],r2=options['r2'],samples_path=options['samples'],config=load_config(options['config']),output=archive)
    extra=SetupReferences(archives=[archive]);refs=app.state.drafts.references
    refs.paths.update(extra.paths);refs.entries.update(extra.entries)
    content.input_mode='analyze';content.r1=content.r2=None;content.demux=next(iter(extra.entries))
    request=reviewed(c,content)
    if phase=='after_acceptance':response=c.post('/api/v1/jobs',json=request);assert response.status_code==200
    (archive/'unexpected-file').write_text('changed archive inventory')
    if phase=='before_submit':assert c.post('/api/v1/jobs',json=request).status_code==409
    else:
        held.set();job=wait_for(c,response.json()['job_id'])
        assert job['state']=='FAILED' and job['error']['code']=='INPUT_CHANGED'
    assert list(out.iterdir())==[]
