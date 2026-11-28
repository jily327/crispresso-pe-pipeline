"""Reconcile current integer measurements with immutable, identified forward artifacts."""
import argparse
from collections import Counter
import csv
import gzip
from itertools import zip_longest
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree

from peanalyzer.metrics.models import CopyMetrics, TargetMetrics


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASELINE = '25ce3a990ccef9e2daa8937f0c09023498ef4cb5'


def load(file):
    return json.loads(file.read_bytes())


def frozen(file):
    data = subprocess.check_output(['git','show',f'{BASELINE}:docs/validation/{file}'], cwd=REPO)
    return json.loads(data)


def datasets():
    datasets = {}
    for name in ['AmpSeq', 'Azenta']:
        path = 'readthrough/' + name
        summary = frozen(path + '-results.json')
        route = frozen(path + '-routing.json')
        metrics = frozen(path + '-metrics.json')
        oracle = frozen(path + '-oracle.json')
        parity = frozen('readthrough-singlecopy/' + name + '-parity.json')
        assert summary['workflow_manifest_sha256'] == parity['workflow_manifest_sha256']
        assert set(summary['samples']) == set(metrics) == set(oracle['sample_counts']) == set(parity['samples'])
        totals = Counter()
        for sample, row in summary['samples'].items():
            targets = TargetMetrics.model_validate(metrics[sample]['target_metrics'])
            exact, native = targets.total_precise_pe, targets.target_crispresso_native_pe
            expected = oracle['exact_haplotypes'][sample]
            routed = route['samples'][sample]['after']
            counts = [CopyMetrics.model_validate(c) for c in metrics[sample]['copies'].values()]
            pairs = row['input_pairs']
            assert pairs == oracle['sample_counts'][sample] == parity['samples'][sample]['pairs'] == sum(routed.values())
            assert pairs == expected['exact_WT'] + expected['exact_PE'] + expected['other_or_unassessable']
            assert exact.denominator == row['precise_denominator'] == expected['exact_WT'] + expected['exact_PE']
            assert exact.numerator == row['exact_pe'] == expected['exact_PE']
            assert (native.numerator, native.denominator) == (row['native_numerator'], row['native_denominator'])
            assert all(c.precise.population_input_reads == routed[c.copy_id] for c in counts)
            assert parity['samples'][sample]['metric_result_sha256'] == row['result_sha256']
            totals.update(pairs=pairs, exact_PE=exact.numerator, exact_WT=expected['exact_WT'],
                native_PE=native.numerator, native_aligned=native.denominator, **routed)
        datasets[name] = dict(sample_count=len(metrics), archived_totals=dict(totals),
            original_workflow_sha256=summary['workflow_manifest_sha256'],
            current_validation='archived metric structures, sample IDs, counts and cross-file hashes',
            original_raw_reexecuted=False)
    return datasets


def numerator_records(obj):
    rows = dict(obj['target_metrics'])
    for name, group in obj['copies'].items():
        for metric in ['precise','native']:
            rows[name + '/' + metric] = group[metric]
    return {name:{k:row[k] for k in ['status','numerator','denominator','population_input_reads']}
            for name,row in sorted(rows.items())}


def backend(runs):
    results = {}
    for name in ['m3','m31']:
        path = runs/name/'m4'
        current = load(path/'result.json')
        archived = frozen('m4/'+name+'/result.json')
        counts = numerator_records(current)
        assert counts == numerator_records(archived), name
        runs_info = [load(p)['running_info'] for p in path.rglob('CRISPResso2_info.json')]
        assert len(runs_info) == (2 if name=='m3' else 4)
        assert all(i['version']=='2.3.4' and i['end_time_string'] for i in runs_info)
        assert load(path/'execution_failures.json') == {}
        results[name] = dict(measurements=counts, backend_version='2.3.4', completed_backend_runs=len(runs_info),
            runtime_digest=current['provenance']['runtime_digest'])
    return results


