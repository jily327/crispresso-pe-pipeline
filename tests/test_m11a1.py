"""Focused setup/execution-constraint parity; no scientific work in setup calls."""
import copy
import gzip
import json
from pathlib import Path

import pytest
from peanalyzer.aggregation import AggregationError, collect_observations
from peanalyzer.gui.setup_models import PETargetDraft
from peanalyzer.gui.workspace import ViewerError
from peanalyzer.remediation import indel_designs
from peanalyzer.workflow_storage import canonical
from m5_fixtures import result_document, write_json, write_manifest, write_samples
from m11a1_guards import zero_execution
from test_m11_setup import setup, validate, nuclease, inventory


CASES = [('duplicate', False), ('treatment', True), ('dpi', True),
         ('editor', True), ('biological_replicate', True)]


def replicate_rows(rows, change):
    rows = copy.deepcopy(rows)
    for field in ('editor', 'treatment', 'dpi', 'biological_replicate'):
        rows[1][field] = rows[0][field]
    if change != 'duplicate':
        rows[1][change] = '7' if change == 'dpi' else 'different'
    return rows


@pytest.mark.parametrize('change,allowed', CASES)
def test_actual_aggregation_replicate_oracle(tmp_path, change, allowed):
    # Independent downstream oracle, outside setup and its no-execution context.
    rows = [dict(sample_name=f'bio{i}', barcode_id=f'bc{i}',
        forward_barcode='AAAA', reverse_barcode='CCCC', editor='synthetic-editor',
        treatment='A', dpi='6', biological_replicate='1', block_id='', paired='false')
        for i in (1, 2)]
    rows = replicate_rows(rows, change)
    write_samples(tmp_path/'samples.csv', rows)
    for row in rows:
        write_json(tmp_path/(row['barcode_id']+'.json'), result_document(row['barcode_id'], 'T1', 1, 10))
    write_manifest(tmp_path/'manifest.csv', ['bc1.json', 'bc2.json'])
    if allowed:
        assert collect_observations(tmp_path/'manifest.csv', tmp_path/'samples.csv').observations
    else:
        with pytest.raises(AggregationError, match='duplicate biological_replicate within condition and target'):
            collect_observations(tmp_path/'manifest.csv', tmp_path/'samples.csv')


@pytest.mark.parametrize('mode', ['precise_edit', 'indel_nuclease'])
@pytest.mark.parametrize('change,allowed', CASES)
def test_setup_replicates_match_downstream_rule(setup, mode, change, allowed):
    data = copy.deepcopy(setup[1]) if mode == 'precise_edit' else nuclease(setup[1])
    data['samples'] = replicate_rows(data['samples'], change)
    before = inventory(setup[3].parent)
    with zero_execution():
        draft, result = validate(setup, data)
        assert result.status == ('VALID' if allowed else 'INVALID')
        if allowed:
            assert setup[0].preview(draft.draft_id, draft.revision) == result.preview
        else:
            assert result.preview is None
            issues = [i for i in result.issues if i.code == 'DUPLICATE_BIOLOGICAL_REPLICATE']
            assert {i.field for i in issues} == {'samples.0.biological_replicate', 'samples.1.biological_replicate'}
            assert all(all(s['barcode_id'] in i.message for s in data['samples']) for i in issues)
            assert all('T1' in i.message for i in issues)
            with pytest.raises(ViewerError, match='DRAFT_NOT_VALIDATED'):
                setup[0].preview(draft.draft_id, draft.revision)
    assert inventory(setup[3].parent) == before


def ambiguous_deletion():
    targets = next(ts for design, ts in indel_designs() if design['id'] == 'deletion_1_seed11')
    return [{k: '' if v is None else v for k, v in t.model_dump().items()
             if k in PETargetDraft.model_fields} for t in targets]


def test_nonunique_deletion_is_partial_limitation_not_invalid_target(setup):
    data = copy.deepcopy(setup[1]); data['targets'] = ambiguous_deletion()
    before = inventory(setup[3].parent)
    with zero_execution():
        draft, result = validate(setup, data)
        assert result.status == 'VALID'
        assert setup[0].preview(draft.draft_id, draft.revision) == result.preview
        for code in ('NONUNIQUE_REFERENCE_ALIGNMENT', 'NONUNIQUE_EDIT_ALIGNMENT'):
            issues = [i for i in result.issues if i.code == code]
            assert issues and all(i.severity == 'WARNING' for i in issues)
            assert all(json.loads(i.detail)['code'] == code for i in issues)
            assert all('unavailable' in i.message for i in issues)
        assert result.targets and result.preview.executable is False
    assert inventory(setup[3].parent) == before


@pytest.mark.parametrize('mode', ['precise_edit', 'indel_nuclease'])
def test_empty_raw_pool_cannot_reach_review(setup, mode):
    data = copy.deepcopy(setup[1]) if mode == 'precise_edit' else nuclease(setup[1])
    for mate in ('r1', 'r2'):
        setup[2][mate].write_bytes(gzip.compress(b'', mtime=0))
    before = inventory(setup[3].parent)
    with zero_execution():
        draft, result = validate(setup, data)
        assert result.status == 'INVALID' and result.preview is None
        assert any(i.code == 'EMPTY_INPUT' and i.severity == 'ERROR' for i in result.issues)
        with pytest.raises(ViewerError, match='DRAFT_NOT_VALIDATED'):
            setup[0].preview(draft.draft_id, draft.revision)
    assert inventory(setup[3].parent) == before


def test_missing_block_error_points_to_block_field(setup):
    data = copy.deepcopy(setup[1]); data['samples'][0]['paired'] = True
    data['samples'][0]['block_id'] = ''
    before = inventory(setup[3].parent)
    with zero_execution():
        _, result = validate(setup, data)
        issues = [i for i in result.issues if 'paired samples require block_id' in i.message]
        assert result.status == 'INVALID' and result.preview is None
        assert len(issues) == 1 and issues[0].field == 'samples.0.block_id'
    assert inventory(setup[3].parent) == before


def test_metadata_identity_and_presentation_identity_are_preserved(setup):
    with zero_execution():
        draft, baseline = validate(setup)
        assert canonical(baseline) == canonical(setup[0].validate(draft.draft_id, draft.revision))
        renamed = copy.deepcopy(setup[1]); renamed['analysis_name'] = 'Display label'
        _, label = validate(setup, renamed)
        assert label.preview.scientific_identity_sha256 == baseline.preview.scientific_identity_sha256
        assert label.preview.plan_identity_sha256 != baseline.preview.plan_identity_sha256
        changed = copy.deepcopy(setup[1]); changed['samples'][0]['biological_replicate'] = 'other'
        _, science = validate(setup, changed)
        assert science.preview.scientific_identity_sha256 != baseline.preview.scientific_identity_sha256


def test_duplicate_replicate_focus_uses_original_row_after_csv_normalization(setup):
    data = copy.deepcopy(setup[1])
    data['samples'] = replicate_rows(data['samples'], 'duplicate')
    data['samples'].reverse()
    for row in data['samples']:
        row['barcode_id'] = ' '+row['barcode_id']+' '
        row['biological_replicate'] = ' '+row['biological_replicate']+' '
    with zero_execution():
        _, result = validate(setup, data)
        assert result.status == 'INVALID' and result.preview is None
        assert {i.field for i in result.issues if i.code == 'DUPLICATE_BIOLOGICAL_REPLICATE'} == {
            'samples.0.biological_replicate', 'samples.1.biological_replicate'}
