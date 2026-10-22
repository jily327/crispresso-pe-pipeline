"""Collect M4.2 text artifacts and independently replay stored products.

Run after complete source and installed-wheel suites. Historical evidence is read
only. Synthetic faults are labelled separately from actual backend executions.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import types
import xml.etree.ElementTree as ET
import zipfile

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'tests'))
from peanalyzer.fastq import paired_fastq
from peanalyzer.metrics import reaggregate,aggregate_family
from peanalyzer.observability import assess_pair
from peanalyzer.remediation import panel,pair,qualify_indels
from peanalyzer.schemas import Target
from test_m42 import tolerance_fixture,distance_fixture,evidence_for,mutate,repeat_targets
from test_m4 import collect as offline_collect

spec=importlib.util.spec_from_file_location('m41_collector',REPO/'docs/validation/m41/collect_evidence.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
read,write,summary,child_evidence=prior.read,prior.write,prior.summary,prior.child_evidence
BASE='2ce80b259e8a8630392363f6559b9de2666699ff'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def scientific(value):
    if isinstance(value,dict):
        return {k:scientific(v) for k,v in value.items() if k not in ('population_id',)}
    if isinstance(value,list):return [scientific(v) for v in value]
    return value


def fields(result):
    return {k:result[k] for k in ('target_metrics','copies','qc','eligibility','derived_metrics')}


def copy_backend(root,dest):
    for execution in root.rglob('execution.json'):
        path=dest/execution.relative_to(root);path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(execution,path)
    for info in root.rglob('CRISPResso2_info.json'):
        child_evidence(info.parent,dest/info.parent.relative_to(root))


def reconcile(records,targets,parent):
    groups=Counter()
    for records_pair in records:
        old=parent.exact_pair_class(records_pair,targets);new=assess_pair(records_pair,targets)
        groups[tuple(r.sequence.decode() for r in records_pair),old,new['canonical'],new['reason']]+=1
    rows=[dict(mates=list(mates),count=n,previous=old,current=new,reason=reason,
               previous_numerator=int(old=='exact_PE')*n,previous_denominator=int(old in ('exact_WT','exact_PE'))*n,
               current_numerator=int(new=='exact_PE')*n,current_denominator=int(new in ('exact_WT','exact_PE'))*n)
          for (mates,old,new,reason),n in sorted(groups.items(),key=lambda x:repr(x[0]))]
    return dict(input=sum(groups.values()),changed=sum(r['count'] for r in rows if r['previous']!=r['current']),
        previous_fraction=[sum(r['previous_numerator'] for r in rows),sum(r['previous_denominator'] for r in rows)],
        current_fraction=[sum(r['current_numerator'] for r in rows),sum(r['current_denominator'] for r in rows)],haplotypes=rows)


def prepared(root):
    manifest=read(root/'analysis/analysis_manifest.json')
    return paired_fastq(*(root/'analysis'/manifest['samples']['1B']['files'][f'r{i}']['path'] for i in (1,2)))


def main():
    parser=argparse.ArgumentParser()
    for name in ('source','wheel','pytest-root','dist'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();out=Path(__file__).resolve().parent
    source=args.source/'m42';wheel=args.wheel/'m42'
    # Exact parent code is executed only for independent before/after diagnosis.
    parent=types.ModuleType('m41_parent_metrics')
    exec(subprocess.check_output(['git','show',f'{BASE}:src/peanalyzer/backend/metrics.py'],cwd=REPO,text=True),parent.__dict__)
    result_paths=sorted(source.rglob('result.json'));parity={};experiments={}
    for path in result_paths:
        rel=path.relative_to(source);result=read(path);other=read(wheel/rel)
        assert scientific(fields(result))==scientific(fields(other))
        parity[str(rel)]=dict(equal=True,compared='canonical and derived records, QC and eligibility; population hashes excluded')
        write(out/'actual'/rel,result)
        if 'titration' not in str(rel):experiments[str(rel)]=fields(result)
    for name in ('targets.json','raw_backend.json','titration.json'):
        for path in source.rglob(name):write(out/'actual'/path.relative_to(source),read(path))
    copy_backend(source,out/'actual')
    titration=[read(source/f'titration/{n}/titration.json') for n in (4,8,9,10,11,12,13,16,20,28,30,32)]
    assert all(r['probe_survivors']==(20 if r['nominal_overlap']>=11 else 0) for r in titration)
    write(out/'merge-titration.json',dict(exact_minimum_overlap=10,empirical_backend_minimum_overlap=11,
        qualification='Perfect high-quality end mates through production Core; 10 independent long-overlap controls per point',points=titration))
    write(out/'real-backend-regressions.json',experiments)
    biased={}
    for kind in ('insertion_short','deletion_boundary'):
        biased[kind]={}
        for copy,size in [('copy1',24),('copy2',16)]:
            parsed=prior.parse_child(source/kind/'copies'/copy/'output/CRISPResso_on_confident',
                routed_pairs=size,one_input_record_per_pair=True)
            expected=(0,size//2) if kind=='insertion_short' else (size//2,size//2)
            assert (parsed['native']['numerator'],parsed['native']['denominator'])==expected
            biased[kind][copy]=parsed
    write(out/'raw-biased-copy-diagnostics.json',dict(scope='Raw diagnostics only; production metrics are BLOCKED',experiments=biased))
    reconciliations={}
    for kind in ('insertion_short','insertion_long','deletion_boundary','deletion_exact_boundary','substitution','repeat','cross_copy_lengths'):
        root=source/kind;targets=[Target.model_validate(t) for t in read(root/'targets.json')]
        reconciliations[kind]=reconcile(prepared(root),targets,parent)
    historical={}
    for kind in ('m3','m31'):
        root=args.source/'m4'/kind;result=read(root/'m4/result.json')
        historical[kind]=fields(result);write(out/'historical'/kind/'result.json',result)
        reconciliations['historical_'+kind]=reconcile(prepared(root),panel(),parent)
        assert reconciliations['historical_'+kind]['changed']==0
        assert scientific(fields(result))==scientific(fields(read(args.wheel/'m4'/kind/'m4/result.json')))
    write(out/'historical-regression.json',historical)
    closed={}
    for kind in ('ambiguous','preprocessing','nonexact_only','routing_blocked'):
        root=args.source/'m41'/kind
        closed[kind]=fields(read(root/'metrics/result.json'))
        assert scientific(closed[kind])==scientific(fields(read(args.wheel/'m41'/kind/'metrics/result.json')))
        # Preserve the new raw run, including discard and actual exit failures.
        copy_backend(root,out/'m41-closed'/kind)
        for path in root.rglob('result.json'):write(out/'m41-closed'/kind/path.relative_to(root),read(path))
    write(out/'m41-closed-findings.json',closed)
    pooled={}
    for copy,n in [('copy1',211),('copy2',139)]:
        child=args.source/f'm3/baseline/backend/output/CRISPRessoPooled_on_diagnostic/CRISPResso_on_SYN_{copy}'
        pooled[copy]=prior.parse_child(child,routed_pairs=n,one_input_record_per_pair=True)
        child_evidence(child,out/'historical/pooled'/copy)
    write(out/'historical-pooled.json',dict(scope='Regression only; unqualified production copy population',metrics=pooled))
    for motif,units,expanded in [('CAG',4,7),('CA',5,9)]:
        t=panel()[0];prefix=t.wt_sequence[:100];suffix=t.wt_sequence[170:]
        wt=prefix+motif*units+suffix;t=t.model_copy(update={'wt_sequence':wt,'prime_edited_sequence':mutate(wt,55)})
        records=[]
        for pe in (False,True):
            physical=prefix+motif*expanded+suffix
            if pe:physical=mutate(physical,55)
            records.append((pair(physical,length=len(prefix)+len(motif)*units)[0],pair(physical,length=len(suffix)+len(motif)*units)[1]))
        reconciliations['periodic_'+motif]=dict(targets=[t.model_dump()],**reconcile(records,[t],parent))
    targets,start=repeat_targets();records=[]
    for t in targets:
        for seq in (t.wt_sequence,t.prime_edited_sequence):
            records.append((pair(seq,length=start+8)[0],pair(seq,length=len(seq)-start)[1]))
    reconciliations['same_repeat_references_shortened']=dict(targets=[t.model_dump() for t in targets],**reconcile(records,targets,parent))
    write(out/'classification-reconciliation.json',dict(parent=BASE,cases=reconciliations))
    policies=[dict(policy_id=str(i),max_extra_substitutions=i) for i in (0,1,2)]
    fixture=tolerance_fixture()
    position=[dict(policy_id='position-'+str(p),max_extra_substitutions=2,allowed_extra_substitution_positions=p) for p in ([149],[179],[])]
    write(out/'family-policies.json',dict(evidence=fixture.model_dump(),results={k:v.model_dump() for k,v in reaggregate(fixture,policies+position).items()}))
    invalid=[{'max_extra_substitutions':-1},{'max_extra_substitutions':1.0},
        {'max_extra_substitutions':True},{'max_extra_indel_events':1},
        {'max_extra_indel_events':False},{'allowed_extra_substitution_positions':[999]},
        {'allowed_extra_substitution_positions':[False]},{'min_haplotype_count':2}]
    failures=[]
    for i,policy in enumerate(invalid):
        result=aggregate_family(fixture,dict(policy_id=f'invalid-{i}',**policy))
        assert result.status=='BLOCKED' and result.reason_codes==['UNSUPPORTED_TOLERANCE_POLICY']
        failures.append(result.model_dump())
    write(out/'unsupported-policy-matrix.json',failures)
    targets,seq=distance_fixture();distance={}
    for kind,observed in [('unequal',seq),('tie',mutate(seq,119,'T'))]:
        evidence=evidence_for(targets,[(observed,7)])
        distance[kind]=dict(evidence=evidence.model_dump(),results={k:v.model_dump() for k,v in reaggregate(evidence,[dict(policy_id=str(n),max_extra_substitutions=n) for n in range(5)]).items()})
    write(out/'minimum-family-distance.json',distance)
    # Replay real aggregate evidence with several policies, without a backend.
    replay={}
    for path in result_paths:
        result=read(path)
        for key,evidence in result['product_evidence'].items():
            selected=result['derived_metrics'].get(key)
            if selected:
                actual={k:v.model_dump() for k,v in reaggregate(evidence,[v['policy'] for v in selected.values()]).items()}
                assert actual==selected
                replay[str(path.relative_to(source))+'::'+key]=dict(equal=True,evidence_sha256=digest(evidence))
    write(out/'stored-reaggregation.json',replay)
    # The tests compare complete canonical structures with/without policies. Run
    # the same check again over the verified historical all-prepared population.
    root=args.source/'m4/m31'
    original=prior.collect(root);selected=prior.collect(root,tolerance_policies=policies)
    canonical_fields=('target_metrics','copies','qc','eligibility','anchor_evidence','product_evidence')
    independence={}
    for key in canonical_fields:
        assert original[key]==selected[key]
        independence[key]=dict(no_policy_sha256=digest(original[key]),selected_sha256=digest(selected[key]),equal=True)
    write(out/'canonical-policy-independence.json',independence)
    failures=[]
    for path in sorted(args.pytest_root.glob('test_execution_reason_contract*')):
        if path.is_symlink() or not (path/'run').exists():continue
        root=path/'run';result=offline_collect(root)
        raw=read(root/'comparator/copy2/execution.json')['reason_code']
        failures.append(dict(evidence_kind='Controlled execution-manifest fault injection',raw_reason=raw,
            target_metrics=result.target_metrics.model_dump()))
    assert len(failures)==8;write(out/'reason-code-attack-matrix.json',failures)
    path=next(p for p in args.pytest_root.glob('test_anchor_partitions_are_per*') if not p.is_symlink())/'run'
    partition=offline_collect(path).model_dump()
    write(out/'anchor-partition-divergence.json',dict(evidence_kind='Coherent controlled JSON, quantification and allele-table perturbation',
        target_metrics=partition['target_metrics'],comparison=partition['anchor_evidence']['comparison']))
    copy_backend(path,out/'anchor-partition-artifacts')
    grid=qualify_indels();assert len(grid)==36 and sum(r['geometry_status']=='BLOCKED' for r in grid)==23
    write(out/'indel-grid.json',grid)
    tests={}
    for label,base in [('source',args.source),('wheel',args.wheel)]:
        xml=ET.parse(str(base)+'-tests.xml');cases=xml.findall('.//testcase')
        tests[label]=dict(tests=len(cases),failures=len(xml.findall('.//failure')),errors=len(xml.findall('.//error')),
            skipped=len(xml.findall('.//skipped')),actual_backend_tests=sum('integration' in c.attrib['classname'] for c in cases),
            cases=[dict(**c.attrib,passed=not list(c)) for c in cases])
        assert tests[label]['tests']==619 and tests[label]['actual_backend_tests']==55
        assert tests[label]['failures']==tests[label]['errors']==tests[label]['skipped']==0
        shutil.copyfile(str(base)+'-tests.txt',out/f'{label}-tests.txt')
    write(out/'test-results.json',tests);write(out/'wheel-regression-parity.json',parity)
    inspect=json.loads(subprocess.check_output(['docker','image','inspect',prior.RUNTIME_DIGEST],text=True))[0]
    container=json.loads(subprocess.check_output(['docker','inspect','m311-runtime'],text=True))[0]
    assert container['Image']==inspect['Id'] and prior.RUNTIME_DIGEST in inspect['RepoDigests']
    write(out/'runtime.json',dict(image_digest=prior.RUNTIME_DIGEST,image_id=inspect['Id'],container_image_id=container['Image'],
        wrappers={n:Path('/workspace/m311-tools',n).read_text() for n in ('CRISPResso','CRISPRessoPooled','samtools')},
        version_probes={n:subprocess.check_output(['/workspace/m311-tools/'+n,'--version'],text=True).splitlines()[:3]
                        for n in ('CRISPResso','CRISPRessoPooled','samtools')},
        fastp_version=subprocess.check_output(['docker','exec','m311-runtime','/CRISPResso2/.pixi/envs/default/bin/fastp','--version'],stderr=subprocess.STDOUT,text=True).strip()))
    with zipfile.ZipFile(next(args.dist.glob('*.whl'))) as z:
        write(out/'tested-wheel-payload.json',{n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/RECORD')})
    write(out/'gate.json',dict(status='PASS',parent=BASE,unchanged_main='550df70f9f9627c7218b9f047d0b6bf3023b8d25',
        version='0.4.2',source_tests=619,wheel_tests=619,actual_backend_tests_per_environment=55,
        geometry=dict(total=36,allowed=13,blocked=23),historical_evidence_untouched=True,
        routing_geometry_unchanged=True,correctness_and_tolerance_same_milestone=True))


if __name__=='__main__':main()
