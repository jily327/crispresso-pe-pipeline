"""Workspace-only tampering cannot manufacture destructive ownership authority."""
import json
import shutil
from pathlib import Path
import pytest
from test_m7 import case, complete, plan, stage_path
from test_m11c_recovery import client_for, open_preview
from test_m11c1_recovery import snapshot, force
from peanalyzer import workflow as w
from peanalyzer.workflow_integrity import RECEIPT


def interrupted(case,monkeypatch,kind='metrics'):
    options,counts=case;original=w.execute_stage
    def stop(plan,node,*args):
        if node.stage_kind==kind:raise RuntimeError('Deliberate pre-stage interruption')
        return original(plan,node,*args)
    monkeypatch.setattr(w,'execute_stage',stop)
    with pytest.raises(w.WorkflowError,match='Deliberate'):w.execute_workflow(**options)
    monkeypatch.setattr(w,'execute_stage',original);counts.clear()
    return options,counts


def refused(options,monkeypatch,code,family='all'):
    before=snapshot(options['output'])
    for name in ('_invalidate','execute_stage'):
        monkeypatch.setattr(w,name,lambda *a,**k:pytest.fail('Destructive or scientific work began'))
    _,c=client_for(options);view=open_preview(c)
    for selected in (None,family):
        if selected:view=force(c,view,selected)
        assert not view['executable'] and view['classification'] in {'TAMPERED','UNSUPPORTED'},view
        expected='CORRUPTED_STAGE_OUTPUT' if selected is None and code=='FOREIGN_CONTENT_PRESENT' else code
        assert view['reasons'][0]['code']==expected,view
    with pytest.raises(w.WorkflowError,match=code):w.resume_workflow(**options,force=[family])
    assert snapshot(options['output'])==before


@pytest.mark.parametrize('mutation',['reasons','add','remove','path','hash','status','parameters'])
def test_unanchored_frontier_tamper_matrix(case,monkeypatch,mutation):
    options,_=interrupted(case,monkeypatch)
    frontier=[n for n in plan(options).nodes if (options['output']/w.stage_manifest_path(n)).exists()][-1]
    p=options['output']/w.stage_manifest_path(frontier);v=json.loads(p.read_text())
    assert not any((options['output']/w.stage_manifest_path(n)).exists() for n in plan(options).nodes if n.stage_kind=='metrics')
    if mutation=='reasons':v['reason_codes'].append('FORGED_REASON')
    elif mutation=='add':
        victim=options['output']/frontier.output_path/'VICTIM.txt';victim.write_bytes(b'foreign user data\n')
        v['output_artifacts'].append(w.artifact(options['output'],victim).model_dump());v['output_artifacts'].sort(key=lambda a:a['path'])
    elif mutation=='remove':v['output_artifacts'].pop()
    elif mutation=='path':v['output_artifacts'][0]['path']=frontier.output_path+'/VICTIM.txt'
    elif mutation=='hash':v['output_artifacts'][0]['sha256']='0'*64
    elif mutation=='status':v['status']='SKIPPED_SCIENTIFIC_GATE';v['reason_codes']=['FORGED_GATE']
    else:v['normalized_parameters']['forged']='future'
    p.write_text(json.dumps(v))
    refused(options,monkeypatch,'TAMPERED_STAGE_MANIFEST','routing')
    if mutation=='add':assert victim.read_bytes()==b'foreign user data\n'


@pytest.mark.parametrize('mutation',['inventory','stage_hash','final_hash','plan','status'])
def test_completion_marker_claims_are_authenticated(case,monkeypatch,mutation):
    options,_=complete(case);p=options['output']/'workflow_manifest.json';v=json.loads(p.read_text())
    if mutation=='inventory':v['stage_inventory'].pop('report')
    elif mutation=='stage_hash':v['stage_inventory']['report']['sha256']='0'*64
    elif mutation=='final_hash':v['report_manifest']['sha256']='0'*64
    elif mutation=='plan':v['plan']['sha256']='0'*64
    else:v['status']='FAILED'
    p.write_text(json.dumps(v));refused(options,monkeypatch,'TAMPERED_COMPLETION_MARKER')


def test_future_plan_edit_and_matching_mutable_history_do_not_authenticate(case,monkeypatch):
    options,_=interrupted(case,monkeypatch);p=options['output']/'workflow/plan.json';v=json.loads(p.read_text())
    v['normalized_options']['title']='Forged future report title'
    p.write_text(json.dumps(v))
    # Agreement with another workspace JSON file does not grant trust.
    (p.parent/'plans'/f'{w.digest(v)}.json').write_text(json.dumps(v))
    refused(options,monkeypatch,'TAMPERED_WORKFLOW_PLAN')


