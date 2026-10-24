"""Compare every replayed baseline routing decision with final production ledger."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
from itertools import zip_longest
from peanalyzer.fastq import paired_fastq,read_id
p=argparse.ArgumentParser();p.add_argument('dataset');p.add_argument('root',type=Path);p.add_argument('oracle',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
manifest=json.loads((a.root/'analysis/analysis_manifest.json').read_text());results={}
for sample,item in sorted(manifest['samples'].items()):
    transitions=Counter();changed_lengths=Counter();before=Counter();after=Counter();long_before=Counter();long_after=Counter();changed_digest=hashlib.sha256();n=0
    with (a.oracle/f'{sample}-baseline.jsonl').open() as old,(a.root/f'routing/{sample}/ALSW/routing_ledger.jsonl').open() as new:
        for x,y,pair in zip_longest(old,new,paired_fastq(*(a.root/'analysis'/item['files'][f'r{m}']['path'] for m in (1,2)))):
            assert x and y and pair
            x=json.loads(x);y=json.loads(y);assert x[0]==y['read_id']==read_id(pair[0],1).decode();n+=1
            prev=(x[1],x[2]);now=(y['category'],y['assigned_copy']);before[x[2] or 'quarantine']+=1;after[y['assigned_copy'] or 'quarantine']+=1
            raw_lengths=tuple(len(r.sequence)+27 for r in pair)
            if max(raw_lengths)>=290:
                long_before[x[2] or 'quarantine']+=1;long_after[y['assigned_copy'] or 'quarantine']+=1
            if prev!=now:
                transitions[str(prev)+' -> '+str(now)]+=1;changed_lengths[str(raw_lengths)]+=1;changed_digest.update((x[0]+'\n').encode())
    results[sample]=dict(input_pairs=n,before=dict(before),after=dict(after),classification_transitions=dict(transitions),changed_pairs=sum(transitions.values()),changed_ids_sha256=changed_digest.hexdigest(),changed_raw_lengths=dict(changed_lengths),raw_mate_at_least_290_before=dict(long_before),raw_mate_at_least_290_after=dict(long_after))
normalization=json.loads((a.oracle/'summary.json').read_text())
a.output.write_text(json.dumps(dict(dataset=a.dataset,samples=results,normalization_trials=normalization['normalization_trials'],normalization_failures=normalization['normalization_failed']),indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(dataset=a.dataset,input_pairs=sum(v['input_pairs'] for v in results.values()),changed_pairs=sum(v['changed_pairs'] for v in results.values()),assigned=sum(sum(n for k,n in v['after'].items() if k!='quarantine') for v in results.values()),normalization_trials=len(normalization['normalization_trials']))))
