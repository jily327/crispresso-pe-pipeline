"""Retest the previously disclosed 42-nt deletion using the current identity helper."""
import hashlib,json
from pathlib import Path
from peanalyzer.fastq import paired_fastq,read_id
from peanalyzer.geometry import geometry,aligner
from peanalyzer.routing import route_pair,RoutingPolicy,reference_span_identity
from peanalyzer.schemas import Target,reverse_complement
out=Path(__file__).resolve().parent
loss=json.loads((out.parents[0]/'readthrough/AmpSeq-conservative-losses.json').read_text())[0]
root=Path('/workspace/validation/readthrough/AmpSeq-final');sample=loss['sample']
manifest=json.loads((root/'analysis/analysis_manifest.json').read_text());item=manifest['samples'][sample]
route=json.loads((root/f'routing/{sample}/ALSW/routing_manifest.json').read_text());targets=[Target.model_validate(t) for t in route['targets']]
for pair in paired_fastq(*(root/'analysis'/item['files'][f'r{m}']['path'] for m in (1,2))):
    if hashlib.sha256(read_id(pair[0],1)).hexdigest()!=loss['id_sha256']:continue
    result=route_pair(pair,targets,geometry(targets),RoutingPolicy());assert result['category']=='ALIGNMENT_FAILURE' and result['assigned_copy'] is None
    target=next(t for t in targets if t.copy_name=='chr01g24880');identities=[]
    for mate,record in enumerate(pair,1):
        sequence=record.sequence.decode();sequence=reverse_complement(sequence) if mate==2 else sequence
        values=[reference_span_identity(target.wt_sequence,sequence,a) for a in aligner(reads=True).align(target.wt_sequence,sequence)]
        assert values and all(x==168/211 and x<RoutingPolicy().min_alignment_identity for x in values)
        identities.append(dict(mate=mate,WT_reference_span_identities=values))
    evidence=dict(sample=sample,id_sha256=loss['id_sha256'],category=result['category'],assigned_copy=result['assigned_copy'],reason=result['reason'],threshold=0.8,chr01_WT_placement_identities=identities)
    (out/'internal-deletion-parity.json').write_text(json.dumps(evidence,indent=2)+'\n');print('42-nt deletion remains quarantined; identity 168/211 =',168/211);break
else:raise AssertionError('Previously recorded deletion molecule not found')
