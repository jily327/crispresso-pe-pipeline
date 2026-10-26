"""Independent fixed-DAG force closure; imports no peanalyzer implementation."""
import argparse,itertools,re
from common import read,write,digest
FAMILIES=('demux','analysis','routing','metrics','statistics','report','all')

def graph(mode,samples,targets):
    if mode not in ('run','analyze'):raise ValueError('Unsupported source mode')
    for values in (samples,targets):
        if not values or values!=sorted(set(values)) or len({v.casefold() for v in values})!=len(values):raise ValueError('Invalid inventory')
        if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',v) for v in values):raise ValueError('Unsafe identifier')
    nodes=[]
    def add(key,kind,deps,path):nodes.append(dict(stage_id=key,stage_kind=kind,dependencies=deps,output_path=path))
    source='raw_inputs' if mode=='run' else 'external_demux'
    add(source,source,[],f'workflow/sources/{source}.json')
    if mode=='run':add('demux','demux',[source],'demux')
    add('analysis','analysis',['demux' if mode=='run' else source],'analysis')
    for kind in ('routing','metrics'):
        for s in samples:
            for t in targets:
                add(f'{kind}::{s}::{t}',kind,['analysis']+([f'routing::{s}::{t}'] if kind=='metrics' else []),f'{kind}/{s}/{t}')
    add('metrics_manifest','metrics_manifest',[n['stage_id'] for n in nodes if n['stage_kind']=='metrics'],'metrics/manifest.csv')
    add('statistics','statistics',['metrics_manifest'],'statistics');add('report','report',['statistics'],'report')
    return nodes

def closure(mode,samples,targets,families,valid_completed=()):
    families=sorted(set(families));nodes=graph(mode,samples,targets)
    if set(families)-set(FAMILIES) or (mode=='analyze' and 'demux' in families):raise ValueError('INVALID_FORCE')
    chosen={n['stage_id'] for n in nodes if n['stage_kind'] in families or 'all' in families}
    if mode=='run' and 'demux' in families:chosen.add('raw_inputs')
    # Fixed point, independent of traversal order of the implementation's loop.
    previous=None
    while previous!=chosen:
        previous=set(chosen)
        chosen|={n['stage_id'] for n in nodes if set(n['dependencies'])&chosen}
    order=[n['stage_id'] for n in nodes]
    known=set(valid_completed)
    if known-set(order):raise ValueError('Unknown completed stage')
    paths=[n['output_path'] for n in nodes if n['stage_id'] in chosen]
    manifests=['workflow/stages/'+digest(n['stage_id'])+'.json' for n in nodes if n['stage_id'] in chosen]
    return dict(requested=families,closure=[n for n in order if n in chosen],
        reuse_candidates=[n for n in order if n not in chosen],
        proven_reused=[n for n in order if n in known-chosen],
        rerun=[n for n in order if n in chosen or n not in known],
        owned_outputs=paths,owned_stage_manifests=manifests,
        completion_marker=['workflow_manifest.json'] if chosen else [])

def from_plan(plan,families,valid_completed=()):
    expected=graph(plan['mode'],plan['expected_samples'],plan['expected_targets'])
    keys=('stage_id','stage_kind','dependencies','output_path')
    if [{k:n[k] for k in keys} for n in plan['nodes']]!=expected:raise ValueError('Plan graph/path ownership is not authoritative')
    return closure(plan['mode'],plan['expected_samples'],plan['expected_targets'],families,valid_completed)

def union_owned(old,new,families):
    a=from_plan(old,families);b=from_plan(new,families)
    return {k:sorted(set(a[k])|set(b[k])) for k in ('owned_outputs','owned_stage_manifests','completion_marker')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan');p.add_argument('--force',action='append',default=[]);p.add_argument('--out',required=True)
    a=p.parse_args();write(a.out,from_plan(read(a.plan),a.force))
