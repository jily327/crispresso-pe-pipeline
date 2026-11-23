"""Compare final prepared exact, routing and native confident-copy counts by strand."""
import argparse
import json
from pathlib import Path

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.demux import demultiplex
from peanalyzer.metrics.production import run_metrics
from peanalyzer.routing import route_analysis
from peanalyzer.schemas import Config, reverse_complement
from peanalyzer.synthetic_routing import write_challenges


def main(output, exe):
    output.mkdir(parents=True, exist_ok=False)
    targets,_=write_challenges(output/'artificial')
    demultiplex(r1=output/'artificial/raw_R1.fastq.gz',r2=output/'artificial/raw_R2.fastq.gz',
                samples_path=output/'artificial/samples.csv',config=Config(schema_version=1),output=output/'demux')
    prepare_analysis_fastqs(output/'demux',output/'prepared')
    core=resolve_executable(exe)
    summary={}
    for strand in ('forward','reverse'):
        panel=targets if strand=='forward' else [t.model_copy(update=dict(wt_sequence=reverse_complement(t.wt_sequence),
                    prime_edited_sequence=reverse_complement(t.prime_edited_sequence))) for t in targets]
        case=output/strand
        route_analysis(output/'prepared','1B',panel,case/'routing')
        result=run_metrics(analysis_root=output/'prepared',sample_id='1B',targets=panel,analysis_id='native-strand-equivalence',
                           output=case/'metrics',core=core,routing_root=case/'routing')
        records={'target_native':result.target_metrics.target_crispresso_native_pe,'target_exact':result.target_metrics.total_precise_pe}
        for name,copy in result.copies.items():
            records[name+'_native']=copy.native;records[name+'_exact']=copy.precise
        summary[strand]={key:dict(status=v.status,numerator=v.numerator,denominator=v.denominator) for key,v in records.items()}
        assert all(r.status=='REPORTABLE' for r in records.values()),records
        summary[strand]['routing']={'assigned':result.qc.routing_assigned_reads,'quarantine':result.qc.routing_quarantined_reads}
        for key,e in result.product_evidence.items():
            products=sorted((r.sequence or '',r.count,r.intended_state) for r in e.products)
            if strand=='reverse':
                products=sorted((reverse_complement(seq),n,state) for seq,n,state in products)
            (case/(key+'_products.json')).write_text(json.dumps(products,indent=2)+'\n')
    assert summary['forward']==summary['reverse']
    for name in ('target','copy1','copy2'):
        assert (output/'forward'/(name+'_products.json')).read_bytes()==(output/'reverse'/(name+'_products.json')).read_bytes()
    def decisions(case):
        rows=[json.loads(line) for line in (output/case/'routing/routing_ledger.jsonl').read_text().splitlines()]
        return {r['read_id']:(r['category'],r['assigned_copy']) for r in rows}
    assert decisions('forward')==decisions('reverse')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('core')
    args=parser.parse_args();main(args.output,args.core)
