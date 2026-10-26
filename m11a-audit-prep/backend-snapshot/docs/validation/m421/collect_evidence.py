"""Portable M4.2.1 evidence collection from explicit source/wheel result roots.

No transient pytest archive, Git parent checkout or named existing container is
required. Historical evidence is read only. All count diagnoses are regenerated.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'tests'))
from peanalyzer.fastq import paired_fastq
from peanalyzer.metrics import collect_metrics,reaggregate
from peanalyzer.metrics.policy_requests import prepare_policies
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.observability import assess_pair
from peanalyzer.remediation import panel,qualify_indels
from peanalyzer.schemas import Target,reverse_complement
from peanalyzer.backend.metrics import parse_child
from test_m421 import policy_cases,periodic_case,canonical
from test_m42 import tolerance_fixture


def read(path):return json.loads(path.read_text())


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def scientific(value):
    if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k!='population_id'}
    if isinstance(value,list):return [scientific(v) for v in value]
    return value


spec=importlib.util.spec_from_file_location('audited_m42_observability',Path(__file__).with_name('audited_observability.py'))
audited=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audited)


def audited_class(records,targets):
    """Replay the committed verbatim audited source snapshot, without Git access."""
    return audited.assess_pair(records,targets)['canonical']


def prepared(root):
    manifest=read(root/'analysis/analysis_manifest.json')
    return paired_fastq(*(root/'analysis'/manifest['samples']['1B']['files'][f'r{m}']['path'] for m in (1,2)))


def reconcile(records,targets):
    groups=Counter()
    for pair in records:
        previous=audited_class(pair,targets);current=assess_pair(pair,targets)
        groups[tuple(p.sequence.decode() for p in pair),previous,current['canonical'],current['reason']]+=1
    rows=[dict(mates=list(mates),count=n,previous=previous,current=current,reason=reason,
               previous_numerator=n*int(previous=='exact_PE'),previous_denominator=n*int(previous in ('exact_WT','exact_PE')),
               current_numerator=n*int(current=='exact_PE'),current_denominator=n*int(current in ('exact_WT','exact_PE')))
          for (mates,previous,current,reason),n in sorted(groups.items(),key=lambda item:repr(item[0]))]
    return dict(input=sum(groups.values()),changed=sum(r['count'] for r in rows if r['previous']!=r['current']),
        previous_fraction=[sum(r['previous_numerator'] for r in rows),sum(r['previous_denominator'] for r in rows)],
        current_fraction=[sum(r['current_numerator'] for r in rows),sum(r['current_denominator'] for r in rows)],haplotypes=rows)


def child_evidence(child,dest):
    info=read(child/'CRISPResso2_info.json');running=info['running_info'];dest.mkdir(parents=True,exist_ok=True)
    for name in ('CRISPResso2_info.json',running['mapping_stats_filename'],running['quant_of_editing_freq_filename']):
        shutil.copyfile(child/name,dest/name)
    with zipfile.ZipFile(child/running['allele_frequency_table_zip_filename']) as archive:
        (dest/'alleles.txt').write_bytes(archive.read(running['allele_frequency_table_filename']))


def main():
    parser=argparse.ArgumentParser()
    for name in ('source','wheel','dist','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--runtime-container',help='Optional actual container identity; any caller-supplied name')
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    source=args.source/'m421';wheel=args.wheel/'m421'
    parity={};experiments={};reconciliation={}
    for path in sorted(source.rglob('result.json')):
        rel=path.relative_to(source);result=read(path);other=read(wheel/rel)
        fields=('target_metrics','copies','qc','eligibility','derived_metrics')
        assert scientific({k:result[k] for k in fields})==scientific({k:other[k] for k in fields})
        parity[str(rel)]=dict(equal=True,compared=list(fields),ignored=['population_id'])
        write(out/'actual'/rel,result)
        experiments[str(rel)]={k:result[k] for k in fields}
    for name in ('targets.json','raw_backend.json'):
        for path in source.rglob(name):write(out/'actual'/path.relative_to(source),read(path))
    for path in source.rglob('execution.json'):
        dest=out/'actual'/path.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    for info in source.rglob('CRISPResso2_info.json'):
        child_evidence(info.parent,out/'actual'/info.parent.relative_to(source))
    for name in ('cross_copy_150_150','cross_copy_125_125','cross_copy_124_125','copy_specific_repeat'):
        root=source/name;targets=[Target.model_validate(t) for t in read(root/'targets.json')]
        reconciliation[name]=reconcile(prepared(root),targets)
    assert reconciliation['cross_copy_150_150']['current_fraction']==[20,40]
    assert reconciliation['cross_copy_125_125']['current_fraction']==[20,40]
    assert reconciliation['cross_copy_124_125']['previous_fraction']==[18,20]
    assert reconciliation['cross_copy_124_125']['current_fraction']==[0,0]
    assert reconciliation['copy_specific_repeat']['previous_fraction']==[2,20]
    assert reconciliation['copy_specific_repeat']['current_fraction']==[0,0]
    write(out/'cross-copy-results.json',experiments)
    write(out/'wheel-parity.json',parity)
    root=args.source/'m4/m31'
    collect_args=dict(analysis_root=root/'analysis',sample_id='1B',targets=panel(),analysis_id='policy-validation',
        comparator_root=root/'m4/comparator',routing_root=root/'routing',
        copy_roots={c:root/'m4/copies'/c for c in ('copy1','copy2')},runtime_digest=RUNTIME_DIGEST)
    baseline=collect_metrics(**collect_args);base=canonical(baseline)
    matrix={};independence={}
    for name,policies in policy_cases()+[('top_integer',7),('top_bool',True),('top_string','bad'),('top_dict',{})]:
        result=collect_metrics(**collect_args,tolerance_policies=policies)
        assert canonical(result)==base
        matrix[name]=dict(requests=policies,canonical_equal=True,
            target={k:v.model_dump() for k,v in result.derived_metrics.get('target',{}).items()})
        independence[name]={k:dict(baseline_sha256=digest(base[k]),requested_sha256=digest(canonical(result)[k]),equal=True) for k in base}
        for key,evidence in result.product_evidence.items():
            if result.derived_metrics:assert reaggregate(evidence,policies)==result.derived_metrics[key]
    write(out/'policy-validation-matrix.json',matrix);write(out/'canonical-policy-independence.json',independence)
    write(out/'policy-execution-order.json',dict(evidence_kind='Assertions in the complete passing source and wheel tests',
        test='test_m421.test_run_metrics_prevalidates_before_canonical_work_and_publishes',
        asserted_order=['policy_validation','canonical_collection','backend_launch','result.json publication'],
        actual_publication_cases=[str(p.relative_to(source)) for p in source.glob('cross_copy_*/production/result.json')]))
    # A separate process sees serialized aggregate evidence, never input FASTQs.
    fixture=tolerance_fixture();policies=[{},None,dict(policy_id='same'),dict(policy_id='same'),dict(policy_id='valid',max_extra_substitutions=1)]
    request=dict(evidence=fixture.model_dump(),policies=policies)
    code="import json,sys; from peanalyzer.metrics import reaggregate; r=json.load(sys.stdin); print(json.dumps({k:v.model_dump() for k,v in reaggregate(r['evidence'],r['policies']).items()}))"
    replay=json.loads(subprocess.check_output([sys.executable,'-c',code],input=json.dumps(request),text=True))
    assert replay=={k:v.model_dump() for k,v in reaggregate(fixture,policies).items()}
    write(out/'clean-process-reaggregation.json',dict(request=request,results=replay,equal=True,fastq_or_backend_access=False))
    periodic=[]
    for period in range(1,11):
        for direction in ('expansion','contraction'):
            for state in ('WT','PE'):
                target,records=periodic_case(period,direction,state)
                row=reconcile([records],[target]);assert row['current_fraction']==[0,0]
                controls={}
                from peanalyzer.remediation import pair
                for label,sequence in [('exact_WT',target.wt_sequence),('exact_PE',target.prime_edited_sequence)]:
                    control=(pair(sequence,length=len(sequence)-50)[0],pair(sequence,length=len(sequence)-80)[1])
                    actual=assess_pair(control,[target]);assert actual['canonical']==label
                    controls[label]=dict(mates=[r.sequence.decode() for r in control],assessment=actual)
                periodic.append(dict(period=period,direction=direction,state=state,target=target.model_dump(),
                    reconciliation=row,informative_flank_controls=controls))
    write(out/'periodic-grid.json',dict(cases=periodic,ambiguous_cases=40,all_current_nonexact=True,
        positive_control_classifications=80,all_positive_controls_exact=True,alternative_overlap_minimum=4))
    historical={}
    for kind in ('m3','m31'):
        root=args.source/'m4'/kind;result=read(root/'m4/result.json')
        historical[kind]={k:result[k] for k in ('target_metrics','copies','qc')}
        reconciliation['historical_'+kind]=reconcile(prepared(root),panel())
        assert reconciliation['historical_'+kind]['changed']==0
        other=read(args.wheel/'m4'/kind/'m4/result.json')
        assert scientific(historical[kind])==scientific({k:other[k] for k in historical[kind]})
    pooled={}
    for copy,n in [('copy1',211),('copy2',139)]:
        child=args.source/f'm3/baseline/backend/output/CRISPRessoPooled_on_diagnostic/CRISPResso_on_SYN_{copy}'
        pooled[copy]=parse_child(child,routed_pairs=n,one_input_record_per_pair=True)
    write(out/'historical-regression.json',dict(production=historical,pooled_diagnostic_only=pooled))
    write(out/'classification-reconciliation.json',dict(audited_parent='db49e23f0881bed35a24747587275463949c764d',
        previous_classifier='Verbatim audited source snapshot: audited_observability.py',
        previous_source_sha256=hashlib.sha256(Path(__file__).with_name('audited_observability.py').read_bytes()).hexdigest(),cases=reconciliation))
    grid=qualify_indels();assert len(grid)==36 and sum(r['geometry_status']=='BLOCKED' for r in grid)==23
    write(out/'geometry-grid.json',grid)
    preserved={}
    for stage,kinds in [('m41',('ambiguous','preprocessing','nonexact_only','routing_blocked')),
                        ('m42',('insertion_short','insertion_long','deletion_boundary','substitution','repeat','cross_copy_lengths'))]:
        for kind in kinds:
            relative=Path(stage)/kind/('metrics/result.json' if stage=='m41' else 'result.json')
            result=read(args.source/relative);other=read(args.wheel/relative)
            fields=('target_metrics','copies','qc','eligibility','derived_metrics')
            assert scientific({k:result[k] for k in fields})==scientific({k:other[k] for k in fields})
            preserved[str(relative)]={k:result[k] for k in fields}
    tolerance=read(args.source/'m42/tolerance/metrics/result.json')
    for key in ('target','copy1'):
        assert [(r['numerator'],r['denominator']) for r in tolerance['derived_metrics'][key].values()]==[(300,1300),(330,1360),(335,1370)]
    write(out/'preserved-closures.json',preserved);write(out/'preserved-tolerance.json',tolerance)
    tests={}
    for label,root in [('source',args.source),('wheel',args.wheel)]:
        xml=ET.parse(root/'tests.xml');cases=xml.findall('.//testcase')
        integration=[c for c in cases if 'integration' in c.attrib['classname']]
        # The repeat preflight test deliberately prevents backend launch; count
        # it separately instead of inflating the actual backend execution count.
        preflight=[c for c in integration if c.attrib['name']=='test_actual_copy_specific_repeat_excludes_target_length_class']
        tests[label]=dict(tests=len(cases),failures=len(xml.findall('.//failure')),errors=len(xml.findall('.//error')),
            skipped=len(xml.findall('.//skipped')),integration_cases=len(integration),preflight_only_cases=len(preflight),
            actual_backend_test_cases=len(integration)-len(preflight),cases=[dict(**c.attrib,passed=not list(c)) for c in cases])
        assert tests[label]['tests']==698 and len(integration)==59 and len(preflight)==1
        assert tests[label]['failures']==tests[label]['errors']==tests[label]['skipped']==0
        shutil.copyfile(root/'tests.txt',out/f'{label}-tests.txt')
    write(out/'test-results.json',tests)
    runtime=dict(required_image=RUNTIME_DIGEST,tools={})
    for name,variable in [('CRISPResso','M3_CORE_EXECUTABLE'),('CRISPRessoPooled','M3_POOLED_EXECUTABLE'),('samtools','M3_SAMTOOLS_EXECUTABLE')]:
        executable=os.environ.get(variable) or shutil.which(name)
        if not executable:raise ValueError(f'Set {variable} or provide {name} on PATH')
        runtime['tools'][name]=dict(executable=executable,version=subprocess.check_output([executable,'--version'],text=True).splitlines()[:3])
    if args.runtime_container:
        inspected=read_json_command(['docker','inspect',args.runtime_container])[0]
        image=read_json_command(['docker','image','inspect',RUNTIME_DIGEST])[0]
        assert inspected['Image']==image['Id'] and RUNTIME_DIGEST in image['RepoDigests']
        runtime.update(container=args.runtime_container,image_id=image['Id'],container_image_id=inspected['Image'])
    write(out/'runtime.json',runtime)
    with zipfile.ZipFile(next(args.dist.glob('*.whl'))) as archive:
        write(out/'tested-wheel-payload.json',{n:hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if not n.endswith('/RECORD')})
    write(out/'gate.json',dict(status='PASS',parent='db49e23f0881bed35a24747587275463949c764d',
        unchanged_main='550df70f9f9627c7218b9f047d0b6bf3023b8d25',version='0.4.3',source_tests=698,wheel_tests=698,
        integration_cases_per_environment=59,actual_backend_test_cases_per_environment=58,preflight_only_cases_per_environment=1,
        new_a='CLOSED',new_b='CLOSED',periodic_residual='CLOSED_FOR_QUALIFIED_PERIOD_1_THROUGH_10_GRID',
        historical_classifications_unchanged=475,geometry=dict(total=36,allowed=13,blocked=23)))


def read_json_command(argv):return json.loads(subprocess.check_output(argv,text=True))


if __name__=='__main__':main()
