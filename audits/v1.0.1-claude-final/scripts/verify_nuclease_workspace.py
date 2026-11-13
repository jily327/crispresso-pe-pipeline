"""Independent check of a completed nuclease workspace.

Usage: python verify_nuclease_workspace.py WORKSPACE TRUTH_JSON EVIDENCE_JSON
Own parser of raw CRISPResso output; own class/bin arithmetic; own window derivation.
"""
import csv, io, json, sys, zipfile
from collections import Counter
from pathlib import Path
root, truth = Path(sys.argv[1]), json.load(open(sys.argv[2]))
checks = []
def check(name, actual, expected):
    ok = actual == expected
    checks.append(dict(check=name, ok=ok, actual=actual, expected=expected))
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'\n     actual={actual!r}\n     expected={expected!r}'))
target = truth['design']['target_name']
window_positions = sorted(p for a, b in truth['window_ranges'] for p in range(a, b + 1))
detail = {}
for barcode, counts in truth['counts'].items():
    base = root / f'metrics/{barcode}/{target}'
    result = json.load(open(base / 'result.json'))
    children = list(base.rglob('CRISPResso2_info.json'))
    check(f'{barcode}.single_backend_run', len(children), 1)
    child = children[0].parent
    info = json.load(open(children[0]))
    idx = info['results']['refs']['Reference']['include_idxs']
    idx = idx['value'] if isinstance(idx, dict) else idx
    check(f'{barcode}.backend_window_equals_independent_tigr_geometry', sorted(idx), window_positions)
    args = info['running_info']['args']
    args = args.get('value', args) if isinstance(args, dict) else args
    mapping = next(csv.DictReader(open(child / 'CRISPResso_mapping_statistics.txt'), delimiter='\t'))
    with zipfile.ZipFile(child / 'Alleles_frequency_table.zip') as z:
        rows = list(csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0])), delimiter='\t'))
    classes, flags, bins = Counter(), Counter(), Counter()
    for r in rows:
        n, i, dl, m = int(r['#Reads']), int(r['n_inserted']), int(r['n_deleted']), int(r['n_mutated'])
        if r['Reference_Name'] != 'Reference':
            classes[r['Reference_Name']] += n; continue
        cls = ('indel_plus_substitution' if m else 'indel_only') if (i or dl) else ('substitution_only' if m else 'unmodified')
        classes[cls] += n
        if i or dl:
            flags['indel'] += n; bins[str(i - dl)] += n      # one read counted once
        flags['insertion'] += n * (i > 0); flags['deletion'] += n * (dl > 0); flags['both'] += n * (i > 0 and dl > 0)
        flags['substitution'] += n * (m > 0); flags['any'] += n * (i > 0 or dl > 0 or m > 0)
    aligned = int(mapping['READS ALIGNED'])
    check(f'{barcode}.allele_rows_sum_to_aligned', sum(int(r['#Reads']) for r in rows), aligned)
    m = result['metrics']
    got = {k: [m[k]['numerator'], m[k]['denominator']] for k in m}
    want = dict(indel_fraction=[flags['indel'], aligned], unmodified_fraction=[classes['unmodified'], aligned],
                substitution_only_fraction=[classes['substitution_only'], aligned], indel_only_fraction=[classes['indel_only'], aligned],
                indel_plus_substitution_fraction=[classes['indel_plus_substitution'], aligned],
                substitution_containing_fraction=[flags['substitution'], aligned], insertion_containing_fraction=[flags['insertion'], aligned],
                deletion_containing_fraction=[flags['deletion'], aligned],
                insertion_and_deletion_containing_fraction=[flags['both'], aligned], any_modification_fraction=[flags['any'], aligned])
    check(f'{barcode}.all_ten_metrics_vs_independent_parse', got, want)
    check(f'{barcode}.exclusive_classes_partition_aligned',
          sum(result['class_counts'][k] for k in ('unmodified', 'substitution_only', 'indel_only', 'indel_plus_substitution', 'ambiguous', 'discarded')), aligned)
    check(f'{barcode}.net_size_bins_vs_independent_parse',
          {k: [v['numerator'], v['denominator']] for k, v in result['fraction_of_indel_reads_by_net_size'].items()},
          {k: [v, flags['indel']] for k, v in bins.items()})
    check(f'{barcode}.backend_input_equals_designed_pairs', result['backend_input_reads'], sum(counts.values()))
    check(f'{barcode}.aligned_equals_designed_minus_unrelated', aligned, sum(counts.values()) - counts.get('unrelated', 0))
    # Designed-class comparison (documents where the backend's calls differ from the physical molecule).
    designed = Counter()
    for label, n in counts.items():
        designed[truth['designed_class'].get(label, 'see_notes')] += n
    detail[barcode] = dict(designed_molecules=counts, designed_classes=dict(designed), backend_classes=dict(classes),
                           backend_flags=dict(flags), backend_bins=dict(bins), aligned=aligned,
                           resolved_args_subset={k: args.get(k) for k in ('quantification_window_coordinates', 'exclude_bp_from_left', 'exclude_bp_from_right', 'ignore_substitutions', 'ignore_insertions', 'ignore_deletions', 'discard_indel_reads', 'min_average_read_quality', 'min_single_bp_quality', 'default_min_aln_score', 'plot_window_size', 'use_legacy_insertion_quantification')})
stats = json.load(open(root / 'statistics/result.json'))
for o in stats['observations']:
    if o['metric_name'] == 'indel_fraction':
        r = json.load(open(root / f"metrics/{o['sample_id']}/{target}/result.json"))['metrics']['indel_fraction']
        check(f"{o['sample_id']}.stats_observation_equals_metric", [o['numerator'], o['denominator']], [r['numerator'], r['denominator']])
out = dict(workspace=root.name, window=truth['window'], passed=sum(c['ok'] for c in checks), failed=sum(not c['ok'] for c in checks), detail=detail, checks=checks)
Path(sys.argv[3]).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
print(f"\n{out['passed']} passed, {out['failed']} failed")
