"""Independent synthetic 33-nt insertion controls with prespecified whole-fragment truth."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import random

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.native_runs import write_native_runs
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.demux import demultiplex
from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.metrics.production import run_metrics
from peanalyzer.observability import assess_pair
from peanalyzer.schemas import Config, Target, reverse_complement


def main(root, exe):
    root.mkdir(parents=True, exist_ok=False)
    rng = random.Random(123991)
    wt=''.join(rng.choice('ACGT') for _ in range(240))
    pos=104
    insert='AGTCGCTTCCGACTAGGCTATTCGCTGACAGCA'
    insert=next(b for b in 'ACGT' if b!=wt[pos])+insert[1:-1]+next(b for b in 'ACGT' if b!=wt[pos-1])
    assert len(insert)==33
    def product(payload): return wt[:pos]+payload+wt[pos:]
    pe=product(insert)
    target=Target(target_name='SyntheticTag',copy_name='A',wt_sequence=wt,prime_edited_sequence=pe,
                  pegRNA_spacer=wt[pos-20:pos],pegRNA_extension=reverse_complement(pe[pos-21:pos+36]))
    # Unique insertion coordinate prevents equally valid repeat-shifted boundaries.
    assert [p for p in range(len(wt)+1) if pe[:p]+pe[p+len(insert):]==wt]==[pos]
    wrong=insert[:15]+('A' if insert[15]!='A' else 'C')+insert[16:]
    extra=pe[:72]+('A' if pe[72]!='A' else 'C')+pe[73:]
    products=[('exact_WT',wt,8,192),('exact_intended_insertion',pe,7,192),
              ('partial_intended_insert',product(insert[:16]),6,192),('alternate_same_length_insert',product(wrong),5,192),
              ('intended_insert_with_flank_substitutions',extra,4,192),('unexpected_longer_product',product(insert+'ACTGG'),3,192),
              ('tandem_intended_insert',product(insert+insert),2,192),('insufficient',pe,1,42),
              ('ambiguous', 'AT'*170,1,192)]
    prefixes=['GCTTGCGTTGGAGTGAGTACGGTGTGC','CTGTGTAGTGAGTTGGATGCTGGATGG']
    for mate,prefix in enumerate(prefixes,1):
        with gzip.open(root/f'R{mate}.fq.gz','wt') as f:
            for state,fragment,count,n in products:
                seq=prefix+(fragment[:n] if mate==1 else reverse_complement(fragment[-n:]))
                for i in range(count): f.write(f'@{state}:{i}/{mate}\n{seq}\n+\n{"I"*len(seq)}\n')
    (root/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nHiBiT-size,1B,F1,RB\n')
    demultiplex(r1=root/'R1.fq.gz',r2=root/'R2.fq.gz',samples_path=root/'samples.csv',
                config=Config(schema_version=1),output=root/'demux')
    prepare_analysis_fastqs(root/'demux',root/'prepared')
    sample=verify_analysis_output(root/'prepared').manifest['samples']['1B']
    by_truth={}
    paths=[root/'prepared'/sample['files'][m]['path'] for m in ('r1','r2')]
    for pair in paired_fastq(*paths):
        state=read_id(pair[0],1).decode().split(':')[0]
        observed=assess_pair(pair,[target])
        wanted={'exact_WT':'exact_WT','exact_intended_insertion':'exact_PE'}.get(state,'other_or_unassessable')
        assert observed['canonical']==wanted,(state,observed)
        if state in ('insufficient','ambiguous'):
            assert observed['reason'],(state,observed)
        by_truth.setdefault(state,Counter())[(observed['canonical'],observed['reason'])]+=1
    result=run_metrics(analysis_root=root/'prepared',sample_id='1B',targets=[target],analysis_id='HiBiT-synthetic',
                       output=root/'metrics',core=resolve_executable(exe))
    write_native_runs(root/'metrics','1B',target.target_name,[target],sample)
    anchor=result.anchor_evidence['backend_metrics']['A']
    classes=anchor['insertion_products']['counts']
    for state,_,n,_ in products[:-2]: assert classes[state]==n,(state,classes)
    native=anchor['native']
    assert native['backend_input_reads']==sum(x[2] for x in products)
    assert sum(classes.values())==native['aligned_reads']
    exact=result.target_metrics.total_precise_pe
    observed=[exact.numerator,exact.denominator]
    assert observed==[7,15] and exact.status=='REPORTABLE'
    summary=dict(fixture='Independent synthetic 33-nt insert, numerical multiplicities fixed before classification',
                 known_truth={state:n for state,_,n,_ in products},
                 paired_calls={s:[dict(call=k[0],reason=k[1],n=v) for k,v in counter.items()] for s,counter in by_truth.items()},
                 aligned_allele_counts=classes,full_sample_native=[native['numerator'],native['denominator']],
                 input=native['backend_input_reads'],exact_prepared_observed=observed)
    (root/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('core')
    a=p.parse_args(); main(a.output,a.core)
