"""Independent statistical oracles, identity attacks, design gates and offline CLI."""
import csv
import itertools
import json
import os
from fractions import Fraction
from importlib.resources import files
from pathlib import Path
import subprocess
import sys

import pytest
import yaml
from pydantic import ValidationError

from peanalyzer.aggregation import AggregationError, publish, summarize
from peanalyzer.statistics import (MAX_PERMUTATIONS, benjamini_hochberg, exact_paired,
                                  exact_unpaired, stats)
from peanalyzer.statistical_models import ContrastSpecification, StatisticsResult
from m5_fixtures import (change_record, contrast, dataset, read_samples, result_document,
                         write_json, write_manifest, write_samples)

ROOT = Path(__file__).resolve().parents[1]
ORACLES = json.loads((ROOT / 'docs/validation/m5/oracles.json').read_text())


@pytest.fixture
def inputs(tmp_path):
    return dataset(tmp_path / 'inputs')


def summary(inputs):
    return summarize(manifest_path=inputs['manifest_path'], samples_path=inputs['samples_path'])


def mutate(inputs, change, name='A001-T1.json'):
    path = inputs['manifest_path'].parent / name
    raw = json.loads(path.read_text())
    change(raw)
    write_json(path, raw)


def specification(inputs, change):
    path = inputs['contrasts_path']
    raw = yaml.safe_load(path.read_text())
    change(raw)
    path.write_text(yaml.safe_dump(raw))


def native(result):
    return next(c for c in result.contrasts if c.contrast_id == 'native')


@pytest.mark.parametrize('oracle', ORACLES['unpaired'])
def test_hand_enumerated_unpaired(oracle):
    effect, space, extreme = exact_unpaired(map(Fraction, oracle['a']), map(Fraction, oracle['b']))
    assert (effect, space, extreme, Fraction(extreme, space)) == (
        Fraction(oracle['effect']), oracle['space'], oracle['extreme'], Fraction(oracle['p']))
    for a in itertools.permutations(oracle['a']):
        for b in itertools.permutations(oracle['b']):
            assert exact_unpaired(map(Fraction, a), map(Fraction, b)) == (effect, space, extreme)


@pytest.mark.parametrize('oracle', ORACLES['paired'])
def test_hand_enumerated_paired(oracle):
    expected = Fraction(oracle['effect']), oracle['space'], oracle['extreme']
    for order in itertools.permutations(oracle['differences']):
        assert exact_paired(map(Fraction, order)) == expected
    assert Fraction(expected[2], expected[1]) == Fraction(oracle['p'])


@pytest.mark.parametrize('oracle', ORACLES['bh'])
def test_hand_calculated_bh(oracle):
    values = dict(zip(map(str, range(len(oracle['p']))), oracle['p']))
    result = benjamini_hochberg(values)
    assert list(result.values()) == pytest.approx(oracle['q'])
    assert benjamini_hochberg(dict(reversed(list(values.items())))) == result
    assert all(values[k] <= q <= 1 for k, q in result.items())
    assert [result[k] for k in sorted(values, key=values.get)] == sorted(result.values())


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf'), -0.1, 1.1])
def test_bh_rejects_invalid_probabilities(value):
    with pytest.raises(AggregationError):
        benjamini_hochberg({'invalid': value})


def test_multisample_populations_and_exact_contrasts(inputs):
    result = stats(**inputs)
    assert len(result.observations) == 144
    assert len(result.group_summaries) == 48
    assert {r.target_name for r in result.observations} == {'T1', 'T2'}
    assert {r.copy_name for r in result.observations} == {None, 'copy1', 'copy2'}
    assert {r.policy_id for r in result.observations} == {None, 'policy0', 'policy1'}
    for row in result.observations:
        assert row.fraction == row.numerator / row.denominator
        assert row.routing_conditioned == (row.copy_name is not None)
    for c in result.contrasts:
        assert c.status == 'REPORTABLE'
        assert (c.permutation_space_size, c.permutation_count, c.extreme_count, c.p_value) == (20, 20, 2, 0.1)
        assert c.q_value == 0.1
        assert c.used_group_a_count == c.used_group_b_count == 3
    assert native(result).difference_in_biological_sample_fraction == pytest.approx(0.8)
    assert [(f.family_id, f.valid_test_count) for f in result.multiple_testing_families] == [('primary', 4), ('secondary', 1)]


