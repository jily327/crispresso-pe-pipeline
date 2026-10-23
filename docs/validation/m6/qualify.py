"""Qualify deterministic source/wheel M6 reports from the same committed fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from peanalyzer.reporting import build_report_spec, generate_report, load_result
from peanalyzer.statistical_models import StatisticsResult


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def benchmark(fixture):
    """Expand stored synthetic M5 records; the renderer still receives completed values."""
    import copy
    source = fixture.model_dump(mode='json')
    rows, summaries = [], []
    for target in ('T1', 'T2', 'T3', 'T4'):
        template_rows = [r for r in source['observations'] if r['target_name'] == 'T1']
        template_groups = [r for r in source['group_summaries'] if r['target_name'] == 'T1']
        for group in template_groups:
            group = copy.deepcopy(group)
            group['target_name'] = target
            treatment = group['condition']['treatment']
            template = next(r for r in template_rows if r['sample_name'] == treatment+'001' and r['metric_name'] == group['metric_name'] and r['policy_id'] == group['policy_id'] and r['copy_name'] == group['copy_name'])
            assessment = copy.deepcopy(group['sample_assessments'][0])
            group.update(expected_sample_count=50, reportable_count=50, expected_sample_ids=[], reportable_sample_ids=[], sample_assessments=[], source_fractions=[])
            for i in range(50):
                name = treatment + f'{i+1:03}'
                row = copy.deepcopy(template)
                row.update(target_name=target, sample_name=name, sample_id='barcode-'+name, biological_replicate=str(i+1))
                rows.append(row)
                group['expected_sample_ids'].append(name)
                group['reportable_sample_ids'].append(name)
                group['sample_assessments'].append(assessment | dict(sample_name=name, biological_replicate=str(i+1)))
                group['source_fractions'].append(dict(sample_name=name, numerator=row['numerator'], denominator=row['denominator'], fraction=row['fraction']))
            for field in ('mean_biological_sample_fraction', 'median_biological_sample_fraction', 'minimum_biological_sample_fraction', 'maximum_biological_sample_fraction', 'pooled_read_fraction'):
                group[field] = template['fraction']
            summaries.append(group)
    source.update(observations=rows, group_summaries=summaries, contrasts=[], multiple_testing_families=[])
    return StatisticsResult.model_validate(source)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    summary = {}
    for name in ('unpaired', 'paired'):
        source = args.fixtures / (name + '.json')
        result = load_result(source.read_bytes())
        spec = build_report_spec(result)
        write(args.output / (name+'-spec.json'), spec)
        manifest = generate_report(result_path=source, output=args.output / name)
        for artifact in manifest.artifacts:
            assert hashlib.sha256((args.output / name / artifact.path).read_bytes()).hexdigest() == artifact.sha256
        summary[name] = dict(spec_sha256=hashlib.sha256((args.output / (name+'-spec.json')).read_bytes()).hexdigest(),
                             artifacts=tree(args.output / name))
    result = benchmark(load_result((args.fixtures / 'unpaired.json').read_bytes()))
    source = args.output / 'benchmark-input.json'
    write(source, result.model_dump(mode='json'))
    start = time.monotonic()
    generate_report(result_path=source, output=args.output / 'benchmark-report')
    elapsed = time.monotonic() - start
    write(args.output / 'benchmark.json', dict(biological_samples=100, targets=4, observations=len(result.observations),
        group_summaries=len(result.group_summaries), elapsed_seconds=round(elapsed, 3), figures=len(list((args.output / 'benchmark-report/figures').glob('*.svg')))))
    write(args.output / 'qualification.json', summary)
    if args.compare:
        other = json.loads((args.compare / 'qualification.json').read_text())
        assert summary == other
        write(args.output / 'source-wheel-byte-parity.json', dict(status='PASS', ignored_fields=[],
            fixtures=['unpaired', 'paired'], report_specs_equal=True, every_artifact_byte_identical=True, qualification=summary))
    print(json.dumps(dict(status='PASS', benchmark_seconds=round(elapsed,3), observations=len(result.observations))))


if __name__ == '__main__':
    main()
