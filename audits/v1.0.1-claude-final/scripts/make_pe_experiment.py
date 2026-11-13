"""Generate the synthetic PE experiment (raw Hi-TOM pool + metadata + truth).

Usage: python make_pe_experiment.py OUTDIR
Ground truth is the designed molecule inventory, independent of PEAnalyzer.
"""
import sys
from pathlib import Path
from design import (pe_design, sub, write_pool, write_csv, sample_rows, SAMPLE_HEADER, dump, random_sequence)

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
d = pe_design()
wt, pe, partial = d['wt'], d['pe'], d['partial']
pe_extra = sub(pe, 20)             # intended edit + unintended substitution far from the edit
wt_sub = sub(wt, 150)              # WT + unintended substitution far from the edit
deletion = wt[:75] + wt[80:]       # 5-bp deletion spanning the nick (indel by-product)
wrong_sub = sub(sub(wt, 78, None), 81, 'A')  # first intended base + WRONG base at the PAM site
assert wrong_sub != pe
junk = random_sequence(190, 999)   # unrelated product

meta = {
    '1A': dict(sample_name='ctrl_rep1', editor='PE2', treatment='control', dpi=7, rep='1'),
    '2A': dict(sample_name='ctrl_rep2', editor='PE2', treatment='control', dpi=7, rep='2'),
    '3A': dict(sample_name='edit_rep1', editor='PE2', treatment='edited', dpi=7, rep='1'),
    '4A': dict(sample_name='edit_rep2', editor='PE2', treatment='edited', dpi=7, rep='2'),
}
# label -> molecule; counts per sample chosen so exact and native PE differ in BOTH directions.
molecules = dict(exact_wt=wt, exact_pe=pe, partial_pe=partial, pe_plus_extra=pe_extra, wt_plus_sub=wt_sub,
                 nick_deletion=deletion, wrong_substitution=wrong_sub, unrelated=junk)
counts = {
    '1A': dict(exact_wt=400, exact_pe=0, partial_pe=0, pe_plus_extra=0, wt_plus_sub=30, nick_deletion=0, wrong_substitution=0, unrelated=10),
    '2A': dict(exact_wt=300, exact_pe=3, partial_pe=0, pe_plus_extra=0, wt_plus_sub=10, nick_deletion=5, wrong_substitution=0, unrelated=0),
    '3A': dict(exact_wt=200, exact_pe=100, partial_pe=40, pe_plus_extra=60, wt_plus_sub=20, nick_deletion=30, wrong_substitution=20, unrelated=5),
    '4A': dict(exact_wt=100, exact_pe=150, partial_pe=10, pe_plus_extra=5, wt_plus_sub=120, nick_deletion=10, wrong_substitution=0, unrelated=0),
}
pool = {b: [(label, molecules[label], n) for label, n in c.items() if n] for b, c in counts.items()}
# Pairs that must NEVER reach a sample: an undeclared-but-valid barcode pair and a no-barcode pair.
from design import read_pair
extra = [(f'unexpected:{i}', *read_pair(pe, 'F5', 'RB')) for i in range(25)]
extra += [(f'nobarcode:{i}', 'ACGT' * 37 + 'AC', 'TGCA' * 37 + 'TG') for i in range(15)]
total = write_pool(out / 'pool_R1.fastq.gz', out / 'pool_R2.fastq.gz', pool, extra_pairs=extra)
write_csv(out / 'samples.csv', SAMPLE_HEADER, sample_rows(meta))
write_csv(out / 'targets.csv', ['target_name', 'copy_name', 'wt_sequence', 'prime_edited_sequence', 'pegRNA_spacer',
                                'pegRNA_extension', 'nicking_guide', 'pegRNA_scaffold'],
          [[d['target_name'], d['copy_name'], wt, pe, d['spacer'], d['extension'], '', '']])
(out / 'config.yaml').write_text('schema_version: 1\ndemux:\n  profile: qi_hitom_v1\n')
(out / 'contrasts.yaml').write_text('''schema_version: 1
families: [primary]
contrasts:
  - contrast_id: exact-edited-vs-control
    family_id: primary
    target_name: T1
    metric_name: total_precise_pe
    copy_name: null
    policy_id: null
    group_a: {editor: PE2, treatment: control, dpi: 7}
    group_b: {editor: PE2, treatment: edited, dpi: 7}
    pairing_mode: unpaired
    alternative: two-sided
  - contrast_id: native-edited-vs-control
    family_id: primary
    target_name: T1
    metric_name: target_crispresso_native_pe
    copy_name: null
    policy_id: null
    group_a: {editor: PE2, treatment: control, dpi: 7}
    group_b: {editor: PE2, treatment: edited, dpi: 7}
    pairing_mode: unpaired
    alternative: two-sided
''')
truth = dict(design=d, molecules=molecules, counts=counts, meta=meta, total_pool_pairs=total,
             unexpected_valid_pairs=25, no_barcode_pairs=15,
             expected_exact={b: dict(numerator=c['exact_pe'], denominator=c['exact_wt'] + c['exact_pe']) for b, c in counts.items()},
             expected_prepared_pairs={b: sum(c.values()) for b, c in counts.items()})
dump(out / 'truth.json', truth)
print('pool pairs', total)
