"""Two-homeolog PE experiment: ambiguity must never become a confident copy assignment.

Usage: python make_multicopy_experiment.py OUTDIR routable|blocked|lengthdiff
 routable  : copies differ at 4 edit-independent SNPs (two each side of the edit) -> routing allowed
 blocked   : copies differ at 1 SNP -> routing geometry BLOCKED; target metrics must survive
 lengthdiff: copyB carries a 6-bp internal expansion; with 150-nt reads only copyA is
             reconstructible -> copy-dependent observability -> target exact NOT_ASSESSABLE
"""
import gzip
import random
import sys
from pathlib import Path
from design import pe_design, sub, read_pair, write_csv, sample_rows, SAMPLE_HEADER, dump, rc, random_sequence

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
variant = sys.argv[2]
length = 236 if variant == 'lengthdiff' else 190
d = pe_design(seed=31, length=length)
a_wt, a_pe = d['wt'], d['pe']
snps = [150] if variant == 'blocked' else [15, 40, 130, 170]
b_wt, b_pe = a_wt, a_pe
for p in snps:
    b_wt, b_pe = sub(b_wt, p), sub(b_pe, p)
if variant == 'lengthdiff':
    extra = 'GACTCA'
    b_wt = b_wt[:200] + extra + b_wt[200:]; b_pe = b_pe[:200] + extra + b_pe[200:]
chimera_wt = sub(sub(a_wt, snps[0]), snps[-1]) if len(snps) > 1 else None   # B allele at both outer sites only
if chimera_wt:
    chimera_wt = a_wt
    chimera_wt = sub(chimera_wt, snps[0])           # B at first site, A elsewhere -> mosaic of the two copies
meta = {'1C': dict(sample_name='mc_ctrl', editor='PE2', treatment='control', dpi=7, rep='1'),
        '2C': dict(sample_name='mc_edit', editor='PE2', treatment='edited', dpi=7, rep='1')}
counts = {'1C': dict(a_wt=200, a_pe=0, b_wt=150, b_pe=0, mosaic_wt=0, a_pe_lowq=0),
          '2C': dict(a_wt=120, a_pe=80, b_wt=90, b_pe=30, mosaic_wt=25 if chimera_wt else 0, a_pe_lowq=40)}
molecules = dict(a_wt=a_wt, a_pe=a_pe, b_wt=b_wt, b_pe=b_pe, mosaic_wt=chimera_wt or a_wt, a_pe_lowq=a_pe)
rows = []
for barcode, c in counts.items():
    f, r = 'F' + barcode[:-1], 'R' + barcode[-1]
    for label, n in c.items():
        for i in range(n):
            r1, r2 = read_pair(molecules[label], f, r)
            q1, q2 = 'I' * len(r1), 'I' * len(r2)
            if label == 'a_pe_lowq':
                # Every copy-diagnostic base is below Q30 in both mates: copy identity is not established,
                # although the full product sequence is an exact copyA PE molecule.
                q1 = list(q1); q2 = list(q2)
                for p in snps:
                    if 27 + p < len(r1): q1[27 + p] = '+'
                    back = 27 + (len(molecules[label]) - 1 - p)
                    if back < len(r2): q2[back] = '+'
                q1, q2 = ''.join(q1), ''.join(q2)
            rows.append((f'{barcode}:{label}:{i}', r1, q1, r2, q2))
random.Random(3).shuffle(rows)
with gzip.open(out / 'pool_R1.fastq.gz', 'wt') as h1, gzip.open(out / 'pool_R2.fastq.gz', 'wt') as h2:
    for name, r1, q1, r2, q2 in rows:
        h1.write(f'@{name}/1\n{r1}\n+\n{q1}\n'); h2.write(f'@{name}/2\n{r2}\n+\n{q2}\n')
write_csv(out / 'samples.csv', SAMPLE_HEADER, sample_rows(meta))
header = ['target_name', 'copy_name', 'wt_sequence', 'prime_edited_sequence', 'pegRNA_spacer', 'pegRNA_extension', 'nicking_guide', 'pegRNA_scaffold']
write_csv(out / 'targets.csv', header, [['T1', 'copyA', a_wt, a_pe, d['spacer'], d['extension'], '', ''],
                                        ['T1', 'copyB', b_wt, b_pe, d['spacer'], d['extension'], '', '']])
(out / 'config.yaml').write_text('schema_version: 1\ndemux:\n  profile: qi_hitom_v1\n')
exact = {}
for b, c in counts.items():
    pe_n = c['a_pe'] + c['b_pe'] + c['a_pe_lowq']
    wt_n = c['a_wt'] + c['b_wt']
    exact[b] = dict(numerator=pe_n, denominator=pe_n + wt_n)
dump(out / 'truth.json', dict(variant=variant, snps=snps, molecules=molecules, counts=counts, meta=meta,
                              expected_target_exact=exact, lengths=dict(copyA=len(a_wt), copyB=len(b_wt)),
                              expected_prepared_pairs={b: sum(c.values()) for b, c in counts.items()}))
print(variant, 'pairs', len(rows), 'lengths', len(a_wt), len(b_wt))
