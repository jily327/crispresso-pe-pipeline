"""Boundary-normalization check on the newly assigned AmpSeq >=290-nt raw class."""
import json,hashlib
from pathlib import Path
from peanalyzer.fastq import paired_fastq,read_id,FastqRecord
from peanalyzer.geometry import geometry,aligner
from peanalyzer.routing import RoutingPolicy,route_pair
from peanalyzer.schemas import reverse_complement
from peanalyzer.validation import load_targets
out=Path(__file__).resolve().parent;root=Path('/workspace/validation/readthrough/AmpSeq-final')
inputs=json.loads((out/'input-hashes.json').read_text());ts=load_targets(Path(inputs['targets_ALSW.csv']['path']));g=geometry(ts)
manifest=json.loads((root/'analysis/analysis_manifest.json').read_text());rows=[]
for sample,item in manifest['samples'].items():
    ledger=(root/f'routing/{sample}/ALSW/routing_ledger.jsonl').open()
    for line,pair in zip(ledger,paired_fastq(*(root/'analysis'/item['files'][f'r{m}']['path'] for m in (1,2)))):
        row=json.loads(line)
        if not row['assigned_copy'] or max(len(r.sequence)+27 for r in pair)<290:continue
        lengths=[];bounds=[];raw_bounds=[];indeterminate=[]
        for mate,r in enumerate(pair,1):
            seq=r.sequence.decode();seq=reverse_complement(seq) if mate==2 else seq
            candidates=set()
            for t in ts:
                for ref in (t.wt_sequence,t.prime_edited_sequence):
                    alns=aligner(reads=True).align(ref,seq)
                    if len(alns)>16:continue
                    for aln in alns:
                        ref_blocks,query_blocks=aln.aligned
                        if ref_blocks[0,0]==0 and ref_blocks[-1,1]==len(ref):
                            candidates.add((int(query_blocks[0,0]),int(query_blocks[-1,1])))
            if len(candidates)!=1:
                indeterminate.append(dict(mate=mate,candidate_bounds=sorted(candidates)))
                continue
            lo,hi=next(iter(candidates))
            raw_bounds.append((lo,hi) if mate==1 else (len(seq)-hi,len(seq)-lo))
            lengths.append(hi-lo);bounds.append([lo,hi])
        if indeterminate:
            rows.append(dict(sample=sample,id_sha256=hashlib.sha256(row['read_id'].encode()).hexdigest(),normalization='NOT_ESTABLISHED',reason='optimal full-reference placements do not establish one boundary',details=indeterminate,assigned_copy=row['assigned_copy']))
            continue
        normalized=tuple(FastqRecord(r.header,r.sequence[lo:hi]+b'\n',r.plus,r.quality_line[lo:hi]+b'\n') for r,(lo,hi) in zip(pair,raw_bounds))
        decision=route_pair(normalized,ts,g,RoutingPolicy())
        assert (decision['category'],decision['assigned_copy'])==(row['category'],row['assigned_copy'])
        rows.append(dict(sample=sample,id_sha256=hashlib.sha256(row['read_id'].encode()).hexdigest(),prepared_lengths=[len(r.sequence) for r in pair],biological_query_bounds=bounds,raw_query_bounds=raw_bounds,normalized_lengths=lengths,assigned_copy=row['assigned_copy'],decision_equal=True))
assert len(rows)==7
(out/'AmpSeq-long-class-normalization.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(dict(long_class_assigned=len(rows),normalization_established=sum(r.get('decision_equal',False) for r in rows),normalization_indeterminate=sum(r.get('normalization')=='NOT_ESTABLISHED' for r in rows))))
