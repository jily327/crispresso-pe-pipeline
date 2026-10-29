"""FROZEN future adapter contract. Run explicitly with auditor-written -p binding.
No endpoint, selector, path ownership, or candidate implementation is assumed.
Missing audit_adapter MUST error, never skip or silently approve.
See ADAPTER.md for method semantics; run against disposable server inputs only.
"""
import hashlib,json
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parent
NAMES=['../../VICTIM.fastq.gz',r'..\..\VICTIM.fastq.gz','/tmp/VICTIM.fastq.gz',r'C:\Windows\System32\VICTIM.fastq.gz','..%2f..%2fVICTIM.fastq.gz','..%5c..%5cVICTIM.fastq.gz','..%252fVICTIM.fastq.gz','..∕..∕VICTIM.fastq.gz','a'*4096+'.fastq.gz','.hidden.fastq.gz','duplicate.fastq.gz']
@pytest.mark.parametrize('name',NAMES)
def test_upload_filename(audit_adapter,name):
    a=audit_adapter;before=a.victim_snapshot();raw=(HERE/'fixtures/R1.fastq.gz').read_bytes()
    result=a.upload(name,iter([raw]))
    assert a.victim_snapshot()==before
    if result.accepted:
        assert a.registered_bytes(result.capability)==raw
        assert a.is_owned_regular_file(result.capability)
        assert not a.path_controlled_by_client(result.capability,name)

@pytest.mark.parametrize('boundary',['zero','first','middle','last-before-finalize','written-before-register'])
def test_interruption(audit_adapter,boundary):
    a=audit_adapter;before=a.accepted_capabilities();victims=a.victim_snapshot()
    a.interrupt_upload(HERE/'fixtures/R1.fastq.gz',boundary)
    assert a.accepted_capabilities()==before
    assert a.victim_snapshot()==victims
    assert not a.accepted_partial_files()
    assert a.staging_safe_after_settle()

@pytest.mark.parametrize('attack',['staging-symlink','replace-temp','external-symlink','directory-substitution'])
def test_symlink(audit_adapter,attack):
    a=audit_adapter;before=a.victim_snapshot();caps=a.accepted_capabilities()
    a.upload_with_owned_staging_fault(attack,HERE/'fixtures/R1.fastq.gz')
    assert a.victim_snapshot()==before and a.accepted_capabilities()==caps

@pytest.mark.parametrize('target',['/etc/passwd','owned-workspace','other-analysis','legacy-input'])
def test_server_path_not_upload(audit_adapter,target):
    a=audit_adapter;before=a.accepted_capabilities();victims=a.victim_snapshot()
    result=a.send_path_instead_of_file(target)
    assert not result.accepted and a.accepted_capabilities()==before
    assert a.victim_snapshot()==victims

def test_legacy_ownership(audit_adapter):
    a=audit_adapter;legacy=a.register_external_fixture();before=a.victim_snapshot()
    first=a.upload('same.fastq.gz',iter([(HERE/'fixtures/R1.fastq.gz').read_bytes()]))
    second=a.upload('same.fastq.gz',iter([(HERE/'fixtures/R2.fastq.gz').read_bytes()]))
    assert first.accepted and second.accepted
    a.replace_selected_upload(first.capability,second.capability)
    a.cleanup_uploads();assert a.victim_snapshot()==before and a.external_exists(legacy)

@pytest.mark.parametrize('case',json.loads((HERE/'fixtures/excel-cases.json').read_text()))
def test_excel(audit_adapter,case):
    a=audit_adapter;before=a.draft_snapshot();result=a.import_workbook(HERE/'fixtures'/(case+'.xlsx'))
    expectation=json.loads((HERE/'fixtures/excel-cases.json').read_text())[case]['expectation']
    if expectation=='reject':assert not result.accepted and a.draft_snapshot()==before
    else:
        assert result.accepted
        assert a.canonical_imported_samples()==a.authoritative_manual_equivalent(case)

def test_catalog_dependency(audit_adapter):
    a=audit_adapter
    # Binding perturbs a fresh in-memory backend Catalog, never the frozen file.
    assert a.import_with_catalog_probe(HERE/'fixtures/catalog-4A.xlsx','F4','ACGTACGTA')=='ACGTACGTA'

def test_upload_streaming(audit_adapter,tmp_path):
    a=audit_adapter;path=a.generate_large_fastq(tmp_path,minimum_compressed_bytes=32*1024*1024)
    before=a.victim_snapshot();result=a.upload_file_in_chunks(path,chunk_size=65536)
    assert result.accepted
    observed=a.registered_identity(result.capability)
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):h.update(block)
    assert observed=={'sha256':h.hexdigest(),'size_bytes':path.stat().st_size}
    assert a.victim_snapshot()==before
    assert a.streaming_evidence().bounded_reads_and_no_linear_rss_growth

@pytest.mark.parametrize('scenario',json.loads((HERE/'fixtures/metric-display.json').read_text())['scenarios'])
def test_visible_metric_values(audit_adapter,scenario):
    a=audit_adapter;rows=json.loads((HERE/'fixtures/metric-display.json').read_text())['scenarios'][scenario]
    a.render_metric_scenario(rows)
    for row in rows:
        key=(row['sample_id'],row['target'],row['metric_name'],row['copy_name'],row['policy_id'])
        visible=a.visible_metric_cells(key)
        for field in ('numerator','denominator','percentage','status'):
            assert visible[field]==row[field]  # absence marker maps only to None, never zero
    assert a.primary_metrics_precede_copy_diagnostics()
    assert a.samples_has_simultaneous_primary_columns()
    if scenario=='missing-comparator':assert a.comparator_is_visibly_unavailable()

def test_verification_presentation(audit_adapter):
    a=audit_adapter
    for frame in json.loads((HERE/'fixtures/job-timeline.json').read_text()):
        a.deliver_job_frame(frame)
        assert a.authoritative_job_state()==frame['state']
        assert a.displayed_finished_stages()==frame['finished']
        if frame['phase'] in ('final-verification','viewer-verification'):
            assert a.verification_message_prominent() and not a.open_results_available()
        if frame['phase']=='complete':assert a.open_results_available()
    for terminal in ('FAILED','CANCELLED','CANCELLING'):
        a.deliver_terminal_after_verification(terminal)
        assert a.authoritative_job_state()==terminal and not a.open_results_available()
        assert not a.verification_message_primary()

def test_version_sources(audit_adapter):
    versions=audit_adapter.actual_current_versions()
    assert set(versions)>={'project','runtime','installed','wheel','capabilities','ui','frontend','npm_lock'}
    assert set(versions.values())=={'0.9.0'}
    assert audit_adapter.static_build_identity_valid()
    assert audit_adapter.historical_evidence_unchanged()

def test_legacy_upload_scientific_parity(audit_adapter):
    # These are actual execution outputs from two paths on the same candidate,
    # not data synthesized from a preview or normalized through candidate code.
    legacy,uploaded=audit_adapter.execute_identical_bytes_both_paths()
    fields=('fastq_hashes','fastq_sizes','samples','catalog','scientific_config',
            'target_definitions','routing_policy','scientific_dag','prepared_records',
            'routing_assignments','metric_values','metric_status_reasons','qc_counts',
            'statistical_values','scientific_report_values')
    for field in fields:assert legacy[field]==uploaded[field],field
    assert audit_adapter.identity_differences_follow_frozen_constituents(legacy,uploaded)
