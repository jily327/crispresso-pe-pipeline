"""Independent oracle check of a completed PE workspace against designed truth.

Usage: python verify_pe_workspace.py WORKSPACE TRUTH_JSON [EVIDENCE_JSON]
Imports nothing from PEAnalyzer. Native PE is recomputed from raw CRISPResso files
with this script's own parser; exact PE is compared with the designed molecules.
"""
import csv
import io
import itertools
import json
import sys
import zipfile
from fractions import Fraction
from pathlib import Path

root, truth = Path(sys.argv[1]), json.load(open(sys.argv[2]))
checks = []


def check(name, actual, expected):
    ok = actual == expected
    checks.append(dict(check=name, ok=ok, actual=actual, expected=expected))
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'\n     actual={actual!r}\n     expected={expected!r}'))


def load(path):
    return json.load(open(root / path))


# A. Demultiplexing accounting -------------------------------------------------
demux = load('demux/01_demux_QC/demux_summary.json')
check('demux.total_input_pairs', demux['total_input_read_pairs'], truth['total_pool_pairs'])
check('demux.per_sample_assigned', demux['per_sample_assigned_read_pairs'], truth['expected_prepared_pairs'])
check('demux.unexpected_valid_pairs_never_assigned', demux['unexpected_valid_barcode_pair'], truth['unexpected_valid_pairs'])
check('demux.no_barcode_pairs', demux['no_barcode_match'], truth['no_barcode_pairs'])

# B/C. Per-sample metrics ------------------------------------------------------
target = truth['design']['target_name']
independent = {}
for barcode, counts in truth['counts'].items():
    result = load(f'metrics/{barcode}/{target}/result.json')
    exact = result['target_metrics']['total_precise_pe']
    native = result['target_metrics']['target_crispresso_native_pe']
    want = truth['expected_exact'][barcode]
    if want['denominator']:
        check(f'{barcode}.exact_pe.status', exact['status'], 'REPORTABLE')
        check(f'{barcode}.exact_pe.counts', [exact['numerator'], exact['denominator']], [want['numerator'], want['denominator']])
    else:
        check(f'{barcode}.exact_pe.zero_denominator_not_reported_as_zero',
              [exact['status'], exact['numerator'], exact['denominator']], ['NOT_ASSESSABLE', None, None])
    check(f'{barcode}.population_input_reads', exact['population_input_reads'], sum(counts.values()))
    # Independent CRISPResso parse (anchor run on all prepared pairs).
    child = root / f'metrics/{barcode}/{target}/comparator/{truth["design"]["copy_name"]}/output/CRISPResso_on_unrouted'
    mapping = next(csv.DictReader(open(child / 'CRISPResso_mapping_statistics.txt'), delimiter='\t'))
    with zipfile.ZipFile(child / 'Alleles_frequency_table.zip') as archive:
        rows = list(csv.DictReader(io.TextIOWrapper(archive.open(archive.namelist()[0])), delimiter='\t'))
    by_ref = {}
    for row in rows:
        by_ref[row['Reference_Name']] = by_ref.get(row['Reference_Name'], 0) + int(row['#Reads'])
    quant = {r['Amplicon']: r for r in csv.DictReader(open(child / 'CRISPResso_quantification_of_editing_frequency.txt'), delimiter='\t')}
    aligned = int(mapping['READS ALIGNED'])
    pe_assigned = by_ref.get('Prime-edited', 0)
    check(f'{barcode}.native.counts_vs_independent_crispresso_parse', [native['numerator'], native['denominator']], [pe_assigned, aligned])
    # Designed expectation of what CRISPResso should do with each molecule class.
    designed_pe_ref = counts['exact_pe'] + counts['pe_plus_extra'] + counts['wrong_substitution']
    designed_aligned = sum(counts.values()) - counts['unrelated']
    check(f'{barcode}.native.counts_vs_designed_molecules', [native['numerator'], native['denominator']], [designed_pe_ref, designed_aligned])
    check(f'{barcode}.native.ambiguous_equals_designed_partial_pe', native['ambiguous_aligned_reads'], counts['partial_pe'])
    # Modified% conflation probe: CRISPResso "Modified" counts across references.
    modified_total = sum(int(q['Modified']) for q in quant.values())
    modified_fraction = Fraction(modified_total, aligned) if aligned else None
    stored_fraction = Fraction(native['numerator'], native['denominator']) if native['denominator'] else None
    independent[barcode] = dict(exact=[want['numerator'], want['denominator']], native=[pe_assigned, aligned],
                                crispresso_modified_reads_all_refs=modified_total,
                                crispresso_reference_modified_pct=quant['Reference']['Modified%'],
                                crispresso_pe_reference_modified_pct=quant['Prime-edited']['Modified%'],
                                allele_reads_by_reference=by_ref)
    if modified_fraction is not None and modified_fraction != stored_fraction:
        check(f'{barcode}.native_is_not_modified_pct', stored_fraction != modified_fraction, True)