def test_descriptive_weighting_oracle(tmp_path):
    inputs = dataset(tmp_path, replicates=2, targets=('T1',))
    write_json(tmp_path / 'A001-T1.json', result_document('barcode-A001', 'T1', 1, 10))
    write_json(tmp_path / 'A002-T1.json', result_document('barcode-A002', 'T1', 90, 100))
    result = summary(inputs)
    group = next(s for s in result.group_summaries if s.metric_name == 'total_precise_pe' and s.condition.treatment == 'A')
    assert group.mean_biological_sample_fraction == group.median_biological_sample_fraction == 0.5
    assert group.pooled_read_fraction == 91 / 110
    assert group.minimum_biological_sample_fraction == 0.1
    assert group.maximum_biological_sample_fraction == 0.9
    assert group.pooled_read_fraction_label == 'POOLED READ-WEIGHTED DESCRIPTIVE FRACTION'
    assert [(s.numerator, s.denominator) for s in group.source_fractions] == [(1, 10), (90, 100)]


@pytest.mark.parametrize('status', ['BLOCKED', 'NOT_ASSESSABLE'])
def test_mixed_status_retained_and_inference_uses_valid_samples(inputs, status):
    change_record(inputs['manifest_path'].parent / 'A001-T1.json', status)
    result = stats(**inputs)
    c = native(result)
    assert c.status == 'REPORTABLE' and c.used_group_a_count == 2
    excluded = next(s for s in c.expected_group_a if s.sample_name == 'A001')
    assert excluded.status == status and excluded.reason_codes == ['SYNTHETIC_' + status]
    row = next(r for r in result.observations if r.sample_name == 'A001' and r.target_name == 'T1' and r.metric_name == c.metric_name)
    assert row.numerator is row.denominator is row.fraction is None
    group = next(g for g in result.group_summaries if g.target_name == 'T1' and g.metric_name == c.metric_name and g.condition.treatment == 'A')
    assert group.expected_sample_count == 3 and group.reportable_count == 2
    assert group.blocked_count + group.not_assessable_count == 1


def test_all_nonreportable_and_mixed_bh_family(inputs):
    for name in ('A001', 'A002', 'A003', 'B001', 'B002', 'B003'):
        change_record(inputs['manifest_path'].parent / f'{name}-T1.json', 'NOT_ASSESSABLE')
    result = stats(**inputs)
    c = native(result)
    assert c.status == 'NOT_ASSESSABLE' and c.p_value is c.q_value is None
    assert c.reason_codes == ['INSUFFICIENT_BIOLOGICAL_REPLICATES']
    assert c.valid_tests_in_family == 3
    group = next(g for g in result.group_summaries if g.target_name == 'T1' and g.metric_name == c.metric_name)
    assert group.mean_biological_sample_fraction is group.pooled_read_fraction is None
    assert group.not_assessable_count == 3


def test_missing_policy_is_explicit_without_fabricating_observations(inputs):
    mutate(inputs, lambda r: r['derived_metrics']['target'].pop('policy1'))
    result = stats(**inputs)
    c = next(c for c in result.contrasts if c.contrast_id == 'family')
    assert c.expected_group_a_count == 3 and c.used_group_a_count == 2
    assert c.expected_group_a[0].status == 'MISSING_METRIC'
    assert c.expected_group_a[0].reason_codes == ['METRIC_NOT_PRESENT']
    assert len(result.observations) == 143


@pytest.mark.parametrize('kind', ['same_path', 'alias_path', 'duplicate_analysis'])
def test_duplicate_analysis_never_selected(inputs, kind):
    root = inputs['manifest_path'].parent
    paths = list(csv.DictReader(inputs['manifest_path'].open()))
    entries = [p['result_json'] for p in paths]
    if kind == 'same_path':
        entries.append(entries[0])
    elif kind == 'alias_path':
        (root / 'alias.json').symlink_to(root / entries[0])
        entries.append('alias.json')
    else:
        raw = json.loads((root / entries[0]).read_text())
        raw['analysis_id'] = 'different-analysis'
        write_json(root / 'second.json', raw)
        entries.append('second.json')
    write_manifest(inputs['manifest_path'], entries)
    with pytest.raises(AggregationError, match='duplicate'):
        summary(inputs)


