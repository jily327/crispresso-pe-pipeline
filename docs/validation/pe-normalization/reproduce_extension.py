"""Exercise production routing and secondary-copy allele accounting on artificial molecules."""
import argparse
import gzip
import json
from pathlib import Path

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.backend.synthetic import changed
from peanalyzer.demux import demultiplex
from peanalyzer.metrics.production import run_metrics
from peanalyzer.remediation import panel
from peanalyzer.routing import route_analysis
from peanalyzer.schemas import Config, reverse_complement


def main(output, exe):
    output.mkdir(parents=True, exist_ok=False)
    first, secondary=panel()
    pos=140
    def mutate(seq, p): return seq[:p]+changed(seq[p])+seq[p+1:]
    converted=secondary.prime_edited_sequence
    secondary=secondary.model_copy(update=dict(wt_sequence=mutate(secondary.wt_sequence,pos),
                                               prime_edited_sequence=mutate(converted,pos)))
    # The independently specified whole-fragment truth includes other changes and a marker mosaic.
    products=[(first.wt_sequence,3),(first.prime_edited_sequence,4),(secondary.wt_sequence,8),
              (secondary.prime_edited_sequence,7),(converted,6),(mutate(secondary.prime_edited_sequence,68),5),
              (secondary.wt_sequence[:120]+first.wt_sequence[120:],2)]
    prefixes=['GCTTGCGTTGGAGTGAGTACGGTGTGC','CTGTGTAGTGAGTTGGATGCTGGATGG']
    for mate, prefix in enumerate(prefixes,1):
        with gzip.open(output/f'R{mate}.fq.gz','wt') as handle:
            for i,(fragment,count) in enumerate(products):
                seq=prefix+(fragment[:150] if mate==1 else reverse_complement(fragment[-150:]))
                for j in range(count):
                    handle.write(f'@artificial-{i}-{j} {mate}:N:0:SYN\n{seq}\n+\n{"I"*len(seq)}\n')
    (output/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nsynthetic,1B,F1,RB\n')
    demultiplex(r1=output/'R1.fq.gz',r2=output/'R2.fq.gz',samples_path=output/'samples.csv',
                config=Config(schema_version=1),output=output/'demux')
    prepare_analysis_fastqs(output/'demux',output/'prepared')
    targets=[first,secondary]
    routing=route_analysis(output/'prepared','1B',targets,output/'routing')
    result=run_metrics(analysis_root=output/'prepared',sample_id='1B',targets=targets,analysis_id='synthetic-rtt',
                       output=output/'metrics',core=resolve_executable(exe),routing_root=output/'routing')
    report=result.anchor_evidence['extension_alleles']['copy2']
    assert report['status']=='REPORTABLE', report
    assert report['counts']==dict(exact_wt=8,intended_snp_retained=7,intended_snp_converted=6,other_modification=5,unresolved=0)
    assert result.copies['copy2'].native.numerator is None and result.copies['copy2'].native.status=='BLOCKED'
    assert routing['cohorts']['quarantine']['pairs']==2
    summary=dict(secondary={k:v for k,v in report.items() if k!='artifacts'},
                 primary_native=result.copies['copy1'].native.model_dump(include={'status','numerator','denominator'}),secondary_native=result.copies['copy2'].native.status,
                 quarantine=routing['cohorts']['quarantine']['pairs'],cohort=routing['cohorts']['copy2']['pairs'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('core')
    args=parser.parse_args();main(args.output,args.core)
