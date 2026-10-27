"""Focused W2, R7 and G6 audit remediation regressions."""
import json
from pathlib import Path
import pytest
from test_m7 import case,complete,plan,stage_path
from test_m11c_recovery import partial,client_for,open_preview
from peanalyzer import workflow as w


def snapshot(root):
    result={}
    for p in [root,*sorted(root.rglob('*'))]:
        s=p.lstat();result[str(p)]=(s.st_ino,s.st_mode,s.st_mtime_ns,s.st_ctime_ns,p.readlink().as_posix() if p.is_symlink() else p.read_bytes() if p.is_file() else None)
    return result


def force(c,v,family):
    r=c.post(f"/api/v1/recovery/{v['recovery_id']}/preview",json=dict(revision=v['revision'],force=[family]));assert r.status_code==200,r.text
    return r.json()


@pytest.mark.parametrize('family',['routing','metrics'])
@pytest.mark.parametrize('entry',['regular','directory','hidden','symlink','nested'])
def test_foreign_removal_entries_refused_without_any_mutation(case,monkeypatch,family,entry):
    options,_=partial(case);root=options['output'];folder=root/family/'bc001/T1'
    name='.hidden-note' if entry=='hidden' else 'FOREIGN-NOTE.txt'
    path=folder/name
    if entry=='directory':path.mkdir()
    elif entry=='symlink':path.symlink_to(options['r1'])
    elif entry=='nested':path=folder/'foreign/nested/note';path.parent.mkdir(parents=True);path.write_text('keep')
    else:path.write_text('keep')
    before=snapshot(root);raw=options['r1'].read_bytes()
    monkeypatch.setattr(w,'_invalidate',lambda *a:pytest.fail('invalidation entered'))
    _,c=client_for(options);v=force(c,open_preview(c),family)
    assert not v['executable'] and v['classification']=='TAMPERED'
    assert v['reasons'][0]['code'] in {'FOREIGN_CONTENT_PRESENT','UNSAFE_PATH'}
    if entry!='symlink':assert str(path.relative_to(root)) in v['reasons'][0]['detail']
    with pytest.raises(ValueError):w.resume_workflow(**options,force=[family])
    assert snapshot(root)==before and options['r1'].read_bytes()==raw


@pytest.mark.parametrize('family',['routing','metrics'])
def test_foreign_arrival_invalidates_old_force_preview(case,monkeypatch,family):
    options,_=partial(case);_,c=client_for(options);v=force(c,open_preview(c),family);assert v['executable']
    (options['output']/family/'bc001/T1/FOREIGN-NOTE.txt').write_text('keep')
    before=snapshot(options['output']);monkeypatch.setattr(w,'_invalidate',lambda *a:pytest.fail('invalidation entered'))
    r=c.post(f"/api/v1/recovery/{v['recovery_id']}/execute",json=dict(revision=v['revision'],recovery_plan_sha256=v['recovery_plan_sha256'],confirmed=True))
    assert r.status_code==409 and r.json()['error']['code']=='RECOVERY_PLAN_CHANGED'
    assert snapshot(options['output'])==before


@pytest.mark.parametrize('mutation',['signature','dependency','node','status','artifact_hash','artifact_reference'])
def test_internal_manifest_tampering_is_never_force_eligible(case,mutation):
    options,_=partial(case);p=stage_path(options,'analysis');value=json.loads(p.read_text())
    if mutation=='signature':value['stage_signature_sha256']='0'*64
    elif mutation=='dependency':value['dependencies']['demux']['output_identity_sha256']='0'*64
    elif mutation=='node':value['node']['stage_id']='foreign'
    elif mutation=='status':value['status']='SKIPPED_SCIENTIFIC_GATE'
    elif mutation=='artifact_hash':value['output_artifacts'][0]['sha256']='0'*64
    else:value['output_artifacts'][0]['path']='analysis/foreign-result'
    p.write_text(json.dumps(value));before=snapshot(options['output']);_,c=client_for(options)
    v=open_preview(c)
    for family in [None,'analysis','all']:
        if family:v=force(c,v,family)
        assert v['classification']=='TAMPERED' and not v['executable'],v
        assert v['reasons'][0]['code']=='TAMPERED_STAGE_MANIFEST'
    assert snapshot(options['output'])==before


def test_resume_events_distinguish_reuse_from_execution(case):
    options,counts=partial(case);events=[]
    result=w.resume_workflow(**options,observer=events.append)
    for stage in result['reused_stages']:
        assert [e['status'] for e in events if e.get('stage_id')==stage]==['REUSED']
    assert [e['status'] for e in events if e.get('stage_id')=='report']==['RUNNING','COMPLETED']
    assert result['executed_stages']==['report'] and counts=={'generate_report':1}
