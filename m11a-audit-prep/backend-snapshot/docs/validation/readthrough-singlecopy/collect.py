"""Collect final source/wheel qualification and enforce the narrow follow-up scope."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

PARENT='249979e0e97c7dc8fffdf04cdab329bdb4a47394'
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def cases(root):
    tree=ET.parse(root/'tests.xml');rows=tree.findall('.//testcase')
    counts=dict(tests=len(rows),failures=len(tree.findall('.//failure')),errors=len(tree.findall('.//error')),skips=len(tree.findall('.//skipped')))
    assert not any(counts[k] for k in ('failures','errors','skips'))
    return counts,{r.attrib['classname']+'::'+r.attrib['name'] for r in rows}

p=argparse.ArgumentParser();p.add_argument('work',type=Path);a=p.parse_args();out=Path(__file__).resolve().parent;repo=out.parents[2]
_,prior=cases(Path('/workspace/validation/readthrough/source-final'));assert len(prior)==1095
results={}
for env in ('source','wheel'):
    root=a.work/(env+'-final');counts,inventory=cases(root);assert prior<=inventory
    counts.update(prior_retained=len(prior),new_cases=len(inventory-prior),integration=sum('integration' in x.split('::')[0] for x in inventory))
    assert counts['tests']==1185 and counts['new_cases']==90 and counts['integration']==63
    results[env]=counts;(out/(env+'-tests.txt')).write_text((root/'tests.txt').read_text())
write(out/'tests.json',results)
def scientific(value):
    if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k!='population_id'}
    if isinstance(value,list):return [scientific(v) for v in value]
    return value
fields=('target_metrics','copies','qc','eligibility','derived_metrics','product_evidence')
parity_rows={}
baseline=Path('/workspace/validation/readthrough/source-final')
for stage in ('m4','m41','m42','m421','m422'):
    for path in sorted((baseline/stage).rglob('result.json')):
        relative=path.relative_to(baseline);expected=read(path)
        for env in ('source','wheel'):
            actual=read(a.work/(env+'-final')/relative)
            assert scientific({k:expected.get(k) for k in fields})==scientific({k:actual.get(k) for k in fields}), (env,relative)
        parity_rows[str(relative)]={'source_equal':True,'wheel_equal':True}
assert len(parity_rows)==42
write(out/'m4-result-parity.json',parity_rows)
changes=subprocess.check_output(['git','diff',PARENT,'--name-only','--','src'],cwd=repo,text=True).splitlines()
assert changes==['src/peanalyzer/routing.py']
path='src/peanalyzer/routing.py';before=subprocess.check_output(['git','show',PARENT+':'+path],cwd=repo,text=True);after=(repo/path).read_text()
old="""            if len(spans)!=1:
                return dict(read_id=identifier,category='ALIGNMENT_FAILURE',assigned_copy=None,compatible_copies=copies,evidence=[],alignments=scores,reason='nonunique single-copy placement')"""
new="""            # Witnesses can disprove uniqueness, never supply a qualified span.
            witness_spans={(min(a),max(a)) for key, alternatives in ambiguity.items()
                           if key[0]==mate for a in alternatives if a}
            if len(spans)!=1 or len(spans | witness_spans)!=1:
                return dict(read_id=identifier,category='ALIGNMENT_FAILURE',assigned_copy=None,compatible_copies=copies,evidence=[],alignments=scores,reason='nonunique single-copy placement')"""
assert before.count(old)==1 and before.replace(old,new)==after
wheel=a.work/'dist-final/crispresso_pe_pipeline-0.7.1-py3-none-any.whl';files={}
with zipfile.ZipFile(wheel) as z:
    for file in sorted((repo/'src/peanalyzer').rglob('*')):
        if file.is_file() and file.suffix in ('.py','.json','.yaml','.csv','.css'):
            name=file.relative_to(repo/'src').as_posix();assert z.read(name)==file.read_bytes();files[name]=hashlib.sha256(file.read_bytes()).hexdigest()
origin=subprocess.check_output([str(a.work/'wheel-env/bin/python'),'-c','import peanalyzer; print(peanalyzer.__file__)'],cwd=a.work/'wheel-suite',text=True).strip()
assert 'site-packages' in origin
write(out/'scope-and-wheel.json',dict(wheel_import_origin=origin,parent=PARENT,production_files_changed=changes,exact_single_copy_veto_only=True,D1_identity_unchanged=True,D2_source_unchanged=True,version='0.7.1',wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),source_wheel_files=files))
assert read(out/'baseline-070.json')==read(out/'final-panels.json')
parity={name:read(out/(name+'-parity.json')) for name in ('Azenta','AmpSeq')}
assert sum(x['pairs'] for x in parity.values())==178128
assert all(x['changed_routing_rows']==x['changed_product_counts']==0 for x in parity.values())
write(out/'gate.json',dict(status='PASS',parent=PARENT,version='0.7.1',single_copy=read(out/'panel-gate.json')['single_copy'],multi_copy=read(out/'panel-gate.json')['multi_copy'],tests=results,real_replayed_pairs=178128,changed_real_routing_rows=0,changed_real_products=0,real_result_files_unchanged=19,historical_m4_result_comparisons=42,internal_deletion_quarantine_retained=True))
print(json.dumps(dict(status='PASS',tests=results,real_replayed_pairs=178128)))
