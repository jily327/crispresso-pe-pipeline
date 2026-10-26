"""Recovery preflight is non-destructive and uses the existing M7 authority."""
import json
from pathlib import Path
import shutil
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from test_m7 import case,complete,plan,stage_path
from peanalyzer import workflow as w
from peanalyzer.workflow_recovery import preflight_resume,workspace_identity
from peanalyzer.gui.recovery import inspect
from peanalyzer.gui.execution import RuntimeSettings
from peanalyzer.gui.app import create_app


def partial(case):
    options,counts=complete(case);root=options['output']
    (root/'workflow_manifest.json').unlink()
    stage_path(options,'report').unlink();shutil.rmtree(root/'report')
    return options,counts


def client_for(options):
    app=create_app(token='test',runtime=RuntimeSettings(crispresso=options['crispresso']),recovery_workspaces=[options['output']])
    c=TestClient(app,base_url='http://127.0.0.1',headers={'X-Viewer-Token':'test'})
    return app,c


def open_preview(c):
    key=c.get('/api/v1/recovery/workspaces').json()[0]['registration_id']
    r=c.post('/api/v1/recovery',json={'registration_id':key});assert r.status_code==200,r.text
    return r.json()


@pytest.mark.parametrize('mutation',['upstream_output','metadata','snapshot','dependency'])
def test_partial_force_preflight_failure_deletes_nothing(case,mutation):
    options,_=partial(case);root=options['output']
    if mutation=='upstream_output':
        path=root/'analysis/03_analysis_fastq/bc001_R1.analysis.fastq.gz';path.write_bytes(path.read_bytes()+b'bad')
    elif mutation=='metadata':
        p=options['samples'];p.write_text(p.read_text().replace('synthetic-editor','changed-editor'))
    elif mutation=='snapshot':
        p=root/plan(options).inputs['samples'].snapshot;p.write_bytes(p.read_bytes()+b'bad')
    else:
        p=stage_path(options,'analysis');d=json.loads(p.read_text());d['stage_signature_sha256']='0'*64;p.write_text(json.dumps(d))
    before=workspace_identity(root)
    with pytest.raises(w.WorkflowError):w.resume_workflow(**options,force=['routing'])
    assert workspace_identity(root)==before
    assert not root.with_name('.workflow.m7-lock').exists()


def test_recovery_preview_is_read_only_no_probe_or_executor(case,monkeypatch):
    options,_=partial(case);root=options['output'];before=workspace_identity(root)
    for name in ('resolve_executable','build_workflow_plan','execute_workflow','resume_workflow','_invalidate','execute_stage'):
        monkeypatch.setattr(w,name,lambda *a,**k:pytest.fail('inspection executed/probed/mutated'))
    app,c=client_for(options)
    v=open_preview(c)
    assert v['classification']=='RESUMABLE' and v['executable']
    assert [s['action'] for s in v['stages']].count('REUSE')==9
    assert [s['stage_id'] for s in v['stages'] if s['action']=='RUN']==['report']
    assert workspace_identity(root)==before and app.state.jobs.jobs=={}


@pytest.mark.parametrize('family',w.FORCE_FAMILIES)
def test_force_preview_exact_backend_closure(case,family):
    options,_=partial(case);p=plan(options);before=workspace_identity(options['output'])
    _,pf,state=inspect(options['output'],RuntimeSettings(crispresso=options['crispresso']),[family])
    assert state=='RESUMABLE_WITH_FORCE'
    assert set(pf['closure'])==w.force_closure(p,[family])
    assert all(s['reason_codes'] for s in pf['stages'] if s['action']=='RERUN')
    assert workspace_identity(options['output'])==before


def test_completed_is_open_results_not_recovery(case):
    options,_=complete(case);app,c=client_for(options);v=open_preview(c)
    assert v['classification']=='COMPLETED' and not v['executable'] and not v['force_families']
    assert c.post(f"/api/v1/recovery/{v['recovery_id']}/open",json={}).status_code==200
    assert not app.state.jobs.jobs


@pytest.mark.parametrize('mutation',['raw','metadata','output','stage','snapshot','symlink','software'])
def test_stale_recovery_confirmation_has_zero_destructive_effect(case,monkeypatch,mutation):
    options,_=partial(case);root=options['output'];app,c=client_for(options);v=open_preview(c)
    if mutation=='raw':options['r1'].write_bytes(options['r1'].read_bytes()+b'changed')
    elif mutation=='metadata':options['samples'].write_text(options['samples'].read_text().replace('synthetic-editor','other-editor'))
    elif mutation=='output':(root/'foreign-file').write_text('must survive')
    elif mutation=='stage':stage_path(options,'metrics').write_text('{}')
    elif mutation=='snapshot':(root/plan(options).inputs['config'].snapshot).write_text('{}')
    elif mutation=='symlink':(root/'foreign-link').symlink_to(options['r1'])
    else:
        actual=w.software_identity();monkeypatch.setattr(w,'software_identity',lambda:actual.model_copy(update={'git_commit':'0'*40}))
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
    r=c.post(f"/api/v1/recovery/{v['recovery_id']}/execute",json=dict(revision=v['revision'],recovery_plan_sha256=v['recovery_plan_sha256'],confirmed=True))
    assert r.status_code==409 and r.json()['error']['code']=='RECOVERY_PLAN_CHANGED'
    assert not app.state.jobs.jobs
    assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def test_software_change_requires_explicit_full_rebuild(case,monkeypatch):
    options,_=partial(case);old=w.software_identity();new=old.model_copy(update={'git_commit':'0'*40})
    monkeypatch.setattr(w,'software_identity',lambda:new)
    app,c=client_for(options);v=open_preview(c)
    assert v['classification']=='SOFTWARE_CHANGED' and not v['executable']
    r=c.post(f"/api/v1/recovery/{v['recovery_id']}/preview",json=dict(revision=v['revision'],force=['all']))
    assert r.status_code==200,r.text
    assert r.json()['executable'] and r.json()['classification']=='RESUMABLE_WITH_FORCE'


