"""Retain all prior cases and enumerate scientific differences explicitly."""
import argparse,importlib.util,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from peanalyzer.remediation import panel,qualify_indels

def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def science(v):
    if isinstance(v,dict):return {k:science(x) for k,x in v.items() if k!='population_id'}
    if isinstance(v,list):return [science(x) for x in v]
    return v

def suite(root):
    t=ET.parse(root/'tests.xml');cases=[c.attrib['classname']+'::'+c.attrib['name'] for c in t.findall('.//testcase')]
    counts=dict(tests=len(cases),failures=len(t.findall('.//failure')),errors=len(t.findall('.//error')),skips=len(t.findall('.//skipped')))
    assert not any(counts[k] for k in ('failures','errors','skips'))
    return counts,set(cases)

def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();out=Path(__file__).resolve().parent
    baseline=Path('/workspace/validation/m7/source-final');old,oldcases=suite(baseline)
    results={};parity={};changes=[];documentation_changes=[]
    fields=('target_metrics','copies','qc','eligibility','derived_metrics','product_evidence')
    for label in ('source','wheel'):
        root=a.root/(label+'-final');counts,cases=suite(root)
        assert oldcases<=cases and old['tests']==1036
        counts.update(prior_retained=len(oldcases),new_targeted=len(cases-oldcases),integration=sum('integration' in c.split('::')[0] for c in cases))
        results[label]=counts
        results[label]['m5_m51_cases']=sum(c.split('::')[0].split('.')[-1] in ('test_m5','test_m51') for c in cases)
        results[label]['m6_m61_cases']=sum(c.split('::')[0].split('.')[-1] in ('test_m6','test_m61') for c in cases)
        (out/(label+'-tests.txt')).write_text((root/'tests.txt').read_text())
        for stage in ('m4','m41','m42','m421','m422'):
            for path in sorted((baseline/stage).rglob('result.json')):
                rel=path.relative_to(baseline);x,y=read(path),read(root/rel)
                before=science({k:x.get(k) for k in fields});after=science({k:y.get(k) for k in fields})
                old_text=before['qc']['limitations'][3];new_text=after['qc']['limitations'][3]
                assert new_text==old_text.replace('; internal fragments', '; uniquely supported exact reference products may exclude terminal read-through (0.7.1); internal fragments')
                documentation_changes.append(dict(environment=label,result=str(rel),field='qc.limitations[3]',before=old_text,after=new_text))
                after['qc']['limitations'][3]=old_text
                parity.setdefault(str(rel),{})[label]=before==after
                if before!=after:changes.append(dict(environment=label,result=str(rel),before=before,after=after))
    assert len(parity)==42
    write(out/'implementation-provenance-text-changes.json',documentation_changes);write(out/'test-results.json',results);write(out/'m4-result-parity.json',parity);write(out/'historical-result-changes.json',changes)
    repo=out.parents[2];sys.path.insert(0,str(repo/'tests'))
    spec=importlib.util.spec_from_file_location('readthrough_historical_helpers',repo/'docs/validation/m422/collect_evidence.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    replay={kind:helpers.reconcile(helpers.prepared(baseline/'m4'/kind),panel()) for kind in ('m3','m31')}
    assert sum(r['input'] for r in replay.values())==475
    write(out/'historical-classifications.json',{k:{x:y for x,y in v.items() if x!='haplotypes'} for k,v in replay.items()})
    grid=qualify_indels();assert len(grid)==36 and sum(r['geometry_status']!='BLOCKED' for r in grid)==13
    write(out/'geometry-grid.json',grid)
    assert not changes,[(r['environment'],r['result']) for r in changes]
    assert all(v['changed']==0 for v in replay.values())
    print(json.dumps(dict(tests=results,results_compared=len(parity),historical_classifications=475,changed=0,geometry=[36,13,23])))
if __name__=='__main__':main()
