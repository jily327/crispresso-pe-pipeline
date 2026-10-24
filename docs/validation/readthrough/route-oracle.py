"""Replay the starting router and compare uniquely supported tail-normalized pairs."""
import argparse,hashlib,importlib.util,json,sys
from collections import Counter
from pathlib import Path
from peanalyzer.fastq import FastqRecord,paired_fastq,read_id
from peanalyzer.geometry import geometry
from peanalyzer.routing import route_pair,RoutingPolicy
from peanalyzer.validation import load_targets
from peanalyzer.schemas import reverse_complement
p=argparse.ArgumentParser();p.add_argument('dataset');p.add_argument('root',type=Path);p.add_argument('baseline',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
spec=importlib.util.spec_from_file_location('readthrough_audited_router',a.baseline);old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
evidence=Path(__file__).resolve().parent
identity=json.loads((evidence/'input-hashes.json').read_text());ts=load_targets(Path(identity['targets_ALSW.csv']['path']));report=geometry(ts)
refs={s:(t.copy_name,state) for t in ts for state,s in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]}
manifest=json.loads((a.root/'analysis/analysis_manifest.json').read_text());summary={};tested=Counter();invariance=[]
a.output.mkdir(parents=True,exist_ok=True)
for sample,item in sorted(manifest['samples'].items()):
    counts=Counter();lengths=Counter()
    with (a.output/f'{sample}-baseline.jsonl').open('w') as f:
        for pair in paired_fastq(*(a.root/'analysis'/item['files'][f'r{m}']['path'] for m in (1,2))):
            row=old.route_pair(pair,ts,report,old.RoutingPolicy())
            counts[row['assigned_copy'] or 'quarantine']+=1
            lengths[(len(pair[0].sequence)+27,len(pair[1].sequence)+27,row['assigned_copy'] or 'quarantine')]+=1
            f.write(json.dumps([row['read_id'],row['category'],row['assigned_copy'],row['reason']],separators=(',',':'))+'\n')
            left=pair[0].sequence.decode();right=reverse_complement(pair[1].sequence.decode())
            supported=[s for s in refs if len(left)>=len(s) and len(right)>=len(s) and left.startswith(s) and right.endswith(s)]
            if len(supported)!=1:continue
            ref=supported[0];stratum=(sample,*refs[ref],len(left),len(right))
            if tested[stratum]>=3:continue
            tested[stratum]+=1
            normalized=tuple(FastqRecord(r.header,r.sequence[:len(ref)]+b'\n',r.plus,r.quality_line[:len(ref)]+b'\n') for r in pair)
            actual=route_pair(pair,ts,report,RoutingPolicy());expected=route_pair(normalized,ts,report,RoutingPolicy())
            key=lambda r:(r['category'],r['assigned_copy'])
            invariance.append(dict(id_sha256=hashlib.sha256(row['read_id'].encode()).hexdigest(),sample=sample,copy=refs[ref][0],state=refs[ref][1],prepared_lengths=[len(left),len(right)],actual=key(actual),normalized=key(expected),passed=key(actual)==key(expected)))
    summary[sample]=dict(counts=dict(counts),lengths=[dict(r1=x,r2=y,cohort=c,pairs=n) for (x,y,c),n in sorted(lengths.items())])
    print(sample,dict(counts),flush=True)
(a.output/'summary.json').write_text(json.dumps(dict(dataset=a.dataset,samples=summary,normalization_trials=invariance,normalization_failed=sum(not t['passed'] for t in invariance)),indent=2,sort_keys=True)+'\n')
assert all(t['passed'] for t in invariance)