@pytest.mark.parametrize('mutation',['missing','forged','missing_key','copied'])
def test_no_retroactive_or_circular_recovery_authentication(case,monkeypatch,tmp_path,mutation):
    options,_=interrupted(case,monkeypatch);p=options['output']/RECEIPT
    code='TAMPERED_RECOVERY_INTEGRITY'
    if mutation=='missing':p.unlink();code='UNANCHORED_RECOVERY_OWNERSHIP'
    elif mutation=='missing_key':
        monkeypatch.setattr('peanalyzer.workflow_integrity.key_path',lambda:tmp_path/'unavailable/key')
        code='UNANCHORED_RECOVERY_OWNERSHIP'
    else:
        v=json.loads(p.read_text())
        if mutation=='forged':v['payload']['records']['workflow/plan.json']='0'*64
        else:v['payload']['workspace']['inode']+=1
        p.write_text(json.dumps(v))
    refused(options,monkeypatch,code)


def test_intact_interruption_resumes_and_backend_drift_is_stale_not_tampered(case,monkeypatch):
    options,_=interrupted(case,monkeypatch);_,c=client_for(options)
    v=open_preview(c);assert v['executable'] and v['classification']=='RESUMABLE'
    core=Path(options['crispresso']);core.write_text(core.read_text()+'# changed qualified backend bytes\n')
    v=open_preview(c);assert v['executable']  # No metrics has run yet.
    w.resume_workflow(**options);w.verify_workflow_output(options['output'])


def test_legacy_completed_result_still_verifies_but_force_refuses(case,monkeypatch):
    options,_=complete(case);(options['output']/RECEIPT).unlink()
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'
    _,c=client_for(options);assert open_preview(c)['classification']=='COMPLETED'
    before=snapshot(options['output'])
    with pytest.raises(w.WorkflowError,match='UNANCHORED_RECOVERY_OWNERSHIP'):w.resume_workflow(**options,force=['all'])
    assert before==snapshot(options['output'])


def test_frontier_foreign_filename_lookalike_is_not_owned(case,monkeypatch):
    options,_=interrupted(case,monkeypatch)
    (options['output']/'routing/bc001/T1/copy3_R1.fastq.gz').write_bytes(b'keep')
    refused(options,monkeypatch,'FOREIGN_CONTENT_PRESENT','routing')


def test_legitimate_backend_drift_requires_metrics_force(case,monkeypatch):
    options,_=interrupted(case,monkeypatch,'report');core=Path(options['crispresso'])
    core.write_text(core.read_text()+'# new backend bytes\n');_,c=client_for(options)
    v=open_preview(c)
    assert v['classification']=='RESUMABLE_WITH_FORCE' and not v['executable']
    assert v['reasons'][0]['code']=='STALE_STAGE_IDENTITY'
    v=force(c,v,'metrics');assert v['executable']
    w.resume_workflow(**options,force=['metrics']);w.verify_workflow_output(options['output'])


def test_legitimate_external_input_drift_remains_stale_input(case,monkeypatch):
    options,_=interrupted(case,monkeypatch);p=options['samples'];p.write_text(p.read_text()+'\n')
    _,c=client_for(options);v=open_preview(c)
    assert v['classification']=='STALE_INPUT' and not v['executable']
    assert v['reasons'][0]['code']=='SOURCE_CHANGED'


def test_forged_ownership_and_matching_receipt_hash_still_fail_authentication(case,monkeypatch):
    options,_=interrupted(case,monkeypatch);root=options['output'];p=stage_path(options,'routing')
    victim=root/'routing/bc001/T1/VICTIM.txt';victim.write_text('do not delete')
    v=json.loads(p.read_text());v['output_artifacts'].append(w.artifact(root,victim).model_dump())
    v['output_artifacts'].sort(key=lambda a:a['path']);p.write_text(json.dumps(v))
    receipt=root/RECEIPT;v=json.loads(receipt.read_text());v['payload']['records'][str(p.relative_to(root))]=w.sha(p)
    receipt.write_text(json.dumps(v));refused(options,monkeypatch,'TAMPERED_RECOVERY_INTEGRITY','routing')
    assert victim.read_text()=='do not delete'


def test_authenticated_receipt_rejects_actual_root_replacement(case,monkeypatch):
    options,_=interrupted(case,monkeypatch);root=options['output']
    original=root.with_name('original-workspace');root.rename(original)
    shutil.copytree(original,root)
    assert root.stat().st_ino!=original.stat().st_ino
    # All receipt/metadata bytes agree, but their original directory no longer
    # occupies the accepted path. No synthetic binding is used in this test.
    assert (root/RECEIPT).read_bytes()==(original/RECEIPT).read_bytes()
    refused(options,monkeypatch,'TAMPERED_RECOVERY_INTEGRITY')
