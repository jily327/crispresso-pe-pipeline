"""M5.1 rejects missing whole results, preserving metric-level attrition."""
import csv
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from peanalyzer.aggregation import AggregationError, summarize
from peanalyzer.statistics import stats
from m5_fixtures import dataset, change_record, read_samples, write_json, write_manifest, write_samples

ROOT = Path(__file__).resolve().parents[1]
CODE = 'PARTIAL_SAMPLE_TARGET_COVERAGE'


def entries(inputs):
    with inputs['manifest_path'].open(newline='') as handle:
        return [r['result_json'] for r in csv.DictReader(handle)]


def remove_results(inputs, removed):
    write_manifest(inputs['manifest_path'], [p for p in entries(inputs) if p not in removed])


def invoke(command, inputs, **kwargs):
    args = inputs if command == 'stats' else {k:v for k,v in inputs.items() if k != 'contrasts_path'}
    return (stats if command == 'stats' else summarize)(**args, **kwargs)


def scientific(result):
    raw = result.model_dump(mode='json')
    return {k:v for k,v in raw.items() if k not in ('provenance','input_manifest_hash','sample_metadata_hash')}


def scientific_sha(result):
    return hashlib.sha256(json.dumps(scientific(result), sort_keys=True, separators=(',',':')).encode()).hexdigest()


def diagnostic(missing):
    return CODE + ': ' + '; '.join(f'sample {sample} is missing targets: {", ".join(sorted(targets))}'
                                   for sample,targets in sorted(missing.items()))


@pytest.mark.parametrize('command', ['summarize','stats'])
@pytest.mark.parametrize('missing', ['A003-T2.json','B002-T1.json'])
@pytest.mark.parametrize('shuffle', [False,True])
def test_partial_target_rejects_before_summaries_or_publication(tmp_path, monkeypatch, command, missing, shuffle):
    import peanalyzer.aggregation as aggregation
    inputs = dataset(tmp_path/'inputs')
    remove_results(inputs, {missing})
    if shuffle:
        paths = entries(inputs); random.Random(51).shuffle(paths)
        write_manifest(inputs['manifest_path'],paths)
    sample,target = missing.removesuffix('.json').split('-')
    def forbidden(*args):
        pytest.fail('partial input reached authoritative group construction')
    monkeypatch.setattr(aggregation,'summarize_groups',forbidden)
    output = tmp_path/'output'
    with pytest.raises(AggregationError) as error:
        invoke(command,inputs,output=output)
    assert str(error.value) == diagnostic({'barcode-'+sample:[target]})
    assert not output.exists() and not list(tmp_path.glob('.output*'))


@pytest.mark.parametrize('command', ['summarize','stats'])
def test_multiple_missing_targets_are_sorted(tmp_path, command):
    inputs = dataset(tmp_path,targets=('T3','T1','T2'))
    remove_results(inputs, {'A003-T3.json','A003-T2.json'})
    with pytest.raises(AggregationError) as error:
        invoke(command,inputs)
    assert str(error.value) == diagnostic({'barcode-A003':['T2','T3']})


@pytest.mark.parametrize('owner', ['A001','B003'])
def test_target_unique_to_one_sample_is_not_selective_applicability(tmp_path, owner):
    inputs = dataset(tmp_path)
    remove_results(inputs,{p for p in entries(inputs) if p.endswith('-T2.json') and not p.startswith(owner+'-')})
    with pytest.raises(AggregationError) as error:
        invoke('summarize',inputs)
    expected = {'barcode-'+s:['T2'] for s in ('A001','A002','A003','B001','B002','B003') if s != owner}
    assert str(error.value) == diagnostic(expected)


@pytest.mark.parametrize('command', ['summarize','stats'])
@pytest.mark.parametrize('kind', ['added_unused','remove_all_A003'])
def test_zero_results_remain_unused_metadata(tmp_path, command, kind):
    inputs = dataset(tmp_path)
    if kind == 'added_unused':
        rows = read_samples(inputs['samples_path'])
        rows.append(rows[0] | dict(sample_name='unused',barcode_id='barcode-unused',biological_replicate='unused'))
        write_samples(inputs['samples_path'],rows)
        expected, count = ['unused'],144
    else:
        remove_results(inputs, {'A003-T1.json','A003-T2.json'})
        expected, count = ['A003'],120
    result = invoke(command,inputs)
    assert result.unused_metadata_sample_ids == expected
    assert len(result.observations) == count
    assert not {r.sample_name for r in result.observations}.intersection(expected)


