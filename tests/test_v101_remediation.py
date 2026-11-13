"""Audit regressions: real nonempty attempts, publication boundaries and key loss."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from test_m7 import case, complete, plan
from test_m11c_recovery import client_for, open_preview
from peanalyzer import workflow as w
from peanalyzer import workflow_integrity as integrity
from peanalyzer import workflow_publication as publication
from peanalyzer.workflow_recovery import workspace_identity


@pytest.mark.parametrize('force',[[],*[ [f] for f in w.FORCE_FAMILIES]])
def test_nonempty_failed_attempt_repeated_resume_and_force(case,monkeypatch,force):
    options,counts=case;good=w.run_metrics
    def fail(**kwargs):
        output=kwargs['output'];output.mkdir(parents=True)
        (output/'execution.json').write_text('{"status":"running"}')
        (output/'input_R1.fastq.gz').write_bytes(b'nonempty partial input')
        (output/'foreign.txt').write_text('user data must survive')
        raise RuntimeError('backend failed after partial writes')
    monkeypatch.setattr(w,'run_metrics',fail)
    for resume in (False,True):
        with pytest.raises(w.WorkflowError,match='backend failed'):
            w.execute_workflow(**options,resume=resume)
        assert not (options['output']/'metrics/bc001/T1').exists()
        assert not (options['output']/'workflow_manifest.json').exists()
    attempts=list(options['output'].parent.glob('.workflow.metrics-attempt-*/output'))
    assert len(attempts)==2
    _,c=client_for(options);view=open_preview(c)
    assert view['classification']=='RESUMABLE' and view['executable']
    monkeypatch.setattr(w,'run_metrics',good)
    result=w.resume_workflow(**options,force=force)
    assert len(result['executed_stages'])==len(set(result['executed_stages']))
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'
    assert all((p/'foreign.txt').read_text()=='user data must survive' for p in attempts)


@pytest.mark.parametrize('boundary',['before_rename','after_rename','before_manifest','after_manifest'])
def test_cancel_publication_boundaries(case,monkeypatch,boundary):
    options,_=case;rename=publication.rename_exclusive;commit=integrity.RecoveryIntegrity.commit_new
    def interrupted_rename(source,destination):
        if boundary=='before_rename':raise KeyboardInterrupt()
        rename(source,destination)
        if boundary=='after_rename':raise KeyboardInterrupt()
    def interrupted_commit(self,relative,value):
        if boundary=='before_manifest':raise KeyboardInterrupt()
        commit(self,relative,value)
        if boundary=='after_manifest':raise KeyboardInterrupt()
    monkeypatch.setattr(publication,'rename_exclusive',interrupted_rename)
    monkeypatch.setattr(integrity.RecoveryIntegrity,'commit_new',interrupted_commit)
    with pytest.raises(KeyboardInterrupt):w.execute_workflow(**options)
    assert not (options['output']/'workflow_manifest.json').exists()
    monkeypatch.setattr(publication,'rename_exclusive',rename)
    monkeypatch.setattr(integrity.RecoveryIntegrity,'commit_new',commit)
    force=['metrics'] if boundary in ('after_rename','before_manifest') else []
    w.resume_workflow(**options,force=force)
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'


def published_interruption(case,monkeypatch):
    options,_=case;original=publication.rename_exclusive
    def stop(source,destination):
        original(source,destination)
        raise KeyboardInterrupt()
    monkeypatch.setattr(publication,'rename_exclusive',stop)
    with pytest.raises(KeyboardInterrupt):w.execute_workflow(**options)
    monkeypatch.setattr(publication,'rename_exclusive',original)
    return options


def test_foreign_file_in_authenticated_publication_is_never_removed(case,monkeypatch):
    options=published_interruption(case,monkeypatch)
    victim=options['output']/'metrics/bc001/T1/foreign.txt';victim.write_text('keep')
    before=workspace_identity(options['output'])
    for scope in ('metrics','routing','all'):
        with pytest.raises(w.WorkflowError,match='FOREIGN_CONTENT_PRESENT'):w.resume_workflow(**options,force=[scope])
        assert workspace_identity(options['output'])==before
    assert victim.read_text()=='keep'


def test_planted_destination_is_not_replaced(case,monkeypatch):
    options,_=case;rename=publication.rename_exclusive
    def collision(source,destination):
        destination.mkdir();(destination/'foreign').write_text('keep')
        rename(source,destination)
    monkeypatch.setattr(publication,'rename_exclusive',collision)
    with pytest.raises(w.WorkflowError,match='OUTPUT_EXISTS'):w.execute_workflow(**options)
    assert (options['output']/'metrics/bc001/T1/foreign').read_text()=='keep'
    with pytest.raises(w.WorkflowError,match='TAMPERED_STAGE_MANIFEST'):w.resume_workflow(**options,force=['metrics'])


def test_foreign_file_appearing_after_removal_check_survives(case,monkeypatch):
    options,_=complete(case)
    import peanalyzer.workflow_recovery as recovery
    original=recovery.check_removal_contents;calls=0
    def planted(root,node,manifest):
        nonlocal calls
        original(root,node,manifest)
        if node.stage_id=='metrics::bc001::T1':
            calls+=1
            if calls==2:(root/node.output_path/'foreign').write_text('keep')
    monkeypatch.setattr(recovery,'check_removal_contents',planted)
    with pytest.raises(w.WorkflowError):w.resume_workflow(**options,force=['metrics'])
    assert (options['output']/'metrics/bc001/T1/foreign').read_text()=='keep'
    assert not (options['output']/'workflow_manifest.json').exists()


@pytest.fixture
def private_keys(tmp_path,monkeypatch):
    new=tmp_path/'persistent/key';old=tmp_path/'volatile/key'
    monkeypatch.setattr(integrity,'key_path',lambda:new)
    monkeypatch.setattr(integrity,'legacy_key_path',lambda:old)
    return new,old


def test_persistent_key_migration_survives_volatile_cleanup(private_keys):
    new,old=private_keys
    legacy=integrity.signing_key(create=True,path=old)
    assert integrity.signing_key(create=True)==legacy
    old.unlink();old.parent.rmdir()
    assert integrity.signing_key()==legacy
    assert new.stat().st_mode & 0o777==0o600
    assert new.parent.stat().st_mode & 0o777==0o700
    code='from peanalyzer.workflow_integrity import signing_key; from pathlib import Path; import hashlib,sys; print(hashlib.sha256(signing_key(path=Path(sys.argv[1]))).hexdigest())'
    output=subprocess.check_output([sys.executable,'-c',code,str(new)],text=True)
    assert output.strip()==hashlib.sha256(legacy).hexdigest()
    assert integrity.signing_key(create=True)==legacy


def test_key_loss_and_rotation_fail_closed_without_false_tampering(case,private_keys):
    options,_=complete(case);new,old=private_keys
    original=new.read_bytes();new.unlink()
    for regenerated in (False,True):
        if regenerated:integrity.signing_key(create=True)
        with pytest.raises(w.WorkflowError,match='UNANCHORED_RECOVERY_OWNERSHIP'):w.resume_workflow(**options,force=['all'])
    new.write_bytes(original)
    assert integrity.authenticate(options['output'],plan(options))


@pytest.mark.parametrize('attack',['key_link','parent_link','permissions','hardlink','short'])
def test_key_paths_fail_closed(private_keys,tmp_path,attack):
    new,_=private_keys
    key=integrity.signing_key(create=True)
    if attack=='permissions':new.chmod(0o644)
    elif attack=='short':new.write_bytes(b'bad')
    elif attack=='hardlink':os.link(new,tmp_path/'other-key')
    elif attack=='key_link':
        new.unlink();new.symlink_to(tmp_path/'victim')
    else:
        new.unlink();new.parent.rmdir();new.parent.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(w.WorkflowError):integrity.signing_key(create=True)


def test_padded_draft_barcode_uses_authoritative_identity():
    from peanalyzer.gui.setup_models import DraftSample
    assert DraftSample(barcode_id=' 4A ').barcode_id=='4A'
    assert DraftSample(barcode_id=' 4a ').barcode_id=='4a'
    assert DraftSample(barcode_id='bad/id').barcode_id=='bad/id' # rejected by Setup validation, never rewritten


def test_legacy_partial_output_has_actionable_fail_closed_status(case,monkeypatch):
    options=published_interruption(case,monkeypatch)
    # Independently sign a receipt without publication proof, as v1.0.0 did.
    auth=integrity.authenticate(options['output'],plan(options));auth.publications={};auth.save()
    _,c=client_for(options);v=open_preview(c)
    response=c.post(f"/api/v1/recovery/{v['recovery_id']}/preview",json={'revision':v['revision'],'force':['metrics']}).json()
    assert response['classification']=='UNSUPPORTED' and not response['executable']
    assert 'legacy partial output' in response['reasons'][0]['detail']


def test_zero_samples_fail_before_first_backend_with_ids(tmp_path,monkeypatch):
    from m7_fixtures import fixture
    options=fixture(tmp_path/'inputs',samples=2,copies=1,reads=0)
    core=tmp_path/'CRISPResso';core.write_text('#!/bin/sh\necho CRISPResso 2.3.4\n');core.chmod(0o755)
    options['crispresso']=str(core)
    monkeypatch.setattr(w,'run_metrics',lambda **kw:pytest.fail('zero-read plate invoked metrics'))
    with pytest.raises(w.WorkflowError,match='EMPTY_SAMPLES') as caught:w.execute_workflow(**options)
    assert 'bc001' in str(caught.value) and 'bc002' in str(caught.value) and 'Setup/Review' in str(caught.value)
    assert not (options['output']/'workflow_manifest.json').exists()
    assert not list(tmp_path.glob('.workflow.metrics-attempt-*'))


def test_version_matching_executable_is_not_claimed_as_verified_image(case):
    from test_desktop_summary import projection
    options,_=complete(case) # fixture executable only prints a matching version
    _,view,p=projection(options['output'])
    fields={v.name:v.value for v in view.provenance}
    assert 'runtime_digest' not in fields
    assert p.backend_identity.runtime_digest in fields['declared_qualified_runtime']
    assert 'unverified' in fields['runtime_provenance']
    assert 'wrapper' in fields['runtime_provenance']
    assert p.backend_identity.executable_sha256 in fields['observed_executable_sha256']


def test_legacy_v1_receipt_authenticated_by_original_key(private_keys,tmp_path):
    import hmac
    from types import SimpleNamespace
    new,old=private_keys
    key=integrity.signing_key(create=True,path=old)
    root=tmp_path/'legacy-workspace';root.mkdir()
    payload=dict(version=1,workspace=integrity.binding(root),records={})
    w.atomic_json(root/integrity.RECEIPT,dict(payload=payload,mac=hmac.new(key,w.canonical(payload).encode(),'sha256').hexdigest()))
    assert integrity.authenticate(root,SimpleNamespace(nodes=[])).key==key
    old.unlink();integrity.signing_key(create=True)
    with pytest.raises(w.WorkflowError,match='RECOVERY_AUTHENTICATION_FAILED'):
        integrity.authenticate(root,SimpleNamespace(nodes=[]))


def test_handtyped_padded_ids_review_and_export_order(tmp_path,monkeypatch):
    from test_m11_setup import setup as setup_fixture, validate
    # Use the existing real Setup compiler fixture, not an alternate normalizer.
    fixture=setup_fixture.__wrapped__(tmp_path,monkeypatch)
    data=next(fixture)
    try:
        original=data[1]
        original['samples'].reverse()
        for sample in original['samples']:sample['barcode_id']=' '+sample['barcode_id']+' '
        draft,result=validate(data)
        assert result.status=='VALID'
        assert [s.barcode_id for s in draft.content.samples]==['bc002','bc001']
        assert result.preview.sample_ids==['bc001','bc002']
        assert [s['barcode_id'] for s in result._compiled['science']['samples']]==['bc001','bc002']
        from types import SimpleNamespace
        from peanalyzer.gui.summary_workbook import ordered_samples
        normalized=result._compiled['science']['samples']
        assert [s['barcode_id'] for s in ordered_samples(SimpleNamespace(samples=normalized),[s.barcode_id for s in draft.content.samples])]==['bc002','bc001']
        original['samples'][0]['barcode_id']='bad/id'
        _,invalid=validate(data)
        assert invalid.status=='INVALID'
    finally:
        try:next(fixture)
        except StopIteration:pass


def test_abrupt_worker_exit_preserves_partial_and_requires_lock_review(case,tmp_path):
    options,_=case
    serialized=tmp_path/'options.json';serialized.write_text(json.dumps(options,default=str))
    script=tmp_path/'crash_worker.py'
    script.write_text('''import os,json,sys
from pathlib import Path
from peanalyzer import workflow as w
options=json.loads(Path(sys.argv[1]).read_text())
def crash(**kw):
    p=kw['output'];p.mkdir(parents=True);(p/'backend-partial').write_bytes(b'nonempty output before abrupt death')
    os._exit(71)
w.run_metrics=crash
w.execute_workflow(**options)
''')
    process=subprocess.run([sys.executable,str(script),str(serialized)],capture_output=True,timeout=30)
    assert process.returncode==71,process.stderr.decode()
    assert not (options['output']/'workflow_manifest.json').exists()
    lock=options['output'].with_name('.workflow.m7-lock')
    assert lock.exists()
    with pytest.raises(w.WorkflowError,match='WORKFLOW_LOCKED'):w.resume_workflow(**options)
    # Only the test removes its known-dead child's lock; production never infers
    # stale ownership or removes a lock automatically.
    lock.unlink()
    w.resume_workflow(**options)
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'
    assert next(tmp_path.glob('.workflow.metrics-attempt-*/output/backend-partial')).read_bytes()==b'nonempty output before abrupt death'


@pytest.mark.parametrize('different_primary',[False,True])
def test_legacy_resume_preserves_original_credential_across_tmp_cleanup(case,private_keys,different_primary):
    import hmac,shutil
    options,_=case;new,old=private_keys
    key=integrity.signing_key(create=True,path=old)
    complete(case)
    receipt=options['output']/integrity.RECEIPT
    data=json.loads(receipt.read_text());payload=data['payload']
    payload.pop('key_id');payload.pop('publications');payload['version']=1
    data['mac']=hmac.new(key,w.canonical(payload).encode(),'sha256').hexdigest()
    w.atomic_json(receipt,data)
    new.unlink()
    if different_primary:new.write_bytes(os.urandom(32));new.chmod(0o600)
    before_primary=new.read_bytes() if different_primary else None
    (options['output']/'workflow_manifest.json').unlink()
    node=next(n for n in plan(options).nodes if n.stage_kind=='report')
    (options['output']/w.stage_manifest_path(node)).unlink();shutil.rmtree(options['output']/'report')
    w.resume_workflow(**options)
    old.unlink()
    assert integrity.authenticate(options['output'],plan(options)).key==key
    if different_primary:assert new.read_bytes()==before_primary
    else:assert new.read_bytes()==key


@pytest.mark.parametrize('relative,family',[('report/figures','report'),('analysis/03_analysis_fastq','analysis')])
def test_force_can_repair_missing_authenticated_subdirectories(case,relative,family):
    import shutil
    options,_=complete(case)
    shutil.rmtree(options['output']/relative)
    w.resume_workflow(**options,force=[family])
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'


def test_repeated_force_after_interruption_during_owned_directory_removal(case,monkeypatch):
    import peanalyzer.workflow_recovery as recovery
    options,_=complete(case);original=recovery.os.rmdir;interrupted=[]
    def interrupt(path,*args,**kwargs):
        original(path,*args,**kwargs)
        if path=='figures' and not interrupted:
            interrupted.append(True);raise KeyboardInterrupt()
    monkeypatch.setattr(recovery.os,'rmdir',interrupt)
    with pytest.raises(KeyboardInterrupt):w.resume_workflow(**options,force=['report'])
    assert not (options['output']/'workflow_manifest.json').exists()
    monkeypatch.setattr(recovery.os,'rmdir',original)
    w.resume_workflow(**options,force=['report'])
    assert w.verify_workflow_output(options['output']).status=='COMPLETED'


def test_concurrent_key_creation_never_overwrites_or_publishes_partial_key(private_keys):
    new,_=private_keys
    code='from peanalyzer.workflow_integrity import signing_key; from pathlib import Path; import os,sys,hashlib; print(hashlib.sha256(signing_key(create=True,path=Path(sys.argv[1]),_initial_key=os.urandom(32))).hexdigest())'
    processes=[subprocess.Popen([sys.executable,'-c',code,str(new)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)]
    hashes=[]
    for process in processes:
        out,err=process.communicate(timeout=30);assert process.returncode==0,err;hashes.append(out.strip())
    assert len(set(hashes))==1 and hashes[0]==hashlib.sha256(new.read_bytes()).hexdigest()
    assert new.stat().st_nlink==1 and not list(new.parent.glob('.key-*'))


def test_process_death_after_key_publication_leaves_valid_single_link(private_keys):
    new,_=private_keys
    code='''from peanalyzer import workflow_integrity as i
from pathlib import Path
import os,sys,stat
original=i.os.fsync
def crash(fd):
    original(fd)
    if stat.S_ISDIR(os.fstat(fd).st_mode):os._exit(71)
i.os.fsync=crash
i.signing_key(create=True,path=Path(sys.argv[1]),_initial_key=os.urandom(32))
'''
    result=subprocess.run([sys.executable,'-c',code,str(new)],capture_output=True,timeout=30)
    assert result.returncode==71,result.stderr.decode()
    assert integrity.signing_key()==new.read_bytes() and new.stat().st_nlink==1
    assert not list(new.parent.glob('.key-*'))
