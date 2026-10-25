"""Compact synthetic nuclease inputs, with no biological/experimental data."""
import csv
import gzip
import json
import random
from pathlib import Path
import yaml
from peanalyzer.nuclease.targets import NucleaseTarget
from peanalyzer.schemas import reverse_complement
from peanalyzer.metrics.production import RUNTIME_DIGEST
from m7_fixtures import write_csv
from peanalyzer.validation import SAMPLE_COLUMNS

_rng=random.Random(771)
WT=''.join(_rng.choice('ACGT') for _ in range(240))
START=100

def other(base):return next(c for c in 'ACGT' if c!=base)
def substitute(seq,p):return seq[:p]+other(seq[p])+seq[p+1:]
def insert(seq,p):return seq[:p]+next(c for c in 'ACGT' if c not in seq[p-1:p+1])+seq[p:]

CASES={
 'WT':(WT,(0,0,0)),
 'substitution':(substitute(WT,108),(0,0,1)),
 'deletion':(WT[:108]+WT[109:],(0,1,0)),
 'insertion':(insert(WT,109),(1,0,0)),
 'insertion_deletion':(insert(WT,111)[:106]+insert(WT,111)[108:],(1,2,0)),
 'deletion_substitution':(substitute(WT,111)[:106]+substitute(WT,111)[107:],(0,1,1)),
 'insertion_substitution':(insert(substitute(WT,106),111),(1,0,1)),
 'net_zero':(insert(WT,112)[:105]+insert(WT,112)[106:],(1,1,0)),
 'outside_window':(substitute(WT,70),(0,0,0)),
 'left_cut_insertion':(insert(WT,105),(1,0,0)),
 'right_cut_insertion':(insert(WT,113),(1,0,0)),
 'large_deletion':(WT[:90]+WT[132:],(0,42,0)),
}


def target(**updates):
    data=dict(analysis_mode='indel_nuclease',target_name='T1',copy_name='copy1',wt_sequence=WT,
              nuclease_profile='tigr_tas_v1',tigr_target_sequence=WT[START:START+18])
    data.update(updates)
    return NucleaseTarget.model_validate(data)


def fixture(root,populations=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    populations=populations or [[('WT',18),('deletion',2)],[('WT',16),('deletion',4)],
                               [('WT',6),('deletion',14)],[('WT',4),('deletion',16)]]
    samples=[]
    for i,population in enumerate(populations):
        samples.append(dict(sample_name=f'bio{i+1}',barcode_id=f'bc{i+1:03}',forward_barcode='AAAAAAA'+'ACGT'[i],
            reverse_barcode='CCCCCCCC',editor='synthetic-nuclease',treatment='A' if i<2 else 'B',dpi=6,
            biological_replicate=str(i%2+1),block_id='',paired='false'))
    write_csv(root/'samples.csv',SAMPLE_COLUMNS,samples)
    t=target();write_csv(root/'targets.csv',list(t.model_dump()),[t.model_dump()])
    (root/'config.yaml').write_text(yaml.safe_dump(dict(schema_version=1,demux=dict(profile='custom',forward_length=8,reverse_length=8))))
    contrast=dict(schema_version=1,families=['primary'],contrasts=[dict(contrast_id='indel',family_id='primary',
        target_name='T1',metric_name='indel_fraction',copy_name=None,policy_id=None,
        group_a=dict(editor='synthetic-nuclease',treatment='A',dpi=6),group_b=dict(editor='synthetic-nuclease',treatment='B',dpi=6),
        pairing_mode='unpaired',alternative='two-sided')])
    (root/'contrasts.yaml').write_text(yaml.safe_dump(contrast))
    for mate in (1,2):
        with (root/f'raw_R{mate}.fastq.gz').open('wb') as raw:
            with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as handle:
                for sample,population in zip(samples,populations):
                    for case,count in population:
                        sequence=CASES[case][0]
                        seq=sequence[:150] if mate==1 else reverse_complement(sequence[-150:])
                        seq=sample['forward_barcode' if mate==1 else 'reverse_barcode']+seq
                        for j in range(count):
                            handle.write((f"@{sample['barcode_id']}_{case}_{j} {mate}:N:0:SYN\n{seq}\n+\n"+'I'*len(seq)+'\n').encode())
    return dict(mode='run',r1=root/'raw_R1.fastq.gz',r2=root/'raw_R2.fastq.gz',samples=root/'samples.csv',
        targets=root/'targets.csv',config=root/'config.yaml',output=root.parent/'workflow',crispresso='CRISPResso',
        runtime_digest=RUNTIME_DIGEST,analysis_r1_trim_5p=8,analysis_r2_trim_5p=8)