# D. Statistics: biological samples are the units ------------------------------
stats = load('statistics/result.json')
meta = truth['meta']
obs = {(o['sample_id'], o['metric_name']): o for o in stats['observations']}
for barcode in truth['counts']:
    for metric, key in (('total_precise_pe', 'exact'), ('target_crispresso_native_pe', 'native')):
        o = obs[barcode, metric]
        n, d = independent[barcode][key]
        if d:
            check(f'{barcode}.stats_observation.{metric}', [o['status'], o['numerator'], o['denominator'], o['fraction']], ['REPORTABLE', n, d, n / d])
        else:
            check(f'{barcode}.stats_observation.{metric}.null_not_zero', [o['status'], o['numerator'], o['denominator'], o['fraction']], ['NOT_ASSESSABLE', None, None, None])
        check(f'{barcode}.stats_observation.{metric}.sample_name', o['sample_name'], meta[barcode]['sample_name'])


def group_values(metric, treatment):
    values = []
    for barcode, m in sorted(meta.items()):
        n, d = independent[barcode]['exact' if metric == 'total_precise_pe' else 'native']
        if m['treatment'] == treatment and d:
            values.append(Fraction(n, d))
    return values


for g in stats['group_summaries']:
    if g['copy_name'] is not None:
        continue
    values = group_values(g['metric_name'], g['condition']['treatment'])
    expected_n = sum(m['treatment'] == g['condition']['treatment'] for m in meta.values())
    check(f"group.{g['metric_name']}.{g['condition']['treatment']}.n_is_biological_samples",
          [g['expected_sample_count'], g['reportable_count']], [expected_n, len(values)])
    mean = float(sum(values) / len(values)) if values else None
    check(f"group.{g['metric_name']}.{g['condition']['treatment']}.unweighted_mean", g['mean_biological_sample_fraction'], mean)


def exact_unpaired(a, b):
    observed = sum(b) / len(b) - sum(a) / len(a)
    pool = a + b
    extreme = total = 0
    for chosen in itertools.combinations(range(len(pool)), len(a)):
        ga = [pool[i] for i in chosen]
        gb = [pool[i] for i in range(len(pool)) if i not in chosen]
        total += 1
        extreme += abs(sum(gb) / len(gb) - sum(ga) / len(ga)) >= abs(observed)
    return observed, Fraction(extreme, total), total


pvals = {}
for c in stats['contrasts']:
    a = group_values(c['metric_name'], c['group_a']['treatment'])
    b = group_values(c['metric_name'], c['group_b']['treatment'])
    if len(a) >= 2 and len(b) >= 2:
        effect, p, total = exact_unpaired(a, b)
        check(f"contrast.{c['contrast_id']}.effect_p_space", [c['status'], c['difference_in_biological_sample_fraction'], c['p_value'], c['permutation_space_size']],
              ['REPORTABLE', float(effect), float(p), total])
        pvals[c['contrast_id']] = p
    else:
        check(f"contrast.{c['contrast_id']}.insufficient_units_not_tested", [c['status'], c['p_value'], c['q_value']], ['NOT_ASSESSABLE', None, None])
# Independent Benjamini-Hochberg within the single declared family.
ordered = sorted(pvals.items(), key=lambda kv: kv[1])
m = len(ordered)
q = {}
running = Fraction(1)
for rank in range(m, 0, -1):
    name, p = ordered[rank - 1]
    running = min(running, p * m / rank)
    q[name] = running
for c in stats['contrasts']:
    if c['contrast_id'] in q:
        check(f"contrast.{c['contrast_id']}.bh_q", c['q_value'], float(q[c['contrast_id']]))

# E. Report tables carry the same stored values --------------------------------
with open(root / 'report/tables/observations.tsv') as handle:
    table = {(r['sample_id'], r['metric_name']): r for r in csv.DictReader(handle, delimiter='\t')}
for (barcode, metric), o in obs.items():
    row = table[barcode, metric]
    want = ['' if o[k] is None else str(o[k]) for k in ('numerator', 'denominator', 'fraction')]
    check(f'report_table.{barcode}.{metric}', [row['numerator'], row['denominator'], row['fraction']], want)
check('report.source_copy_is_byte_identical', (root / 'report/source/result.json').read_bytes() == (root / 'statistics/result.json').read_bytes(), True)

summary = dict(workspace=str(root.name), passed=sum(c['ok'] for c in checks), failed=sum(not c['ok'] for c in checks),
               independent_values=independent, checks=checks)
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print(f"\n{summary['passed']} passed, {summary['failed']} failed")
sys.exit(1 if summary['failed'] else 0)
