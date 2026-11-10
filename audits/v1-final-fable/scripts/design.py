"""Independent synthetic experiment design for the PEAnalyzer v1.0.0 final audit.

Nothing here imports PEAnalyzer. Molecule counts written to truth.json are the
audit's independent ground truth: every expected numerator/denominator is derived
from what was physically put into the FASTQ files, never from product output.
All sequences are synthetic (seeded PRNG); no biological or patient data.
"""
import gzip
import json
import random
from pathlib import Path

COMP = str.maketrans('ACGT', 'TGCA')
F_BRIDGE = 'GGAGTGAGTACGGTGTGC'
R_BRIDGE = 'GAGTTGGATGCTGGATGG'
FWD = {f'F{i}': s for i, s in enumerate(
    ['GCTTGCGTT', 'GCTTGTAGT', 'GCTTACGCT', 'GCTTCTCGT', 'GCTTGCTCT', 'GCTTAGTCT',
     'GCTTCGACT', 'GCTTGATGT', 'GCTTATACT', 'GCTTCACAT', 'GCTTGTGCT', 'GCTTACTAT'], 1)}
REV = dict(zip(['RA', 'RB', 'RC', 'RD', 'RE', 'RF', 'RG', 'RH'],
               ['CTGTGCGTT', 'CTGTGTAGT', 'CTGTACGCT', 'CTGTCTCGT', 'CTGTGCTCT', 'CTGTAGTCT',
                'CTGTCGACT', 'CTGTGATGT']))
ADAPTER = 'AGATCGGAAGAGCACACGTCTGAACTCCAGTCACATCACGATCTCGTATGCCGTCTTCTGCTTG'


def rc(s):
    return s.translate(COMP)[::-1]


def random_sequence(n, seed):
    """Low-repeat random DNA: reject any 8-mer (or its reverse complement) seen before."""
    rng = random.Random(seed)
    seq = ''
    seen = set()
    while len(seq) < n:
        base = rng.choice('ACGT')
        cand = seq + base
        if len(cand) >= 4 and len(set(cand[-4:])) == 1:
            continue  # no homopolymer runs of 4
        if len(cand) >= 8:
            k = cand[-8:]
            if k in seen or rc(k) in seen:
                continue
            seen.add(k)
        seq = cand
    return seq


def sub(seq, pos, base=None):
    old = seq[pos]
    new = base or {'A': 'C', 'C': 'A', 'G': 'T', 'T': 'G'}[old]
    assert new != old
    return seq[:pos] + new + seq[pos + 1:]


def pe_design(seed=11, length=190):
    """Single-copy PE target: 2-base substitution (+2 and PAM), spacer forward."""
    wt = random_sequence(length, seed)
    # Force an NGG PAM at 80..82 so the 20-nt spacer is wt[60:80]; nick between 76|77.
    wt = wt[:80] + 'TGG' + wt[83:]
    spacer = wt[60:80]
    pe = sub(sub(wt, 78), 81, 'C')          # two intended substitutions
    extension = rc(pe[64:92])               # RTT+PBS, RNA 5'->3'; rc(extension) is in PE
    partial = sub(wt, 78)                   # only the first intended base
    assert rc(extension) in pe and spacer in wt and wt.count(spacer) == 1
    return dict(target_name='T1', copy_name='copy1', wt=wt, pe=pe, spacer=spacer, extension=extension,
                partial=partial, edit_positions=[78, 81])


def nuclease_design(seed=23, length=190):
    wt = random_sequence(length, seed)
    s = 80
    target18 = wt[s:s + 18]
    assert wt.count(target18) == 1 and rc(target18) not in wt
    return dict(target_name='N1', copy_name='copy1', wt=wt, tigr_target=target18, start=s)


def read_pair(molecule, fbar, rbar, read_len=150):
    """Hi-TOM layout: barcode(9)+bridge(18)+insert; read-through continues into the far end."""
    top = FWD[fbar] + F_BRIDGE + molecule + rc(R_BRIDGE) + rc(REV[rbar]) + ADAPTER * 3
    bottom = REV[rbar] + R_BRIDGE + rc(molecule) + rc(F_BRIDGE) + rc(FWD[fbar]) + ADAPTER * 3
    return top[:read_len], bottom[:read_len]


def write_pool(path_r1, path_r2, samples, seed=5, read_len=150, extra_pairs=()):
    """samples: {barcode_id: [(label, molecule, count), ...]}; shuffled deterministically."""
    rows = []
    for barcode_id, classes in samples.items():
        f, r = 'F' + barcode_id[:-1], 'R' + barcode_id[-1]
        for label, molecule, count in classes:
            for i in range(count):
                rows.append((f'{barcode_id}:{label}:{i}', *read_pair(molecule, f, r, read_len)))
    for name, r1, r2 in extra_pairs:
        rows.append((name, r1, r2))
    random.Random(seed).shuffle(rows)
    with gzip.open(path_r1, 'wt') as h1, gzip.open(path_r2, 'wt') as h2:
        for name, r1, r2 in rows:
            h1.write(f'@{name}/1\n{r1}\n+\n{"I" * len(r1)}\n')
            h2.write(f'@{name}/2\n{r2}\n+\n{"I" * len(r2)}\n')
    return len(rows)


def write_csv(path, header, rows):
    import csv
    with open(path, 'w', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(header)
        writer.writerows(rows)


SAMPLE_HEADER = ['sample_name', 'barcode_id', 'forward_barcode', 'reverse_barcode', 'editor', 'treatment',
                 'dpi', 'biological_replicate', 'block_id', 'paired']


def sample_rows(meta):
    return [[m['sample_name'], b, FWD['F' + b[:-1]], REV['R' + b[-1]], m['editor'], m['treatment'], m['dpi'],
             m['rep'], '', 'false'] for b, m in meta.items()]


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
