import json,hashlib
from pathlib import Path
from peanalyzer.fastq import paired_fastq,read_id
from peanalyzer.validation import load_targets
from peanalyzer.geometry import geometry,aligner,columns
from peanalyzer.routing import reference_span_identity,deletion_ambiguity_candidate,RoutingPolicy
from peanalyzer.schemas import reverse_complement
root=Path('/workspace/validation/readthrough/AmpSeq-final');baseline=Path('/workspace/validation/readthrough/AmpSeq-routing-oracle')
inputs=json.load(open('docs/validation/readthrough/input-hashes.json'));ts=load_targets(Path(inputs['targets_ALSW.csv']['path']));manifest=json.load(open(root/'analysis/analysis_manifest.json'))
losses=[]
for sample,item in manifest['samples'].items():
 wanted={}
 with (baseline/f'{sample}-baseline.jsonl').open() as f,(root/f'routing/{sample}/ALSW/routing_ledger.jsonl').open() as g:
  for x,y in zip(f,g):
   x=json.loads(x);y=json.loads(y)
   if x[2] and not y['assigned_copy']:wanted[x[0]]=(x,y)
 for pair in paired_fastq(*(root/'analysis'/item['files'][f'r{m}']['path'] for m in (1,2))):
  rid=read_id(pair[0],1).decode()
  if rid not in wanted:continue
  old,new=wanted[rid];details=[]
  for mate,r in enumerate(pair,1):
   seq=r.sequence.decode();seq=reverse_complement(seq) if mate==2 else seq
   for t in ts:
    for state,ref in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]:
     matches=aligner(reads=True).align(ref,seq)
     for aln in list(matches)[:16]:
      cols=columns(aln);oldidentity=sum(a is not None and b is not None and ref[a]==seq[b] for a,b in cols)/len(seq)
      identity=reference_span_identity(ref,seq,aln)
      details.append(dict(mate=mate,copy=t.copy_name,state=state,old_identity=oldidentity,reference_span_identity=identity,ambiguity_witness=identity<.8 and deletion_ambiguity_candidate(ref,seq,cols,RoutingPolicy()),coordinates=aln.coordinates.tolist()))
  losses.append(dict(sample=sample,id_sha256=hashlib.sha256(rid.encode()).hexdigest(),before=old[1:],after={k:new[k] for k in ('category','assigned_copy','reason','alignments')},placements=details))
Path('docs/validation/readthrough/AmpSeq-conservative-losses.json').write_text(json.dumps(losses,indent=2)+'\n')
for loss in losses:
 print(loss['sample'],loss['after']['reason'])
 for p in loss['placements']:
  if p['ambiguity_witness'] or (p['old_identity']>=.8)!=(p['reference_span_identity']>=.8):print(p)