ATTACKS = [
    ('schema', lambda r: r.update(schema_version=2)),
    ('boolean_schema', lambda r: r.update(schema_version=True)),
    ('missing_schema', lambda r: r.pop('schema_version')),
    ('contract', lambda r: r.update(metric_contract_version='m4-future')),
    ('missing_sample', lambda r: r.update(sample_id='unknown')),
    ('target', lambda r: r.update(target_id='other-target')),
    ('target_definition', lambda r: r['provenance'].update(target_definitions_sha256='a'*64)),
    ('population', lambda r: r['target_metrics']['total_precise_pe'].update(population_id='unknown')),
    ('zero_reportable', lambda r: r['target_metrics']['target_crispresso_native_pe'].update(denominator=0)),
    ('status_counts', lambda r: r['target_metrics']['target_crispresso_native_pe'].update(status='BLOCKED')),
    ('copy_collision', lambda r: r['copies']['copy1']['precise'].update(population_scope='target_all_prepared', copy_id=None, routing_conditioned=False)),
    ('family_population', lambda r: r['derived_metrics']['target']['policy1'].update(population_id=r['copies']['copy1']['precise']['population_id'])),
    ('family_name', lambda r: r['derived_metrics']['target']['policy1'].update(metric_name='copy1_pe_family')),
    ('policy_collision', lambda r: r['derived_metrics']['target']['policy1']['policy'].update(max_extra_substitutions=2)),
    ('invalid_policy', lambda r: r['derived_metrics']['target']['policy1']['policy'].update(max_extra_indel_events=1)),
    ('policy_identity', lambda r: r['derived_metrics']['target']['policy1']['policy'].update(policy_id='other')),
    ('duplicate_series', lambda r: r['derived_metrics']['target'].update(second=r['derived_metrics']['target']['policy1'])),
    ('evidence_target', lambda r: r['product_evidence']['target']['targets'][0].update(target_name='different')),
    ('qc_population', lambda r: r['qc'].update(prepared_input_reads=10000)),
    ('sample_population', lambda r: r['provenance']['prepared_sample'].update(pairs=10000)),
]


@pytest.mark.parametrize('label,attack', ATTACKS, ids=[a[0] for a in ATTACKS])
def test_corrupt_m4_input_fails_closed(inputs, label, attack):
    mutate(inputs, attack)
    with pytest.raises(AggregationError):
        stats(**inputs)


@pytest.mark.parametrize('content', ['{', '{"schema_version":1,"schema_version":1}', '{"x":NaN}'])
def test_malformed_or_ambiguous_json(inputs, content):
    (inputs['manifest_path'].parent / 'A001-T1.json').write_text(content)
    with pytest.raises(AggregationError):
        summary(inputs)


@pytest.mark.parametrize('field', ['sample_name', 'barcode_id', 'biological_replicate'])
def test_duplicate_metadata_identity(inputs, field):
    rows = read_samples(inputs['samples_path'])
    rows[1][field] = rows[0][field]
    write_samples(inputs['samples_path'], rows)
    with pytest.raises(AggregationError, match='duplicate'):
        summary(inputs)


def test_absent_metadata_and_no_name_fallback(inputs):
    rows = read_samples(inputs['samples_path'])
    rows[0]['sample_name'] = rows[0]['barcode_id']
    rows[0]['barcode_id'] = 'other-barcode'
    write_samples(inputs['samples_path'], rows)
    with pytest.raises(AggregationError, match='absent from metadata'):
        summary(inputs)


def test_unused_metadata_does_not_create_observation(inputs):
    rows = read_samples(inputs['samples_path'])
    rows.append(rows[0] | dict(sample_name='unused', barcode_id='unused', biological_replicate='unused'))
    write_samples(inputs['samples_path'], rows)
    result = summary(inputs)
    assert result.unused_metadata_sample_ids == ['unused'] and len(result.observations) == 144