def archive_ledger():
    source = subprocess.check_output(['git','show',f'{BASELINE}:docs/validation/m31/qualification/routing_ledger.jsonl'],cwd=REPO)
    rows=[json.loads(line) for line in source.splitlines()]
    return {r['read_id']:(r['category'],r['assigned_copy'] or '') for r in rows}


def synthetic(work):
    ledger = archive_ledger()
    counts = Counter()
    with (work/'baseline-synthetic.csv').open() as base, (work/'candidate-synthetic.csv').open() as current:
        for a,b in zip_longest(csv.DictReader(base),csv.DictReader(current)):
            assert a == b and a
            counts[a['fixture']] += 1
            if a['fixture']=='m31':
                assert ledger.pop(a['read_id']) == (a['category'],a['assigned_copy'])
    assert counts=={'m3':350,'m31':125} and not ledger
    return dict(exact_classifications_identical=dict(counts), routing_ids_compared=125,
        routing_id_category_or_copy_differences=0)


def alsw(work):
    result = {}
    with (gzip.open(work/'baseline.csv.gz','rt') as base, gzip.open(work/'candidate.csv.gz','rt') as current,
          gzip.open(work/'oracle.csv.gz','rt') as oracle):
        for a,b,c in zip_longest(csv.DictReader(base),csv.DictReader(current),csv.DictReader(oracle)):
            assert a and b and c
            assert (a['panel'],a['pairs_seen']) == (b['panel'],b['pairs_seen']) == (c['panel'],c['pairs_seen'])
            row=result.setdefault(a['panel'],dict(pairs=0,product_calls=Counter(),product_changes=0,
                exclusion_reason_changes=0,exclusion_reason_transitions=Counter(),oracle_discordances=0))
            row['pairs'] += 1
            row['product_calls'][b['product']] += 1
            row['product_changes'] += int(a['product']!=b['product'])
            if a['reason'] != b['reason']:
                row['exclusion_reason_changes'] += 1
                row['exclusion_reason_transitions'][f"{a['reason'] or '(none)'} to {b['reason'] or '(none)'}"] += 1
            row['oracle_discordances'] += int(c['product']!=b['product'])
    assert len(result)==2 and all(r['pairs']==53896 and r['product_changes']==r['oracle_discordances']==0 for r in result.values())
    return result


def main():
    if not __debug__:
        raise RuntimeError('Assertions are required for qualification')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('work',type=Path)
    p.add_argument('runs',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--candidate',required=True,help='Full tested candidate commit')
    args=p.parse_args()
    xml=ElementTree.parse(args.work/'readthrough-tests.xml')
    assert not any(xml.findall('.//'+tag) for tag in ('failure','error','skipped'))
    readthrough_cases=len(xml.findall('.//testcase'))
    assert readthrough_cases==149
    evidence=dict(immutable_forward_test_cases_passed=readthrough_cases, baseline_commit=BASELINE, candidate_commit=args.candidate,
        original_datasets=datasets(), archived_target_csv=frozen('readthrough/input-hashes.json')['targets_ALSW.csv'],
        forward_synthetic=synthetic(args.work), genuine_forward_backend=backend(args.runs),
        uploaded_ALSW_panel_hypotheses=alsw(args.work),
        uploaded_source_sha256={k:v for k,v in load(HERE.parent/'epsps-real/input-sha256.json').items()
            if k.startswith('ALSW')},
        historical_FASTQ_sha256={k:v['sha256'] for k,v in frozen('readthrough/input-hashes.json').items()
            if k!='targets_ALSW.csv'})
    # Long-term identity uses the original file name, byte length and hash.
    evidence['archived_target_csv']['path']=Path(evidence['archived_target_csv']['path']).name
    with args.output.open('x') as out:
        json.dump(evidence,out,indent=2,sort_keys=True)
        out.write('\n')


if __name__=='__main__':
    main()
