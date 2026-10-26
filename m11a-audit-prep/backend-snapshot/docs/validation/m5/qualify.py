"""Reproduce offline M5 fixtures, independent oracles and the A-Q matrix."""
import argparse
import csv
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import time

import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tests'))
from m5_fixtures import (change_record, dataset, read_samples, result_document,
                        write_json, write_manifest, write_samples)
from peanalyzer.aggregation import AggregationError, publish, summarize
from peanalyzer.statistics import benjamini_hochberg, exact_paired, exact_unpaired, stats


def scientific(result):
    value = result.model_dump(mode='json')
    for key in ('provenance', 'input_manifest_hash', 'sample_metadata_hash'):
        value.pop(key)
    return value


def contrast(result, name='native'):
    return next(c for c in result.contrasts if c.contrast_id == name).model_dump(mode='json')


def paths(inputs):
    with inputs['manifest_path'].open(newline='') as handle:
        return [r['result_json'] for r in csv.DictReader(handle)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', type=Path, help='Compare scientific evidence with another qualification directory')
    args = parser.parse_args()
    out = args.output.absolute()
    if out.exists():
        raise ValueError('qualification output must be new')
    out.mkdir(parents=True)
    oracles = json.loads(Path(__file__).with_name('oracles.json').read_text())
    observed = {'unpaired': [], 'paired': [], 'bh': []}
    for row in oracles['unpaired']:
        effect, space, extreme = exact_unpaired(map(Fraction, row['a']), map(Fraction, row['b']))
        assert (effect, space, extreme) == (Fraction(row['effect']), row['space'], row['extreme'])
        observed['unpaired'].append(dict(effect=str(effect), space=space, extreme=extreme, p=str(Fraction(extreme, space))))
    for row in oracles['paired']:
        effect, space, extreme = exact_paired(map(Fraction, row['differences']))
        assert (effect, space, extreme) == (Fraction(row['effect']), row['space'], row['extreme'])
        observed['paired'].append(dict(effect=str(effect), space=space, extreme=extreme, p=str(Fraction(extreme, space))))
    for row in oracles['bh']:
        values = dict(zip(map(str, range(len(row['p']))), row['p']))
        actual = benjamini_hochberg(values)
        assert list(actual.values()) == row['q']
        observed['bh'].append(dict(p=row['p'], q=list(actual.values())))
    write_json(out / 'oracles-observed.json', observed)
    matrix = {}
    inputs = dataset(out / 'fixtures/unpaired')
    result = stats(**inputs)
    publish(result, out / 'unpaired')
    matrix['A'] = dict(case='unpaired 3 versus 3', contrast=contrast(result))
    for letter, name in [('I', 'native'), ('J', 'precise'), ('K', 'copy'), ('L', 'family')]:
        matrix[letter] = dict(case='distinct metric population: ' + name, contrast=contrast(result, name))
    matrix['O'] = dict(case='explicit BH families', families=[f.model_dump() for f in result.multiple_testing_families])
    paired_inputs = dataset(out / 'fixtures/paired', paired=True)
    paired = stats(**paired_inputs)
    publish(paired, out / 'paired')
    matrix['B'] = dict(case='paired three complete blocks', contrast=contrast(paired))
    attrition_inputs = dataset(out / 'fixtures/paired-attrition', paired=True, replicates=5)
    write_manifest(attrition_inputs['manifest_path'], [p for p in paths(attrition_inputs) if not p.startswith('B004-')])
    for target in ('T1', 'T2'):
        (attrition_inputs['manifest_path'].parent / f'B004-{target}.json').unlink()
    change_record(attrition_inputs['manifest_path'].parent / 'A005-T1.json', 'BLOCKED')
    attrition = stats(**attrition_inputs)
    publish(attrition, out / 'paired-attrition')
    matrix['F'] = dict(case='missing partner and blocked observation', contrast=contrast(attrition))
    with tempfile.TemporaryDirectory(prefix='m5-qualification-') as temporary:
        root = Path(temporary)
        unequal = dataset(root / 'unequal', replicates=2, targets=('T1',))
        for sample, n, d in [('A001', 1, 10), ('A002', 90, 100)]:
            write_json(unequal['manifest_path'].parent / f'{sample}-T1.json', result_document('barcode-' + sample, 'T1', n, d))
        descriptive = summarize(manifest_path=unequal['manifest_path'], samples_path=unequal['samples_path'])
        group = next(g for g in descriptive.group_summaries if g.metric_name == 'total_precise_pe' and g.condition.treatment == 'A')
        assert group.mean_biological_sample_fraction == 0.5 and group.pooled_read_fraction == 91/110
        matrix['C'] = dict(case='unequal depths', summary=group.model_dump(mode='json'))
        for letter, status in [('D', 'BLOCKED'), ('E', 'NOT_ASSESSABLE')]:
            mixed = dataset(root / letter)
            change_record(mixed['manifest_path'].parent / 'A001-T1.json', status)
            matrix[letter] = dict(case='one nonreportable sample: ' + status, contrast=contrast(stats(**mixed)))
        for letter, is_paired in [('G', False), ('H', True)]:
            small = dataset(root / letter, replicates=1, paired=is_paired)
            matrix[letter] = dict(case='insufficient biological units', contrast=contrast(stats(**small)))
        duplicate = dataset(root / 'duplicate')
        entries = paths(duplicate)
        raw = json.loads((duplicate['manifest_path'].parent / entries[0]).read_text())
        raw['analysis_id'] = 'conflicting-analysis'
        write_json(duplicate['manifest_path'].parent / 'duplicate.json', raw)
        write_manifest(duplicate['manifest_path'], entries + ['duplicate.json'])
        try:
            stats(**duplicate)
        except AggregationError as exc:
            assert 'duplicate analysis' in str(exc)
            matrix['M'] = dict(case='duplicate analysis rejection', rejected=True, diagnostic=str(exc))
        else:
            raise AssertionError('duplicate analysis was accepted')
        ordering = dataset(root / 'ordering')
        before = stats(**ordering)
        entries = paths(ordering)
        write_manifest(ordering['manifest_path'], reversed(entries))
        write_samples(ordering['samples_path'], list(reversed(read_samples(ordering['samples_path']))))
        spec = yaml.safe_load(ordering['contrasts_path'].read_text())
        spec['contrasts'].reverse(); spec['families'].reverse()
        ordering['contrasts_path'].write_text(yaml.safe_dump(spec))
        for name in entries:
            path = ordering['manifest_path'].parent / name
            value = json.loads(path.read_text())
            path.write_text(json.dumps(dict(reversed(list(value.items())))))
        after = stats(**ordering)
        assert scientific(before) == scientific(after)
        matrix['N'] = dict(case='manifest, metadata, contrasts and JSON key reordering', scientific_equal=True,
                           raw_input_hashes_preserved=False, reason='Raw hashes intentionally identify exact input bytes')
        mixed_bh = dataset(root / 'mixed-bh')
        for sample in ('A001', 'A002', 'A003'):
            change_record(mixed_bh['manifest_path'].parent / f'{sample}-T1.json', 'NOT_ASSESSABLE')
        mixed_result = stats(**mixed_bh)
        matrix['P'] = dict(case='mixed valid and nonreportable BH family', contrasts=[c.model_dump() for c in mixed_result.contrasts],
                           families=[f.model_dump() for f in mixed_result.multiple_testing_families])
        matrix['Q'] = dict(case='inclusive enumeration boundary', cases=[])
        for paired_flag, boundary in [(False, 20), (True, 8)]:
            boundary_inputs = dataset(root / ('paired-boundary' if paired_flag else 'unpaired-boundary'), paired=paired_flag)
            for cap in (boundary - 1, boundary):
                row = contrast(stats(**boundary_inputs, max_permutations=cap))
                assert row['status'] == ('REPORTABLE' if cap == boundary else 'NOT_ASSESSABLE')
                matrix['Q']['cases'].append(dict(max_permutations=cap, contrast=row))
        benchmark_inputs = dataset(root / 'benchmark', replicates=50, targets=('T1', 'T2', 'T3', 'T4'))
        started = time.perf_counter()
        benchmark = stats(**benchmark_inputs)
        elapsed = time.perf_counter() - started
        assert len(benchmark.observations) == 4800
        assert all(c.reason_codes == ['PERMUTATION_SPACE_TOO_LARGE'] for c in benchmark.contrasts)
        write_json(out / 'benchmark.json', dict(biological_samples=100, targets=4, copies_per_target=2,
            family_policies=2, m4_documents=400, observations=len(benchmark.observations),
            group_summaries=len(benchmark.group_summaries), contrasts=len(benchmark.contrasts),
            elapsed_seconds=elapsed, measurement='Collection, validation, summaries and cap handling; fixture generation excluded',
            backend_access=False, inferential_spaces_rejected_before_enumeration=True))
    assert set(matrix) == set('ABCDEFGHIJKLMNOPQ')
    write_json(out / 'qualification-matrix.json', matrix)
    if args.compare:
        for name in ('oracles-observed.json', 'qualification-matrix.json'):
            assert json.loads((out / name).read_text()) == json.loads((args.compare / name).read_text()), name
        from peanalyzer.statistical_models import StatisticsResult
        parity = {}
        for name in ('unpaired', 'paired', 'paired-attrition'):
            actual = StatisticsResult.model_validate_json((out / name / 'result.json').read_text())
            other = StatisticsResult.model_validate_json((args.compare / name / 'result.json').read_text())
            assert scientific(actual) == scientific(other)
            parity[name] = dict(scientific_equal=True, observations=len(actual.observations), contrasts=len(actual.contrasts),
                excluded_fields=['provenance', 'input_manifest_hash', 'sample_metadata_hash'])
        write_json(out / 'source-wheel-parity.json', parity)
    print(json.dumps(dict(matrix_cases=len(matrix), output=str(out), benchmark_seconds=elapsed), sort_keys=True))


if __name__ == '__main__':
    main()