def test_orphan_requires_force_and_wrong_force_does_not_authorize(case):
    options,_=partial(case);root=options['output'];(root/'report').mkdir();(root/'report/partial').write_text('partial')
    app,c=client_for(options);v=open_preview(c)
    assert v['classification']=='RESUMABLE_WITH_FORCE' and not v['executable']
    r=c.post(f"/api/v1/recovery/{v['recovery_id']}/preview",json=dict(revision=v['revision'],force=['report']))
    assert r.json()['executable'] and 'report' in r.json()['removal_paths']


@pytest.mark.parametrize('extra',['output','pid','signal','executable','command','removal_paths'])
def test_recovery_api_strict_confirmation(case,extra):
    options,_=partial(case);_,c=client_for(options);v=open_preview(c)
    body=dict(revision=v['revision'],recovery_plan_sha256=v['recovery_plan_sha256'],confirmed=True);body[extra]='untrusted'
    assert c.post(f"/api/v1/recovery/{v['recovery_id']}/execute",json=body).status_code==422


@pytest.mark.parametrize('boundary',['token','origin','host'])
def test_recovery_security(case,boundary):
    options,_=partial(case);_,c=client_for(options)
    headers={'X-Viewer-Token':'wrong'} if boundary=='token' else {'Origin':'https://foreign'} if boundary=='origin' else {'Host':'foreign'}
    assert c.get('/api/v1/recovery/workspaces',headers=headers).status_code==(401 if boundary=='token' else 403)
    assert c.post('/api/v1/recovery',json={'registration_id':'unknown'},headers=headers).status_code==(401 if boundary=='token' else 403)


def test_invocation_lock_is_never_stolen(case):
    options,_=partial(case);root=options['output'];lock=root.with_name('.workflow.m7-lock');lock.write_text('foreign')
    _,c=client_for(options);v=open_preview(c)
    assert v['classification']=='ACTIVE' and not v['executable'] and lock.read_text()=='foreign'


def test_backend_digest_is_same_qualified_identity_as_review():
    with pytest.raises(ValueError,match='qualified identity'):RuntimeSettings(runtime_digest='unqualified')


@pytest.mark.parametrize('value',[False,1,'true',None])
def test_recovery_requires_actual_explicit_boolean(value):
    from peanalyzer.gui.recovery_models import RecoveryRequest
    with pytest.raises(ValueError):RecoveryRequest(revision=1,recovery_plan_sha256='a'*64,confirmed=value)


def test_cross_server_host_lease_blocks_recovery(case):
    import os
    from peanalyzer.gui.process_safety import acquire_lease
    options,_=partial(case);app,c=client_for(options);v=open_preview(c)
    fd=acquire_lease()
    try:
        r=c.post(f"/api/v1/recovery/{v['recovery_id']}/execute",json=dict(revision=v['revision'],recovery_plan_sha256=v['recovery_plan_sha256'],confirmed=True))
        assert r.status_code==409 and r.json()['error']['code']=='WORKER_BUSY'
        assert not app.state.jobs.jobs
    finally:os.close(fd)


def test_recovery_registration_labels_reuse_viewer_disambiguation(tmp_path):
    app=create_app(token='test',recovery_workspaces=[tmp_path/'first/results',tmp_path/'second/results'])
    labels=[r.label for r in app.state.recovery.catalog()]
    assert labels==['first / results','second / results']


def test_external_demux_extra_inventory_rejected_even_in_force_preview(case):
    options,_=complete(case);external=options['output']/'demux'
    analyze={k:v for k,v in options.items() if k not in ('r1','r2')}
    analyze.update(mode='analyze',demux_root=external,output=options['output'].with_name('analyze'))
    w.execute_workflow(**analyze)
    (analyze['output']/'workflow_manifest.json').unlink()
    # An added unrecorded source file must be seen by the authoritative demux
    # verifier even though every formerly recorded input SHA-256 still matches.
    original=next((external/'02_demultiplexed_fastq').glob('*.gz'))
    (original.parent/'unexpected_R1.fastq.gz').write_bytes(original.read_bytes())
    before=workspace_identity(analyze['output'])
    with pytest.raises(ValueError):inspect(analyze['output'],RuntimeSettings(crispresso=options['crispresso']),['all'])
    assert workspace_identity(analyze['output'])==before