@pytest.mark.parametrize('attack', [
    lambda r: r['contrasts'].append(r['contrasts'][0]),
    lambda r: r['families'].append('primary'),
    lambda r: r['contrasts'][0].update(family_id='undeclared'),
    lambda r: r['contrasts'][0].update(pairing_mode='automatic'),
    lambda r: r['contrasts'][0].pop('pairing_mode'),
    lambda r: r['contrasts'][0].update(alternative='one-sided'),
    lambda r: r['contrasts'][0]['group_a'].update(treatment='unknown'),
    lambda r: r['contrasts'][0]['group_a'].update(editor=''),
    lambda r: r['contrasts'][0].update(group_a={}),
    lambda r: r['contrasts'][0].update(group_b=r['contrasts'][0]['group_a']),
    lambda r: r['contrasts'][0].update(metric_name='unknown'),
    lambda r: r['contrasts'][0].update(copy_name='copy1'),
    lambda r: r['contrasts'][0].update(policy_id='unknown'),
])
def test_invalid_contrast_specification(inputs, attack):
    specification(inputs, attack)
    with pytest.raises(AggregationError):
        stats(**inputs)


def test_yaml_duplicate_key(inputs):
    inputs['contrasts_path'].write_text('schema_version: 1\nschema_version: 1\n')
    with pytest.raises(AggregationError, match='duplicate YAML'):
        stats(**inputs)


def test_paired_three_blocks(tmp_path):
    result = stats(**dataset(tmp_path, paired=True))
    c = native(result)
    assert c.complete_blocks == ['block001', 'block002', 'block003']
    assert (c.permutation_count, c.extreme_count, c.p_value, c.difference_in_biological_sample_fraction) == (8, 2, 0.25, 0.8)


def test_incomplete_and_blocked_pairs_are_explicit(tmp_path):
    inputs = dataset(tmp_path, paired=True, replicates=5)
    paths = [r['result_json'] for r in csv.DictReader(inputs['manifest_path'].open()) if not r['result_json'].startswith('B004-')]
    write_manifest(inputs['manifest_path'], paths)
    change_record(tmp_path / 'A005-T1.json', 'BLOCKED')
    c = native(stats(**inputs))
    assert c.status == 'REPORTABLE' and c.permutation_count == 8 and c.p_value == 0.25
    assert c.expected_group_a_count == 5 and c.expected_group_b_count == 4
    assert c.used_group_a_count == c.used_group_b_count == 3
    assert [(b.block_id, b.reason_codes) for b in c.excluded_blocks] == [
        ('block004', ['MISSING_GROUP_B']), ('block005', ['NONREPORTABLE_BLOCK_OBSERVATION', 'SYNTHETIC_BLOCKED'])]


@pytest.mark.parametrize('group', ['A', 'B'])
def test_duplicate_block_group_blocks_inference(tmp_path, group):
    inputs = dataset(tmp_path, paired=True)
    rows = read_samples(inputs['samples_path'])
    next(r for r in rows if r['sample_name'] == group + '002')['block_id'] = 'block001'
    write_samples(inputs['samples_path'], rows)
    c = native(stats(**inputs))
    assert c.status == 'BLOCKED' and c.p_value is c.q_value is None
    assert 'DUPLICATE_BLOCK_GROUP_OBSERVATIONS' in c.reason_codes


@pytest.mark.parametrize('kind', ['paired_true', 'shared_block', 'block_mode_without_pairing', 'missing_block'])
def test_pairing_cannot_be_silently_discarded(inputs, kind):
    rows = read_samples(inputs['samples_path'])
    if kind in ('paired_true', 'shared_block'):
        for row in rows:
            row['block_id'] = 'shared'
            row['paired'] = 'true' if kind == 'paired_true' else 'false'
    elif kind == 'block_mode_without_pairing':
        specification(inputs, lambda r: r['contrasts'][0].update(pairing_mode='block'))
    else:
        rows[0]['paired'] = 'true'
    write_samples(inputs['samples_path'], rows)
    if kind == 'missing_block':
        with pytest.raises(AggregationError, match='block_id'):
            stats(**inputs)
    else:
        c = native(stats(**inputs))
        assert c.status == 'BLOCKED' and c.p_value is c.q_value is None


