"""Generate the synthetic TIGR-Tas nuclease experiment (raw pool + metadata + truth).

Usage: python make_nuclease_experiment.py OUTDIR
Designed classes are relative to the W2 window s+4..s+13 (0-based inclusive), which this
script derives independently from the 18-nt target position.
"""
import sys
from pathlib import Path
from design import nuclease_design, sub, write_pool, write_csv, sample_rows, SAMPLE_HEADER, dump, random_sequence

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
WINDOW = sys.argv[2] if len(sys.argv) > 2 else 'W2'
d = nuclease_design()
wt, s = d['wt'], d['start']
w2 = [s + 4, s + 13]                              # independent derivation: cuts at s+4|s+5 and s+12|s+13
ins3 = 'GAT'
molecules = dict(
    wt=wt,
    deletion_in_window=wt[:s + 6] + wt[s + 11:],                 # 5-bp deletion fully inside W2
    insertion_in_window=wt[:s + 9] + ins3 + wt[s + 9:],          # 3-bp insertion, both anchors inside W2
    substitution_in_window=sub(wt, s + 8),                       # substitution only
    ins_and_del_net_zero=wt[:s + 5] + wt[s + 8:s + 11] + ins3 + wt[s + 11:],  # 3-bp deletion then 3-bp insertion
    deletion_plus_substitution=sub(wt[:s + 6] + wt[s + 9:], s + 10 - 3),      # 3-bp deletion + nearby substitution
    deletion_outside_window=wt[:20] + wt[25:],                   # 5-bp deletion far from the window
    substitution_outside_window=sub(wt, 150),
    large_deletion_spanning_window=wt[:s - 20] + wt[s + 30:],    # 50-bp deletion covering the whole target
    unrelated=random_sequence(190, 777),
    # Well-separated 4-bp deletion and 4-bp insertion (net zero); both inside W4 only.
    separated_ins_del_net_zero=wt[:s - 6] + wt[s - 2:s + 21] + 'CTAG' + wt[s + 21:],
    separated_del5_ins2=wt[:s - 6] + wt[s - 1:s + 21] + 'CA' + wt[s + 21:],
)
meta = {
    '1B': dict(sample_name='nuc_ctrl_1', editor='TIGR', treatment='control', dpi=5, rep='1'),
    '2B': dict(sample_name='nuc_ctrl_2', editor='TIGR', treatment='control', dpi=5, rep='2'),
    '3B': dict(sample_name='nuc_cut_1', editor='TIGR', treatment='nuclease', dpi=5, rep='1'),
    '4B': dict(sample_name='nuc_cut_2', editor='TIGR', treatment='nuclease', dpi=5, rep='2'),
}
counts = {
    '1B': dict(wt=500, substitution_outside_window=20, deletion_outside_window=10),
    '2B': dict(wt=450, substitution_in_window=6, unrelated=4),
    '3B': dict(wt=300, deletion_in_window=80, insertion_in_window=40, substitution_in_window=25, ins_and_del_net_zero=15,
               deletion_plus_substitution=10, deletion_outside_window=12, substitution_outside_window=8,
               large_deletion_spanning_window=20, unrelated=5,
               separated_ins_del_net_zero=18, separated_del5_ins2=7),
    '4B': dict(wt=200, deletion_in_window=120, insertion_in_window=10, large_deletion_spanning_window=30),
}
pool = {b: [(label, molecules[label], n) for label, n in c.items()] for b, c in counts.items()}
total = write_pool(out / 'pool_R1.fastq.gz', out / 'pool_R2.fastq.gz', pool, seed=9)
write_csv(out / 'samples.csv', SAMPLE_HEADER, sample_rows(meta))
write_csv(out / 'targets.csv', ['analysis_mode', 'target_name', 'copy_name', 'wt_sequence', 'nuclease_profile',
                                'tigr_target_sequence', 'tigr_window'],
          [['indel_nuclease', d['target_name'], d['copy_name'], wt, 'tigr_tas_v1', d['tigr_target'], WINDOW]])
(out / 'config.yaml').write_text('schema_version: 1\ndemux:\n  profile: qi_hitom_v1\n')
# Designed class of each molecule relative to W2 (what a window-aware caller should report).
designed_class = dict(wt='unmodified', deletion_in_window='indel_only', insertion_in_window='indel_only',
                      substitution_in_window='substitution_only', ins_and_del_net_zero='indel_only',
                      deletion_plus_substitution='indel_plus_substitution', deletion_outside_window='unmodified',
                      substitution_outside_window='unmodified', large_deletion_spanning_window='indel_only',
                      unrelated='unaligned')
windows = dict(W1=[[s + 4, s + 5], [s + 12, s + 13]], W2=[[s + 4, s + 13]], W3=[[s, s + 17]], W4=[[max(0, s - 10), min(len(wt) - 1, s + 27)]])
dump(out / 'truth.json', dict(design=d, w2=w2, window=WINDOW, window_ranges=windows[WINDOW], molecules=molecules, counts=counts, meta=meta, total_pool_pairs=total,
                              designed_class=designed_class))
print('pool pairs', total, 'W2', w2)
