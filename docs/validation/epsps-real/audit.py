"""Read-only audit of the deposited real-data regression inputs.

Run from an editable installation of PEAnalyzer. Write only to a NEW directory.
Barcode names denote physical indexes until matched to the original sample sheet.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from contextlib import ExitStack
from importlib.resources import files
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.observability import assess_pair

if not __debug__:
    raise RuntimeError('Run regression checks with Python assertions enabled')

HERE = Path(__file__).resolve().parent
CATALOG = files('peanalyzer').joinpath('barcode_sets/qi_hitom_v1.csv')
STATES = ('WT', 'A_only', 'B_only', 'AB')
BASES = ('GG', 'AG', 'GA', 'AA')
COPY_NAMES = ('chr01g', 'chr17g')
COMPLEMENT = str.maketrans('ACGTN', 'TGCAN')


def rc(seq):
    return seq.translate(COMPLEMENT)[::-1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_sources(root):
    paths = {}
    expected = json.loads((HERE / 'input-sha256.json').read_text())
    for name, digest in expected.items():
        matches = list(root.rglob(name))
        if len(matches) != 1 or sha(matches[0]) != digest:
            raise ValueError(f'Input missing, duplicated or altered: {name}')
        paths[name] = matches[0]
    with ZipFile(paths['ALSW_EPSPS_regression_reference_DNA.zip']) as archive:
        manifest = json.loads(archive.read('reference_manifest.json'))
        for row in manifest['current_EPSPS_FASTQ_files']:
            path = paths[row['filename']]
            assert expected[path.name] == row['sha256'] and path.stat().st_size == row['size_bytes']
        all_fasta = {}
        panels = {}
        for panel in manifest['reference_panels']:
            seqs = {}
            for copy in panel['reference_copies']:
                wt, pe = copy['wt_sequence'], copy['intended_pe_sequence']
                length = panel['amplicon_length_bp']
                assert len(wt) == len(pe) == length and set(wt + pe) <= set('ACGT')
                changes = [(i, a, b) for i, (a, b) in enumerate(zip(wt, pe)) if a != b]
                assert changes == [(m['position_0based'], m['wt'], m['edited']) for m in copy['mutations']]
                for state, seq, key in [('WT', wt, 'wt_sha256'), ('intended_PE', pe, 'intended_pe_sha256')]:
                    assert hashlib.sha256(seq.encode()).hexdigest() == copy[key]
                    header = f"{panel['panel_id']}|{copy['copy_id']}|{state}|length={length}"
                    seqs[header] = seq
            assert read_fasta(archive.read(panel['panel_id'] + '.fasta')) == seqs
            all_fasta.update(seqs)
            panels[panel['panel_id']] = {c['copy_id']: c for c in panel['reference_copies']}
        assert read_fasta(archive.read('ALL_panels.fasta')) == all_fasta
    return paths, panels


def read_fasta(data):
    records = {}
    for line in data.decode().splitlines():
        if line.startswith('>'):
            name = line[1:]
            assert name not in records
            records[name] = ''
        else:
            records[name] += line.strip()
    return records


def calls():
    with CATALOG.open() as stream:
        rows = list(csv.DictReader(stream))
    return [{r['sequence']: r['barcode_id'][1:] for r in rows if r['direction'] == end}
            for end in ('forward', 'reverse')]


def haplotypes(refs):
    seqs = {}
    for name, entry in refs.items():
        wt = entry['wt_sequence']
        for state, (first, second) in zip(STATES, BASES):
            allele = wt[:146] + first + wt[147:157] + second + wt[158:]
            assert allele not in seqs
            seqs[allele] = (name, state)
        assert seqs[entry['intended_pe_sequence']] == (name, 'AB')
    return seqs


def window_pattern(refs):
    neighborhoods = {r['wt_sequence'][134:170] for r in refs.values()}
    assert len(neighborhoods) == 1
    window = neighborhoods.pop()
    return re.compile(f'(?={window[:12]}([AG]){window[13:23]}([AG]){window[24:]})')


def site_call(seq, qual, pattern):
    matches = list(pattern.finditer(seq))
    if len(matches) != 1:
        return 'missing_or_nonunique_context'
    hit = matches[0]
    if min(ord(qual[hit.start(i)]) - 33 for i in (1, 2)) < 30:
        return 'low_quality'
    return STATES[BASES.index(''.join(hit.groups()))]


def copy_call(mates, markers):
    votes = []
    for region in markers:
        for seq in mates:
            seen = [name for name, motif in region.items() if seq.count(motif) == 1]
            if len(seen) != 1:
                return 'unresolved'
            votes.extend(seen)
    return votes[0] if len(set(votes)) == 1 else 'unresolved'


def full_match(forward, reverse_forward, alleles):
    # The supplied dataset has no prepared end longer than the 284 bp reference.
    # Require direct evidence at every base on at least one mate, with exact
    # agreement on the overlap. Do not fill uncovered sequence from the reference.
    if not forward or not reverse_forward or max(len(forward), len(reverse_forward)) > 284:
        return None
    overlap = len(forward) + len(reverse_forward) - 284
    if overlap < 10 or forward[-overlap:] != reverse_forward[:overlap]:
        return None
    return alleles.get(forward + reverse_forward[overlap:])


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def table(path, headers, rows):
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(headers)
        writer.writerows(rows)


def audit(root, out):
    paths, panels = validate_sources(root)
    out.mkdir(parents=True, exist_ok=False)
    refs = panels['EPSPS_284bp']
    alleles = haplotypes(refs)
    pattern = window_pattern(refs)
    markers = [{c: r['wt_sequence'][start:start + 15] for c, r in refs.items()}
               for start in (99, 226)]
    for region in markers:
        for c, marker in region.items():
            for seq, (copy, _) in alleles.items():
                assert seq.count(marker) == int(c == copy)
    catalogs = calls()
    matrix, site, full, eligibility = Counter(), Counter(), Counter(), Counter()
    offsets, bridge_counts, legacy = Counter(), Counter(), Counter()
    bridges = ('GGAGTGAGTACGGTGTGC', 'GAGTTGGATGCTGGATGG')
    targets = [SimpleNamespace(copy_name=c, wt_sequence=r['wt_sequence'],
                               prime_edited_sequence=r['intended_pe_sequence']) for c, r in refs.items()]
    bins = [a + b for a, b in product(*[list(d.values()) + ['?'] for d in catalogs])]
    for dataset, basename, panel_id in [('EPSPS', 'EPSPS_1106', 'EPSPS_284bp'),
                                         ('ALSW', 'ALSW_dif_knots', 'ALSW_253bp')]:
        panel = panels[panel_id]
        seqs = [r['wt_sequence'] for r in panel.values()]
        ends = {label: {transform(seq)[:16] for seq in seqs}
                for label, transform in [('forward', str), ('reverse', rc)]}
        patterns = {label: re.compile('(?=' + '|'.join(sorted(motifs)) + ')')
                    for label, motifs in ends.items()}
        ids = set()
        with ExitStack() as stack:
            outputs = {}
            if dataset == 'EPSPS':
                for pop in ('1A', 'all_known'):
                    for mate in (1, 2):
                        outputs[pop, mate] = stack.enter_context((out / f'{pop}.{mate}.fq').open('wb'))
            for pair in paired_fastq(*(paths[f'{basename}_R{i}.fastq.gz'] for i in (1, 2))):
                ident = read_id(pair[0], 1)
                if ident in ids:
                    raise ValueError('Repeated raw pair ID')
                ids.add(ident)
                seq = [r.sequence.decode() for r in pair]
                barcode = ''.join(d.get(s[:9], '?') for d, s in zip(catalogs, seq))
                matrix[dataset, barcode] += 1
                for i, s in enumerate(seq):
                    bridge_counts[dataset, i + 1, s[9:27] == bridges[i]] += 1
                    for strand, end_pattern in patterns.items():
                        positions = {m.start() for m in end_pattern.finditer(s[:95])}
                        key = str(positions.pop()) if len(positions) == 1 else ('multiple' if positions else 'absent')
                        offsets[dataset, i + 1, strand, key] += 1
                if dataset != 'EPSPS':
                    continue
                if len(seq[0]) <= 26 or len(seq[1]) <= 27:
                    eligibility[barcode, 'too_short'] += 1
                    continue
                rev, fwd = pair[0].trimmed(26), pair[1].trimmed(27)
                left, right = fwd.sequence.decode(), rc(rev.sequence.decode())
                if '?' not in barcode:
                    for pop in (('1A', 'all_known') if barcode == '1A' else ('all_known',)):
                        for mate, rec in enumerate((fwd, rev), 1):
                            # Keep normalized raw pair identifiers. Mate numbering now
                            # refers to the derived orientation supplied to CRISPResso.
                            outputs[pop, mate].write(b'@' + ident + b'/' + str(mate).encode() + b'\n'
                                                     + rec.sequence + b'\n+\n' + rec.quality_line)
                exact = full_match(left, right, alleles)
                if exact:
                    full[barcode, *exact] += 1
                mate_calls = [site_call(left, fwd.quality_line.rstrip().decode(), pattern),
                              site_call(right, rev.quality_line.rstrip().decode()[::-1], pattern)]
                if all(s in STATES for s in mate_calls) and mate_calls[0] == mate_calls[1]:
                    copy = copy_call((left, right), markers)
                    site[barcode, copy, mate_calls[0]] += 1
                    eligibility[barcode, 'callable'] += 1
                elif any(s == 'missing_or_nonunique_context' for s in mate_calls):
                    eligibility[barcode, 'missing_or_nonunique_context'] += 1
                elif 'low_quality' in mate_calls:
                    eligibility[barcode, 'low_quality'] += 1
                else:
                    eligibility[barcode, 'discordant'] += 1
                if barcode == '1A':
                    for tr1 in (26, 27):
                        first = pair[0].trimmed(tr1)
                        for swap in (False, True):
                            test_pair = (fwd, first) if swap else (first, fwd)
                            result = assess_pair(test_pair, targets)
                            legacy[tr1, 27, swap, result['canonical']] += 1
    table(out / 'barcodes.csv', ['barcode', 'EPSPS_pairs', 'ALSW_pairs'],
          ((b, matrix['EPSPS', b], matrix['ALSW', b]) for b in bins))
    table(out / 'end_offsets.csv', ['dataset', 'mate', 'strand', 'offset_0based', 'pairs'],
          [(*key, n) for key, n in sorted(offsets.items())])
    table(out / 'bridges.csv', ['dataset', 'mate', 'exact_bridge', 'pairs'],
          [(*key, n) for key, n in sorted(bridge_counts.items())])
    table(out / 'v101_1A.csv', ['R1_trim', 'R2_trim', 'swap_for_classifier', 'classification', 'pairs'],
          [(*key, n) for key, n in sorted(legacy.items())])
    groups = [*COPY_NAMES, 'unresolved']
    rows, qc = [], []
    for b in bins:
        for method, counts in [('both_mates_Q30_sites', site), ('full_pair_template_exact', full)]:
            for c in ['combined', *groups]:
                values = [sum(counts[b, k, state] for k in groups) if c == 'combined' else counts[b, c, state]
                          for state in STATES]
                rows.append((b, method, c, matrix['EPSPS', b], *values, sum(values)))
        reasons = ['callable', 'missing_or_nonunique_context', 'low_quality', 'discordant', 'too_short']
        values = [eligibility[b, reason] for reason in reasons]
        assert sum(values) == matrix['EPSPS', b]
        qc.append((b, *values))
    table(out / 'haplotypes.csv', ['barcode', 'method', 'copy', 'raw_pairs', *STATES, 'four_state_denominator'], rows)
    table(out / 'site_qc.csv', ['barcode', *reasons], qc)
    json_write(out / 'validated-inputs.json', {n: sha(p) for n, p in paths.items()})
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    audit(args.inputs, args.out)