@pytest.mark.parametrize('paired', [False, True])
def test_minimum_biological_units(tmp_path, paired):
    c = native(stats(**dataset(tmp_path, paired=paired, replicates=1)))
    assert c.status == 'NOT_ASSESSABLE' and c.p_value is c.q_value is None
    assert c.reason_codes == ['INSUFFICIENT_BIOLOGICAL_REPLICATES']


@pytest.mark.parametrize('paired,cap,expected', [(False, 20, 'REPORTABLE'), (False, 19, 'NOT_ASSESSABLE'),
                                               (True, 8, 'REPORTABLE'), (True, 7, 'NOT_ASSESSABLE')])
def test_exact_space_boundary(tmp_path, paired, cap, expected):
    c = native(stats(**dataset(tmp_path, paired=paired), max_permutations=cap))
    assert c.status == expected
    if expected != 'REPORTABLE':
        assert c.reason_codes == ['PERMUTATION_SPACE_TOO_LARGE'] and c.p_value is None and c.permutation_count is None


@pytest.mark.parametrize('maximum', [0, -1, True, MAX_PERMUTATIONS + 1])
def test_cannot_raise_hard_cap(inputs, maximum):
    with pytest.raises(AggregationError):
        stats(**inputs, max_permutations=maximum)


def test_default_cap_prevents_combinatorial_execution(tmp_path):
    c = native(stats(**dataset(tmp_path, replicates=10, targets=('T1',))))
    assert c.permutation_space_size == 184756 and c.reason_codes == ['PERMUTATION_SPACE_TOO_LARGE']


def test_zero_effect_and_exact_resolution():
    assert exact_unpaired([0, 1], [0, 1]) == (0, 6, 6)
    assert exact_paired([Fraction(1, 3), Fraction(-1, 3)]) == (0, 4, 4)
    # Decimal-like thirds are compared as exact rationals, including tied tails.
    assert exact_unpaired([Fraction(1, 3)] * 2, [Fraction(2, 3)] * 2) == (Fraction(1, 3), 6, 2)


def test_input_order_invariance_and_immutability(inputs):
    root = inputs['manifest_path'].parent
    before = {p: p.read_bytes() for p in root.iterdir()}
    result = stats(**inputs)
    assert all(p.read_bytes() == value for p, value in before.items())
    entries = [r['result_json'] for r in csv.DictReader(inputs['manifest_path'].open())]
    write_manifest(inputs['manifest_path'], reversed(entries))
    write_samples(inputs['samples_path'], list(reversed(read_samples(inputs['samples_path']))))
    specification(inputs, lambda r: r['contrasts'].reverse())
    for name in entries:
        path = root / name
        value = json.loads(path.read_text())
        path.write_text(json.dumps(dict(reversed(list(value.items())))))
    changed = stats(**inputs)
    left, right = result.model_dump(), changed.model_dump()
    for key in ('provenance', 'input_manifest_hash', 'sample_metadata_hash'):
        left.pop(key); right.pop(key)
    assert left == right
    assert result.input_manifest_hash != changed.input_manifest_hash
    assert result.sample_metadata_hash != changed.sample_metadata_hash


def test_paired_order_invariance(tmp_path):
    inputs = dataset(tmp_path, paired=True)
    before = stats(**inputs)
    write_samples(inputs['samples_path'], list(reversed(read_samples(inputs['samples_path']))))
    after = stats(**inputs)
    assert before.contrasts == after.contrasts


