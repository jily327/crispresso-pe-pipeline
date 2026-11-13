"""Long-running backend input: 40,000 unique synthetic read pairs (1-4 random substitutions each).

Usage: python make_heavy_input.py OUTDIR      (needs design.py beside it)
Writes input_R1.fastq.gz, input_R2.fastq.gz and args.txt (the CRISPResso argv, one item per line).
"""
import gzip, random, sys
from pathlib import Path
from design import pe_design, rc
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
d = pe_design(); wt, pe = d['wt'], d['pe']; rng = random.Random(77)
def mut(s):
    s = list(s)
    for _ in range(rng.randint(1, 4)):
        p = rng.randrange(5, len(s) - 5); s[p] = rng.choice([b for b in 'ACGT' if b != s[p]])
    return ''.join(s)
with gzip.open(out / 'input_R1.fastq.gz', 'wt', compresslevel=1) as a, gzip.open(out / 'input_R2.fastq.gz', 'wt', compresslevel=1) as b:
    for i in range(40000):
        m = mut(pe if i % 3 == 0 else wt); r1 = m[:123]; r2 = rc(m)[:123]
        a.write(f'@h{i}/1\n{r1}\n+\n{"I" * 123}\n'); b.write(f'@h{i}/2\n{r2}\n+\n{"I" * 123}\n')
(out / 'args.txt').write_text('\n'.join(['-r1', 'input_R1.fastq.gz', '-r2', 'input_R2.fastq.gz', '--amplicon_seq', wt, '--name', 'unrouted', '--output_folder', 'output',
    '--write_detailed_allele_table', '--keep_intermediate', '--suppress_report', '--suppress_plots', '--prime_editing_pegRNA_spacer_seq', d['spacer'],
    '--prime_editing_pegRNA_extension_seq', d['extension'], '--prime_editing_override_prime_edited_ref_seq', pe]))
