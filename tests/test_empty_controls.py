import csv
import gzip
import json

import pytest

from m7_fixtures import fixture as pe_fixture, write_csv
from m8_fixtures import fixture as nuclease_fixture
from peanalyzer import workflow as workflow
from peanalyzer.validation import load_samples


def declare_controls(path, ids):
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row['sample_role'] = 'negative_control' if row['barcode_id'] in ids else ''
    write_csv(path, list(rows[0]), rows)


def version_probe(path):
    path.write_text('#!/bin/sh\nprintf "CRISPResso 2.3.4\\n"\n')
    path.chmod(0o755)
    return str(path)


@pytest.mark.parametrize('mode', ['pe', 'nuclease'])
def test_all_empty_controls_complete_verify_and_resume(tmp_path, monkeypatch, mode):
    options = (pe_fixture(tmp_path/'inputs', samples=2, copies=1, reads=0) if mode=='pe'
               else nuclease_fixture(tmp_path/'inputs', populations=[[], []]))
    options['crispresso'] = version_probe(tmp_path/'CRISPResso')
    declare_controls(options['samples'], {'bc001', 'bc002'})
    def unexpected(**kwargs):
        pytest.fail('Empty negative control invoked a backend')
    from peanalyzer import workflow_publication
    monkeypatch.setattr(workflow_publication, 'resolve_executable', lambda *args: pytest.fail(
        'Empty-sample metrics must not start a per-sample backend version probe'))
    monkeypatch.setattr(workflow, 'run_metrics', unexpected)
    monkeypatch.setattr(workflow, 'run_nuclease_metrics', unexpected)
    workflow.execute_workflow(**options)
    root = options['output']
    workflow.verify_workflow_output(root)
    workflow.execute_workflow(**options, resume=True)
    records = [json.loads(p.read_text()) for p in (root/'metrics').rglob('sample_qc.json')]
    assert {r['sample_id'] for r in records} == {'bc001','bc002'}
    assert all((r['depth_status'],r['prepared_read_pairs']) == ('EMPTY_NEGATIVE_CONTROL',0) for r in records)
    result = json.loads((root/'statistics/result.json').read_text())
    assert {r['sample_id'] for r in result['provenance']['input_results']} == {'bc001','bc002'}
    assert all(o['status']=='NOT_ASSESSABLE' and 'EMPTY_NEGATIVE_CONTROL' in o['reason_codes']
               and o['sample_role']=='negative_control' and o['fraction'] is None for o in result['observations'])
    assert result['observations'] and all(g['reportable_count']==0 for g in result['group_summaries'])
    assert 'EMPTY_NEGATIVE_CONTROL' in (root/'report/report.html').read_text()


def test_empty_control_with_populated_experimental_sample(tmp_path, monkeypatch):
    from test_m7 import case
    options, calls = case.__wrapped__(tmp_path, monkeypatch)
    for key in ('r1', 'r2'):
        path=options[key]
        with gzip.open(path, 'rb') as stream:
            records=list(zip(*[iter(stream)]*4))
        with gzip.open(path, 'wb') as stream:
            for record in records:
                if record[0].startswith(b'@bc002'):
                    stream.writelines(record)
    # Barcode names alone have no control semantics.
    assert all(s.sample_role=='experimental' for s in load_samples(options['samples']))
    declare_controls(options['samples'], {'bc001'})
    workflow.execute_workflow(**options)
    assert calls['run_metrics']==1
    qc=[json.loads(p.read_text()) for p in (options['output']/'metrics').rglob('sample_qc.json')]
    assert {r['sample_id']:r['depth_status'] for r in qc}=={'bc001':'EMPTY_NEGATIVE_CONTROL','bc002':'BELOW_MINIMUM'}
    result=json.loads((options['output']/'statistics/result.json').read_text())
    assert all(o['fraction'] is None for o in result['observations'] if o['sample_id']=='bc001')
    assert any(o['fraction'] is not None for o in result['observations'] if o['sample_id']=='bc002')


def test_bridge_displacement_and_trim_offsets_leave_assignment_intact(tmp_path, example_dir):
    from peanalyzer.analysis_fastq import PreparationConfig, prepare_analysis_fastqs
    from peanalyzer.barcodes import bundled_catalog, extraction_rules, load_catalog
    from peanalyzer.demux import demultiplex
    from peanalyzer.schemas import Config
    from synthetic import record, write_pairs

    config = Config(schema_version=1)
    catalog = load_catalog(bundled_catalog())
    rules = extraction_rules(config.demux, catalog)
    def pair(name, shift):
        return (record(name, catalog.ends['forward']['F1'] + shift + rules['forward'].bridge + 'TACGT', 1),
                record(name, catalog.ends['reverse']['RB'] + rules['reverse'].bridge + 'TACGT', 2))
    reads = write_pairs(tmp_path, [pair('standard', ''), pair('inserted', 'T')])
    archive = tmp_path/'demux'
    summary = demultiplex(r1=reads[0], r2=reads[1], samples_path=example_dir/'ev_only_1005_samples.csv',
                          config=config, output=archive)
    qc = summary['bridge_boundary_qc']
    assert qc['per_mate']['forward']['exact_match_fraction'] == 0.5
    assert summary['barcode_bridge_qc']['forward']['bridge_displaced_+1'] == 1
    assert qc['per_sample_pairs_with_short_or_mismatched_bridge']['1B'] == dict(forward=1, reverse=0, either_mate=1)
    assert summary['per_sample_assigned_read_pairs']['1B']==2
    # Deliberately different requested boundary on each mate, independently of bridge matching.
    manifest = prepare_analysis_fastqs(archive, tmp_path/'analysis', PreparationConfig(r1_analysis_trim_5p=1,r2_analysis_trim_5p=2))
    for mate, trim in [('forward',1),('reverse',2)]:
        data=manifest['trim_boundary_qc'][mate]
        assert data['total_removed_from_raw_5p']==trim
        assert data['offset_from_expected_bridge_end']==trim-data['expected_bridge_end_0based']
