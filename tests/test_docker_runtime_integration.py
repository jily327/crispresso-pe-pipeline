"""Genuine CRISPResso in the pinned image through the SHIPPED runtime.

Opt in on an isolated account; these tests use the GUI host lease. No mock
backend, alternate guard, or production fault-injection switch is used.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest
from docker_runtime_helpers import (Docker,IMAGE,LABEL,wrapper,docker_command,until,active_record,
    pause_after_nonempty,assert_stopped,cleanup_owned,core_args,save_evidence,checked_state)

pytestmark=[pytest.mark.integration,pytest.mark.skipif(os.environ.get('PEANALYZER_DOCKER_INTEGRATION')!='1',reason='requires genuine pinned Docker image; PEANALYZER_DOCKER_INTEGRATION=1')]


@pytest.mark.parametrize('termination',['SIGTERM','SIGKILL','docker_cli'])
def test_actual_owner_or_cli_death_stops_backend(tmp_path,termination):
    if termination=='SIGTERM':
        tmp_path=tmp_path/'path with spaces,comma';tmp_path.mkdir()
    args=core_args(tmp_path);record=None
    with (tmp_path/'wrapper.log').open('w') as log:
        process=subprocess.Popen([wrapper(),*args],cwd=tmp_path,stdout=log,stderr=subprocess.STDOUT)
        try:
            record=until(lambda:active_record(owner_pid=process.pid))
            pause_after_nonempty(record)
            if termination=='docker_cli':
                from peanalyzer.gui.process_safety import census
                children=census(process.pid,{})
                assert len(children)==1,children
                os.kill(next(iter(children)),signal.SIGKILL)
            else:process.send_signal(getattr(signal,termination))
            state=assert_stopped(record)
            assert process.wait(timeout=30)!=0
            proof=json.loads((Path(record['control'])/'finished.json').read_text())
            assert proof['reason']=='OWNER_LOST' and proof['backend_returncode']<0
            save_evidence('owner-'+termination,dict(state=state,guard=proof,nonempty=True,image=IMAGE,observed_image_id=record['image_id']))
        finally:
            if process.poll() is None:process.kill();process.wait()
            if record:cleanup_owned(record)


def test_supervisor_death_stops_backend_with_wrapper_still_alive(tmp_path):
    args=core_args(tmp_path);identity=tmp_path/'guardian.json'
    script=tmp_path/'guardian.py'
    script.write_text('''import os,sys,subprocess,json
from pathlib import Path
from peanalyzer.docker_runtime import SESSION_ENV
from peanalyzer.gui.supervision import supervise
from peanalyzer.gui.process_safety import process_identity
parent=os.getppid()
def action():
    process=subprocess.Popen(sys.argv[2:])
    Path(sys.argv[1]).write_text(json.dumps({'pid':process.pid,'session':os.environ[SESSION_ENV]}))
    return process.wait()
sys.exit(supervise(action,lambda event:None,parent,process_identity(parent)['start_ticks']))
''')
    record=None
    with (tmp_path/'wrapper.log').open('w') as log:
        guardian=subprocess.Popen([sys.executable,str(script),str(identity),wrapper(),*args],cwd=tmp_path,stdout=log,stderr=subprocess.STDOUT)
        try:
            until(identity.exists);owner=json.loads(identity.read_text())['pid']
            record=until(lambda:active_record(owner_pid=owner));pause_after_nonempty(record)
            guardian.kill();guardian.wait()
            state=assert_stopped(record)
            proof=json.loads((Path(record['control'])/'finished.json').read_text())
            assert proof['reason']=='OWNER_LOST'
            save_evidence('supervisor-death',dict(state=state,guard=proof,image=IMAGE,observed_image_id=record['image_id']))
        finally:
            if guardian.poll() is None:guardian.kill();guardian.wait()
            if record:cleanup_owned(record)


def test_genuine_gui_failure_repeated_cancel_and_verified_recovery(tmp_path,monkeypatch):
    import m11b_helpers
    from m11b_helpers import application,reviewed,wait_for
    from peanalyzer.gui.execution import RuntimeSettings
    from peanalyzer.workflow import verify_workflow_output
    original=m11b_helpers.fixture
    monkeypatch.setattr(m11b_helpers,'fixture',lambda root,**kw:original(root,**{**kw,'reads':200}))
    app,client,content,_,out=application(tmp_path/'gui',runtime=RuntimeSettings(crispresso=wrapper()))
    records=[];preserved=[];observations=[]
    try:
        response=client.post('/api/v1/jobs',json=reviewed(client,content));assert response.status_code==200,response.text
        key=response.json()['job_id']
        for behavior in ('failure','cancel','cancel'):
            job=app.state.jobs.jobs[key]
            until(lambda:job.process is not None)
            def active():
                state=client.get('/api/v1/jobs/'+key).json()
                assert state['state'] not in ('FAILED','CANCELLED','COMPLETED'),state
                return active_record(ancestor=job.process.pid)
            record=until(active,timeout=180);records.append(record)
            started=pause_after_nonempty(record)
            if behavior=='failure':
                result=docker_command('exec',record['id'],'python','-c','import os,signal,sys;os.kill(int(sys.argv[1]),signal.SIGKILL)',str(started['pid']),capture_output=True)
                assert result.returncode==0
            else:assert client.post('/api/v1/jobs/'+key+'/cancel',json={}).status_code==200
            terminal=wait_for(client,key,timeout=300)
            assert terminal['state']==('FAILED' if behavior=='failure' else 'CANCELLED'),terminal
            # The terminal GUI state itself must already be backed by daemon
            # confirmation, not by a subsequent cleanup initiated by this test.
            state=checked_state(Docker(),record)
            assert state['running'] is False and state['pid']==0,state
            observations.append(dict(behavior=behavior,gui_state=terminal['state'],daemon_state=state,observed_image_id=record['image_id']))
            assert not (out/'analysis/workflow_manifest.json').exists()
            assert not (out/'analysis/metrics/bc001/T1').exists()
            attempts=list(out.glob('.analysis.metrics-attempt-*/output'))
            assert attempts and any(p.stat().st_size for attempt in attempts for p in attempt.rglob('CRISPResso_RUNNING_LOG.txt'))
            foreign=attempts[-1]/'foreign-user-file.txt';foreign.write_text('preserve');preserved.append(foreign)
            view=client.post('/api/v1/jobs/'+key+'/recovery',json={}).json()
            assert view['classification']=='RESUMABLE' and view['executable'],view
            response=client.post(f"/api/v1/recovery/{view['recovery_id']}/execute",json=dict(revision=view['revision'],recovery_plan_sha256=view['recovery_plan_sha256'],confirmed=True))
            assert response.status_code==200,response.text
            key=response.json()['job_id']
        terminal=wait_for(client,key,timeout=420)
        assert terminal['state']=='COMPLETED',terminal
        assert verify_workflow_output(out/'analysis').status=='COMPLETED'
        metric=json.loads((out/'analysis/metrics/bc001/T1/result.json').read_text())['target_metrics']['total_precise_pe']
        assert (metric['numerator'],metric['denominator'])==(2,400)
        assert all(p.read_text()=='preserve' for p in preserved)
        save_evidence('gui-recovery',dict(attempts=observations,exact_counts=[2,400],verified=True,foreign_files_preserved=len(preserved)))
    finally:
        app.state.jobs.close()
        for record in records:cleanup_owned(record)


def test_cancel_at_backend_completion(tmp_path):
    record=None
    with (tmp_path/'wrapper.log').open('w') as log:
        process=subprocess.Popen([wrapper(),*core_args(tmp_path,reads=1000)],cwd=tmp_path,stdout=log,stderr=subprocess.STDOUT)
        try:
            record=until(lambda:active_record(owner_pid=process.pid))
            control=Path(record['control']);until(lambda:(control/'finished.json').exists())
            if process.poll() is None:process.terminate()
            process.wait(timeout=30)
            state=assert_stopped(record)
            proof=json.loads((control/'finished.json').read_text())
            assert proof['backend_returncode']==0
            assert list(tmp_path.glob('output/**/CRISPResso2_info.json'))
            save_evidence('completion-race',dict(state=state,guard=proof,wrapper_returncode=process.returncode))
        finally:
            if process.poll() is None:process.kill();process.wait()
            if record:cleanup_owned(record)


@pytest.fixture(scope='module')
def previous_candidate(tmp_path_factory):
    """Read-only Git export: independently run the exact prior PR candidate."""
    import io,tarfile
    root=tmp_path_factory.mktemp('candidate-59e6755')
    repository=Path(__file__).parents[1]
    archive=subprocess.check_output(['git','-C',str(repository),'archive','59e6755aa2cc1dbe67b6decd88865d9616a3c7e4','src'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(root,filter='data')
    return root/'src'


@pytest.mark.parametrize('mode',['precise_edit','indel_nuclease'])
def test_success_scientific_parity_and_unrelated_container_isolation(tmp_path,previous_candidate,mode):
    import hashlib,shlex,tempfile,uuid
    from peanalyzer import workflow as w
    from peanalyzer.gui.app import create_app
    from peanalyzer.gui.workspace import WorkspaceStore
    from fastapi.testclient import TestClient
    if mode=='precise_edit':from m7_fixtures import fixture
    else:from m8_fixtures import fixture
    options=fixture(tmp_path/'inputs')
    options['contrasts']=tmp_path/'inputs/contrasts.yaml'
    docker=Docker();owned=[]
    def sentinel():
        name='peanalyzer-test-unrelated-'+uuid.uuid4().hex
        _,value=docker.request('POST','/containers/create?name='+name,dict(Image=IMAGE,User=f'{os.getuid()}:{os.getgid()}',
            Entrypoint=['/bin/sleep'],Cmd=['infinity'],HostConfig=dict(NetworkMode='none',Mounts=[dict(Type='bind',Source=tempfile.gettempdir(),Target=tempfile.gettempdir())])),timeout=60)
        owned.append(value['Id']);docker.request('POST','/containers/'+value['Id']+'/start');return value['Id']
    old=sentinel();unrelated=sentinel()
    before=docker.inspect(unrelated)['State']
    legacy=tmp_path/'legacy-CRISPResso'
    legacy.write_text('#!/bin/sh\nexec env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host='+shlex.quote('unix://'+docker.path)+' exec --user '+shlex.quote(f'{os.getuid()}:{os.getgid()}')+' --workdir "$PWD" '+shlex.quote(old)+' CRISPResso "$@"\n');legacy.chmod(0o755)
    baseline=tmp_path/'baseline';candidate=tmp_path/'candidate'
    try:
        old_options={**options,'output':baseline,'crispresso':str(legacy)}
        plan=tmp_path/'baseline-options.json';plan.write_text(json.dumps(old_options,default=str))
        script='import json,sys;from peanalyzer.workflow import execute_workflow;execute_workflow(**json.load(open(sys.argv[1])))'
        with (tmp_path/'baseline.log').open('w') as log:
            result=subprocess.run([sys.executable,'-c',script,str(plan)],env={**os.environ,'PYTHONPATH':str(previous_candidate)},cwd=tmp_path,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode==0,(tmp_path/'baseline.log').read_text()[-2000:]
        # Cold-start independence: the old persistent backend remains stopped.
        docker.request('POST','/containers/'+old+'/stop?t=2')
        old_state=docker.inspect(old)['State']
        assert old_state['Running'] is False
        w.execute_workflow(**{**options,'output':candidate,'crispresso':wrapper()})
        assert w.verify_workflow_output(candidate).status=='COMPLETED'
        assert docker.inspect(old)['State']==old_state
        assert docker.inspect(unrelated)['State']==before
        def science(value):
            if isinstance(value,list):return [science(v) for v in value]
            if isinstance(value,dict):return {k:science(v) for k,v in value.items() if k not in {'population_id','source_result_sha256','source_result','result_sha256'}}
            return value
        fields=('target_metrics','copies','eligibility','qc','product_evidence','derived_metrics') if mode=='precise_edit' else ('metrics','class_counts','aligned_reads','unaligned_reads','fraction_of_indel_reads_by_net_size','alleles')
        count=0;primary={}
        for path in sorted(candidate.glob('metrics/*/*/result.json')):
            a=json.loads((baseline/path.relative_to(candidate)).read_text());b=json.loads(path.read_text())
            for field in fields:assert science(a[field])==science(b[field]),field;count+=1
            metric=b['target_metrics']['total_precise_pe'] if mode=='precise_edit' else b['metrics']['indel_fraction']
            primary[b['sample_id']]=(metric['numerator'],metric['denominator'])
        expected=[(4,24),(8,24),(16,24),(20,24)] if mode=='precise_edit' else [(2,20),(4,20),(14,20),(16,20)]
        assert list(primary.values())==expected,primary
        a=json.loads((baseline/'statistics/result.json').read_text());b=json.loads((candidate/'statistics/result.json').read_text())
        for field in ('observations','group_summaries','contrasts'):
            assert science(a[field])==science(b[field]),field;count+=1
        fingerprint=lambda root:{str(p.relative_to(root)):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
        historical=fingerprint(baseline)
        assert w.verify_workflow_output(baseline).status=='COMPLETED'
        if mode=='precise_edit':WorkspaceStore([]).register_completed('Synthetic parity',candidate,finalize=True)
        app=create_app([(None,baseline),(None,candidate)],token='test')
        client=TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
        registrations=client.get('/api/v1/workspaces').json()
        for entry in registrations:
            response=client.post('/api/v1/workspaces/open',json={'registration_id':entry['registration_id']})
            assert response.status_code==200,response.text
            for observation in response.json()['observations']:
                if observation['copy_name'] is None and observation['metric_name']==('total_precise_pe' if mode=='precise_edit' else 'indel_fraction'):
                    assert (int(observation['numerator']),int(observation['denominator']))==primary[observation['sample_id']];count+=1
        assert fingerprint(baseline)==historical
        if mode=='precise_edit':
            from openpyxl import load_workbook
            book=load_workbook(candidate/'PEAnalyzer_Summary.xlsx',read_only=True,data_only=True)
            for row in list(book['Summary'].values)[1:]:
                numerator,denominator=primary[row[1]]
                assert row[5]==f'{numerator} / {denominator}' and abs(row[4]-numerator/denominator)<1e-14;count+=1
            book.close()
        save_evidence('parity-'+mode,dict(passed_checks=count,primary=primary,previous_candidate='59e6755aa2cc1dbe67b6decd88865d9616a3c7e4',historical_bytes_and_mtimes_unchanged=True,unrelated_container_unchanged=True,stopped_legacy_container_unchanged=True,image=IMAGE,observed_image_id=docker.image()))
    finally:
        for identity in owned:docker.request('DELETE','/containers/'+identity+'?force=1',allowed=(204,404))