@pytest.mark.parametrize('command', ['summarize', 'stats'])
def test_offline_installed_cli_and_atomic_output(inputs, tmp_path, command):
    output = tmp_path / command
    args = [sys.executable, '-m', 'peanalyzer', command, '--manifest', str(inputs['manifest_path']),
            '--samples', str(inputs['samples_path']), '--output', str(output)]
    if command == 'stats':
        args += ['--contrasts', str(inputs['contrasts_path'])]
    result = subprocess.run(args, capture_output=True, text=True, env=os.environ | {'PATH': '/nonexistent'}, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert set(p.name for p in output.iterdir()) == {'result.json', 'observations.tsv', 'group_summaries.tsv', 'contrasts.tsv'}
    parsed = StatisticsResult.model_validate_json((output / 'result.json').read_text())
    assert len(parsed.observations) == 144
    assert subprocess.run(args, capture_output=True).returncode == 2
    mutate(inputs, lambda r: r.update(schema_version=99))
    args[args.index('--output') + 1] = str(tmp_path / 'invalid')
    failed = subprocess.run(args, capture_output=True, text=True)
    assert failed.returncode == 2 and 'unsupported' in failed.stderr
    assert not (tmp_path / 'invalid').exists()


def test_publication_failure_cleans_stage(inputs, tmp_path, monkeypatch):
    result = summary(inputs)
    original = Path.write_text
    def fail(path, *args, **kwargs):
        if path.name == 'result.json':
            raise OSError('synthetic write failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', fail)
    with pytest.raises(OSError):
        publish(result, tmp_path / 'out')
    assert not list(tmp_path.glob('.out*')) and not (tmp_path / 'out').exists()


def test_schemas_and_strict_output_contract(inputs):
    resource = files('peanalyzer').joinpath('statistics_resources')
    assert json.loads(resource.joinpath('result.schema.json').read_text()) == StatisticsResult.model_json_schema()
    assert json.loads(resource.joinpath('contrasts.schema.json').read_text()) == ContrastSpecification.model_json_schema()
    raw = stats(**inputs).model_dump()
    raw['contrasts'][0]['p_value'] = 0.0
    with pytest.raises(ValidationError):
        StatisticsResult.model_validate(raw)


@pytest.mark.parametrize('path', [
    'm4/m31/result.json', 'm41/nonexact_only/result.json', 'm41/routing_blocked/result.json',
    'm42/actual/insertion_long/result.json', 'm422/actual/fixed/result.json',
    'm422/actual/copy2_1_all/result.json', 'm422/actual/copy_independence/production/result.json',
])
def test_existing_qualified_m4_documents_remain_unchanged(tmp_path, path):
    source = ROOT / 'docs/validation' / path
    before = source.read_bytes()
    raw = json.loads(before)
    inputs = dataset(tmp_path, replicates=1, targets=('T1',))
    row = read_samples(inputs['samples_path'])[0] | dict(barcode_id=raw['sample_id'])
    write_samples(inputs['samples_path'], [row])
    write_manifest(inputs['manifest_path'], [str(source)])
    result = summary(inputs)
    for name, metric in raw['target_metrics'].items():
        observation = next(r for r in result.observations if r.metric_name == name and r.copy_name is None)
        assert (observation.status, observation.numerator, observation.denominator, observation.reason_codes) == (
            metric['status'], metric['numerator'], metric['denominator'], metric['reason_codes'])
    assert source.read_bytes() == before


def test_zero_denominator_nonreportable_family_retained(inputs):
    def change(raw):
        row = raw['derived_metrics']['target']['policy1']
        row.update(status='NOT_ASSESSABLE', numerator=None, denominator=None,
                   wt_family=0, pe_family=0, excluded=row['classification_input_reads'], reason_codes=['ZERO_FAMILY_DENOMINATOR'])
    mutate(inputs, change)
    result = stats(**inputs)
    row = next(r for r in result.observations if r.sample_name == 'A001' and r.target_name == 'T1'
               and r.metric_name == 'total_pe_family' and r.policy_id == 'policy1')
    assert row.status == 'NOT_ASSESSABLE' and row.fraction is row.numerator is row.denominator is None
    assert row.reason_codes == ['ZERO_FAMILY_DENOMINATOR']


def test_nonreportable_invalid_policy_preserves_diagnostic(inputs):
    def change(raw):
        row = raw['derived_metrics']['target'].pop('policy1')
        row.update(policy_id='invalid-policy', policy={'policy_id': 'invalid-policy', 'max_extra_indel_events': 1},
                   status='BLOCKED', numerator=None, denominator=None, reason_codes=['UNSUPPORTED_TOLERANCE_POLICY'])
        raw['derived_metrics']['target']['invalid-policy'] = row
    mutate(inputs, change)
    row = next(r for r in summary(inputs).observations if r.policy_id == 'invalid-policy')
    assert row.status == 'BLOCKED' and row.policy_definition['max_extra_indel_events'] == 1


def test_whitespace_condition_is_invalid(inputs):
    specification(inputs, lambda r: r['contrasts'][0]['group_a'].update(editor='   '))
    with pytest.raises(AggregationError):
        stats(**inputs)


@pytest.mark.parametrize('paired', [False, True])
def test_two_biological_units_are_sufficient(tmp_path, paired):
    c = native(stats(**dataset(tmp_path, paired=paired, replicates=2)))
    assert c.status == 'REPORTABLE' and c.permutation_count == (4 if paired else 6)


def test_equal_fractions_do_not_collapse_distinct_policies(inputs):
    result = summary(inputs)
    policies = [g for g in result.group_summaries if g.target_name == 'T1' and g.condition.treatment == 'A'
                and g.metric_name == 'total_pe_family']
    assert {g.policy_id for g in policies} == {'policy0', 'policy1'}
    assert policies[0].source_fractions == policies[1].source_fractions


@pytest.mark.parametrize('contents', ['', 'result_json\n', 'result_json,extra\na.json,x\n', 'result_json\n\n'])
def test_invalid_manifest_rejected(inputs, contents):
    inputs['manifest_path'].write_text(contents)
    with pytest.raises(AggregationError):
        summary(inputs)


def test_publication_failure_during_tsv_cleans_stage(inputs, tmp_path, monkeypatch):
    result = summary(inputs)
    def fail(*args, **kwargs):
        raise OSError('synthetic TSV write failure')
    monkeypatch.setattr(csv.DictWriter, 'writerow', fail)
    with pytest.raises(OSError):
        publish(result, tmp_path / 'out')
    assert not list(tmp_path.glob('.out*')) and not (tmp_path / 'out').exists()


def test_boolean_schema_version_is_not_an_integer_contract(inputs):
    raw = stats(**inputs).model_dump()
    raw['schema_version'] = True
    with pytest.raises(ValidationError, match='integer'):
        StatisticsResult.model_validate(raw)
    raw = yaml.safe_load(inputs['contrasts_path'].read_text())
    raw['schema_version'] = True
    with pytest.raises(ValidationError, match='integer'):
        ContrastSpecification.model_validate(raw)


def test_family_classification_cannot_exceed_source_population(inputs):
    def attack(raw):
        evidence = raw['product_evidence']['target']
        evidence['classification_input_reads'] += 5
        evidence['products'][0]['count'] += 5
        for row in raw['derived_metrics']['target'].values():
            row['classification_input_reads'] += 5
            row['wt_family'] += 5
            row['denominator'] += 5
        from peanalyzer.metrics import MetricResult
        MetricResult.model_validate(raw)
    mutate(inputs, attack)
    with pytest.raises(AggregationError, match='classification exceeds source population'):
        stats(**inputs)


@pytest.mark.parametrize('field', ['schema_version', 'statistics_contract_version'])
def test_result_requires_explicit_version_fields(inputs, field):
    raw = stats(**inputs).model_dump()
    raw.pop(field)
    with pytest.raises(ValidationError):
        StatisticsResult.model_validate(raw)


def test_typed_contrast_api_replaces_specification_provenance(inputs):
    from peanalyzer.statistics import calculate_contrasts
    original = stats(**inputs)
    spec = yaml.safe_load(inputs['contrasts_path'].read_text())
    spec['contrasts'][0]['contrast_id'] = 'revised-native'
    revised = calculate_contrasts(original, ContrastSpecification.model_validate(spec))
    assert revised.provenance.contrast_specification_hash != original.provenance.contrast_specification_hash
    assert revised.provenance.contrast_specification_path is None
    assert revised.provenance.invocation_parameters['contrast_specification_hash_basis'] == 'normalized_typed_specification'
    assert original.provenance.invocation_parameters['contrast_specification_hash_basis'] == 'source_file_bytes'
    assert original.provenance.contrast_specification_path is not None
