"""Run genuine pinned Core and compare independently measured integer populations."""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

from order_control import recount as direct_order_recount
from peanalyzer.backend.intended_sites import run_core_sites
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.docker_runtime import IMAGE
from peanalyzer.schemas import reverse_complement


def target(copy, wt, pe):
    return SimpleNamespace(copy_name=copy, wt_sequence=wt, prime_edited_sequence=pe)


def mutate(seq, pos):
    return seq[:pos] + ('ACGT'.replace(seq[pos], '')[0]) + seq[pos+1:]


def synthetic(work):
    rng = random.Random(63041)
    wt = ''.join(rng.choices('ACGT', k=188))
    a, b = 81, 92
    peer = mutate(mutate(mutate(wt, 25), 149), 163)
    targets, truth = [], {}
    reads = []
    for name, wt in [('one', wt), ('two', peer)]:
        edited = mutate(mutate(wt, a), b)
        targets.append(target(name, wt, edited))
        variants = [
            (wt, 16), (mutate(wt, a), 7), (mutate(wt, b), 5), (edited, 3),
            (mutate(edited, b+31), 4),
            (wt[:a] + ('ACGT'.replace(wt[a], '').replace(edited[a], '')[0]) + wt[a+1:], 2),
            (wt[:b] + wt[b+1:], 2),
            (wt[:116] + 'A' + wt[116:], 2)]
        truth[name] = {'WT': 18, 'A_only': 7, 'B_only': 5, 'AB': 7,
                       'other_mixed': 4, 'unassessable': 0}
        for seq, count in variants:
            reads.extend([seq] * count)
    # Vary copy order within the cohort. Paired inputs here have normalized sequencing orientation.
    rng.shuffle(reads)
    r1, r2 = work/'synthetic.1.fq', work/'synthetic.2.fq'
    with r1.open('x') as left, r2.open('x') as right:
        for i, seq in enumerate(reads):
            for handle, mate, dna in ((left, 1, seq[:144]), (right, 2, reverse_complement(seq[-144:]))):
                handle.write(f'@truth{i}/{mate}\n{dna}\n+\n{"I" * len(dna)}\n')
    return targets, truth, r1, r2, len(reads)


def compare_real(report, oracle):
    assert [report[k] for k in ('input_pairs', 'preprocessed', 'aligned', 'unaligned', 'ambiguous')] == [
        oracle['raw_pairs'], oracle['merged'], oracle['aligned'], oracle['unaligned_after_merge'],
        sum(oracle['ambiguous'].values())]
    for name, expected in oracle['copies'].items():
        copy = report['backend_reference'][name]
        for state in ('WT', 'A_only', 'B_only', 'AB'):
            assert copy['fixed_alignment_counts'][state] == expected['aligned_site_bases'][state]
        assert sum(copy['fixed_alignment_counts'][k] for k in ('other_mixed', 'unassessable')) == expected['aligned_site_bases']['other']
        assert copy['ordinary_alignments'] == expected['ordinary_alignments']
        assert copy['native_window_modified'] == expected['native_window_modified']
        assert copy['qc']['AB_full_length_exact'] == expected['literal_merged_templates']['AB']
        assert report['windows'][name]['effective_indices'] == oracle['window_indices']


def native_summary(report):
    return {k: v for k,v in report.items() if k not in ('execution','copy_assignment')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path, help='New writable directory')
    parser.add_argument('inputs', type=Path, help='Original regression FASTQ/reference attachments')
    parser.add_argument('prepared', type=Path, help='Read-only work directory produced by epsps-real/audit.py')
    parser.add_argument('--executable', default='peanalyzer-crispresso')
    args = parser.parse_args()
    args.work.mkdir(parents=True)
    core = resolve_executable(args.executable)
    targets, truth, r1, r2, total = synthetic(args.work)
    results = {'version': core.version, 'runtime_digest': IMAGE, 'synthetic': {}, 'epsps': {}}
    site_windows = {t.copy_name: '81-81_92-92' for t in targets}
    for variant, windows in [('sites', site_windows), ('outside', dict.fromkeys(site_windows, '50-60')),
                             ('default', None), ('as_acquired', site_windows)]:
        report = run_core_sites(targets=targets, r1=r2 if variant == 'as_acquired' else r1,
                                r2=r1 if variant == 'as_acquired' else r2, input_pairs=total, core=core,
                                runtime_digest=IMAGE, output=args.work/variant, windows=windows)
        assert report['ambiguous'] == report['discarded'] == 0
        assert report['aligned'] == total
        for copy, expected in truth.items():
            actual = report['backend_reference'][copy]
            assert actual['counts'] == expected, (copy, actual, expected)
            assert actual['qc']['AB_full_length_exact'] == 3
            assert actual['qc']['AB_with_additional_change'] == 4
            assert actual['double_edit']['denominator'] == sum(expected.values())
            assert actual['native_window_modified'] == {'outside':0, 'sites':23, 'default':25, 'as_acquired':23}[variant]
        results['synthetic'][variant] = native_summary(report)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'epsps-real'))
    from audit import validate_sources
    refs = validate_sources(args.inputs)[1]['EPSPS_284bp']
    targets = [target(name, t['wt_sequence'], t['intended_pe_sequence']) for name,t in refs.items()]
    oracle_path = Path(__file__).resolve().parents[1] / 'epsps-real/evidence/core-comparison.json'
    oracle = json.loads(oracle_path.read_text())
    results['independent_core_recount_sha256'] = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
    for group in ('1A', 'all_known'):
        report = run_core_sites(targets=targets, r1=args.prepared/(group+'.1.fq'), r2=args.prepared/(group+'.2.fq'),
                                input_pairs=oracle[group]['raw_pairs'], core=core, runtime_digest=IMAGE,
                                output=args.work/group, windows=dict.fromkeys(refs, '146-146_157-157'))
        compare_real(report, oracle[group])
        results['epsps'][group] = native_summary(report)
        results['epsps'][group]['prepared_input_sha256'] = report['execution']['input_sha256']
    # Repeat acquisition order with the normalized prepared mate files supplied in reverse.
    # The independent program demultiplexes and trims the original acquired mates anew.
    oracle_control = direct_order_recount(args.inputs, args.work/'independent-acquired', core.path)
    acquired = run_core_sites(targets=targets, r1=args.prepared/'1A.2.fq', r2=args.prepared/'1A.1.fq',
                              input_pairs=oracle_control['raw_pairs'], core=core, runtime_digest=IMAGE,
                              output=args.work/'1A-acquired', windows=dict.fromkeys(refs, '146-146_157-157'))
    compare_real(acquired, oracle_control)
    results['epsps']['1A_acquired'] = native_summary(acquired)
    results['epsps']['1A_acquired']['prepared_input_sha256'] = acquired['execution']['input_sha256']
    results['independent_acquired'] = oracle_control
    (args.work/'integer-reconciliation.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