@pytest.mark.parametrize('command', ['summarize','stats'])
@pytest.mark.parametrize('paired', [False,True])
def test_complete_fixture_matches_audited_parent(tmp_path, command, paired):
    result = invoke(command,dataset(tmp_path,paired=paired))
    baseline = json.loads((ROOT/'docs/validation/m51/before.json').read_text())
    expected = baseline['complete'][('paired' if paired else 'unpaired')+'_'+command]
    assert scientific_sha(result) == expected['scientific_sha256']
    assert len(result.observations) == 144 and len(result.group_summaries) == 48
    assert all(g.expected_sample_count == 3 for g in result.group_summaries)
    assert result.schema_version == 1 and result.statistics_contract_version == 'm5-v1'


@pytest.mark.parametrize('command', ['summarize','stats'])
def test_missing_policy_is_not_a_missing_result(tmp_path, command):
    inputs = dataset(tmp_path)
    path = tmp_path/'A003-T2.json'; raw = json.loads(path.read_text())
    raw['derived_metrics']['target'].pop('policy1'); write_json(path,raw)
    result = invoke(command,inputs)
    group = next(g for g in result.group_summaries if g.target_name=='T2' and g.condition.treatment=='A'
                 and g.metric_name=='total_pe_family' and g.policy_id=='policy1')
    assessment = next(s for s in group.sample_assessments if s.sample_name=='A003')
    assert (assessment.status,assessment.reason_codes)==('MISSING_METRIC',['METRIC_NOT_PRESENT'])
    assert group.expected_sample_count == 3 and group.missing_metric_count == 1
    assert len(result.observations) == 143


@pytest.mark.parametrize('command', ['summarize','stats'])
@pytest.mark.parametrize('status', ['BLOCKED','NOT_ASSESSABLE'])
def test_nonreportable_metric_still_covers_target(tmp_path, command, status):
    inputs = dataset(tmp_path); change_record(tmp_path/'A003-T2.json',status)
    result = invoke(command,inputs)
    row = next(r for r in result.observations if r.sample_id=='barcode-A003' and r.target_name=='T2'
               and r.metric_name=='target_crispresso_native_pe')
    assert row.status == status and row.numerator is row.denominator is row.fraction is None
    group = next(g for g in result.group_summaries if g.target_name=='T2' and g.condition.treatment=='A'
                 and g.metric_name==row.metric_name)
    assert group.expected_sample_count == 3 and group.reportable_count == 2
    assert len(result.observations) == 144


@pytest.mark.parametrize('command', ['summarize','stats'])
def test_complete_manifest_shuffle_keeps_science(tmp_path, command):
    inputs = dataset(tmp_path); before = invoke(command,inputs)
    paths = entries(inputs); random.Random(51).shuffle(paths); write_manifest(inputs['manifest_path'],paths)
    after = invoke(command,inputs)
    assert scientific(after) == scientific(before)
    assert after.input_manifest_hash != before.input_manifest_hash


def test_coverage_uses_barcode_join_after_metadata_names_are_swapped(tmp_path):
    inputs = dataset(tmp_path); remove_results(inputs,{'A003-T2.json'})
    rows = read_samples(inputs['samples_path'])
    for row in rows:
        if row['barcode_id']=='barcode-A003':row['sample_name']='B002'
        elif row['barcode_id']=='barcode-B002':row['sample_name']='A003'
    write_samples(inputs['samples_path'],rows)
    with pytest.raises(AggregationError) as error:
        invoke('summarize',inputs)
    assert str(error.value) == diagnostic({'barcode-A003':['T2']})


@pytest.mark.parametrize('command', ['summarize','stats'])
def test_installed_cli_rejects_partial_input_without_output(tmp_path, command):
    inputs = dataset(tmp_path/'inputs'); remove_results(inputs,{'A003-T2.json'})
    output = tmp_path/'output'
    args = [str(Path(sys.executable).parent/'peanalyzer'),command,'--manifest',str(inputs['manifest_path']),
            '--samples',str(inputs['samples_path']),'--output',str(output)]
    if command=='stats':args += ['--contrasts',str(inputs['contrasts_path'])]
    result = subprocess.run(args,cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode == 2
    assert diagnostic({'barcode-A003':['T2']}) in result.stderr
    assert not output.exists() and not list(tmp_path.glob('.output*'))
