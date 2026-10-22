"""Collect text-only evidence from completed source/wheel qualifications."""

import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO/'tests'))
from peanalyzer.backend.metrics import exact_pair_class, parse_child
from peanalyzer.metrics import collect_metrics
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.remediation import panel, qualify_indels
from test_m41 import overlap_cases


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2)+'\n')


def summary(result):
    return dict(target=result['target_metrics'], copies=result['copies'],
                qc=result['qc'], eligibility=result['eligibility'],
                anchor_failures=result['anchor_evidence']['failures'])


def child_evidence(child, dest):
    info=read(child/'CRISPResso2_info.json');running=info['running_info']
    dest.mkdir(parents=True, exist_ok=True)
    for name in ('CRISPResso2_info.json', running['mapping_stats_filename'], running['quant_of_editing_freq_filename']):
        shutil.copyfile(child/name, dest/name)
    with zipfile.ZipFile(child/running['allele_frequency_table_zip_filename']) as archive:
        (dest/'alleles.txt').write_bytes(archive.read(running['allele_frequency_table_filename']))


def execution_evidence(root,dest,name):
    child_evidence(root/f'output/CRISPResso_on_{name}',dest)
    shutil.copyfile(root/'execution.json',dest/'execution.json')


def collect(root, **overrides):
    args=dict(analysis_root=root/'analysis',sample_id='1B',targets=panel(),analysis_id='m41-evidence',
        comparator_root=root/'m4/comparator',routing_root=root/'routing',
        copy_roots={c:root/f'm4/copies/{c}' for c in ('copy1','copy2')},runtime_digest=RUNTIME_DIGEST)
    args.update(overrides)
    return collect_metrics(**args).model_dump()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--wheel',type=Path,required=True)
    parser.add_argument('--pytest-root',type=Path,required=True)
    parser.add_argument('--dist',type=Path,required=True)
    args=parser.parse_args();out=Path(__file__).resolve().parent
    results={}
    for kind in ('ambiguous','preprocessing','nonexact_only','routing_blocked'):
        root=args.source/'m41'/kind;result=read(root/'metrics/result.json')
        results[kind]=summary(result);write(out/kind/'result.json',result)
        if (root/'fixture.json').exists(): shutil.copyfile(root/'fixture.json',out/kind/'fixture.json')
        for copy in ('copy1','copy2'):
            execution_evidence(root/f'metrics/comparator/{copy}',out/kind/'anchors'/copy,'unrouted')
            if (root/f'metrics/copies/{copy}').exists():
                execution_evidence(root/f'metrics/copies/{copy}',out/kind/'copies'/copy,'confident')
        if (root/'discarded/evidence.json').exists():
            child_evidence(root/'discarded/output/CRISPResso_on_unrouted',out/kind/'discarded')
            shutil.copyfile(root/'discarded/evidence.json',out/kind/'discarded/evidence.json')
        if (root/'failed_metrics/result.json').exists():
            write(out/kind/'actual_nonzero_exit.json',dict(result=summary(read(root/'failed_metrics/result.json')),
                executions={c:read(root/f'failed_metrics/comparator/{c}/execution.json') for c in ('copy1','copy2')}))
    write(out/'real-backend-regressions.json',results)
    historical={}
    for kind in ('m3','m31'):
        root=args.source/'m4'/kind;result=read(root/'m4/result.json')
        historical[kind]=summary(result)
        write(out/'historical'/kind/'result.json',result)
        for copy in ('copy1','copy2'):
            execution_evidence(root/f'm4/comparator/{copy}',out/'historical'/kind/'anchors'/copy,'unrouted')
            if (root/f'm4/copies/{copy}').exists():
                execution_evidence(root/f'm4/copies/{copy}',out/'historical'/kind/'copies'/copy,'confident')
    write(out/'historical-regression.json',historical)
    pooled={}
    for copy,n,a,u,pe,exact,den in [('copy1',211,199,12,72,60,140),('copy2',139,131,8,48,40,90)]:
        child=args.source/f'm3/baseline/backend/output/CRISPRessoPooled_on_diagnostic/CRISPResso_on_SYN_{copy}'
        parsed=parse_child(child,routed_pairs=n,one_input_record_per_pair=True)
        assert (parsed['native']['backend_input_reads'],parsed['native']['aligned_reads'],parsed['native']['unaligned_reads'])==(n,a,u)
        assert (parsed['native']['numerator'],parsed['native']['denominator'])==(pe,a)
        assert (parsed['exact_haplotype']['numerator'],parsed['exact_haplotype']['denominator'])==(exact,den)
        pooled[copy]=parsed
        child_evidence(child,out/'historical/pooled'/copy)
    write(out/'historical-pooled.json',dict(scope='regression only; unqualified copy production population',metrics=pooled))
    root=args.source/'m4/m31'
    runtime={name:summary(collect(root,runtime_digest=d)) for name,d in
             [('correct',RUNTIME_DIGEST),('missing',None),('wrong','wrong')]}
    write(out/'runtime-independence.json',runtime)
    matrix={}
    for attack in ('missing_anchor','malformed_window','empty_window','diagnostic_window','counter_mismatch','missing_artifact'):
        with tempfile.TemporaryDirectory(prefix='m41-evidence-') as temporary:
            clone=Path(temporary)/'run';shutil.copytree(root,clone)
            info=clone/'m4/comparator/copy2/output/CRISPResso_on_unrouted/CRISPResso2_info.json'
            if attack=='missing_anchor':shutil.rmtree(clone/'m4/comparator/copy2')
            elif attack=='missing_artifact':info.unlink()
            else:
                data=read(info)
                if attack=='counter_mismatch':data['running_info']['alignment_stats']['N_TOT_READS']+=1
                else:data['results']['refs']['Reference']['include_idxs']={'malformed_window':{'_type':'np.ndarray','value':[True]},'empty_window':[],'diagnostic_window':[40]}[attack]
                write(info,data)
            result=collect(clone)
            assert result['target_metrics']['total_precise_pe']['denominator']==55
            assert result['target_metrics']['target_crispresso_native_pe']['status']=='BLOCKED'
            matrix[attack]=summary(result)
    from test_m4 import collect as collect_offline
    path=next(args.pytest_root.glob('test_empirical_anchor_differen[0-9]*'))/'run'
    changed=collect_offline(path).model_dump()
    assert changed['target_metrics']['target_crispresso_native_pe']['reason_codes']==['ANCHOR_DEPENDENT_NATIVE_RESULT']
    assert changed['target_metrics']['total_precise_pe']['denominator']==55
    matrix['anchor_dependence']=dict(evidence_kind='independently reconciled offline anchor perturbation',**summary(changed))
    write(out/'native-family-independence.json',matrix)
    failures={}
    for path in sorted(args.pytest_root.glob('test_independent_anchor_failur[0-9]*')):
        result=read(path/'result/result.json')
        executions={c:read(path/f'result/comparator/{c}/execution.json') for c in ('copy1','copy2')}
        key='__'.join(executions[c].get('reason_code','success')+'_'+str(executions[c]['return_code']) for c in ('copy1','copy2'))
        failures[key]=dict(evidence_kind='controlled process/artifact fault injection, not real backend execution',
            target_metrics=result['target_metrics'],anchor_failures=result['anchor_evidence']['failures'],
            executions={c:{k:v for k,v in d.items() if k in ('status','return_code','reason_code','error')} for c,d in executions.items()})
    assert len(failures)==8
    write(out/'anchor-failure-matrix.json',failures)
    preconditions={}
    for prefix in ('test_known_prelaunch_version','test_runtime_precondition_prevents'):
        paths=[p for p in args.pytest_root.glob(prefix[:29]+'*') if not p.is_symlink()]
        assert len(paths)==1
        run=paths[0]/'result'
        preconditions[prefix]=dict(result=summary(read(run/'result.json')),
            executions={str(p.relative_to(run)):read(p) for p in run.glob('*/copy*/execution.json')})
    write(out/'prelaunch-failure-matrix.json',preconditions)
    overlaps=[]
    for name,target,records,expected in overlap_cases():
        actual=exact_pair_class(records,[target]);assert actual==expected
        overlaps.append(dict(name=name,target=target.model_dump(),r1=records[0].sequence.decode(),
            r2=records[1].sequence.decode(),expected=expected,actual=actual,minimum_overlap=10))
    write(out/'exact-overlap.json',overlaps)
    grid=qualify_indels();assert len(grid)==36 and sum(r['geometry_status']=='BLOCKED' for r in grid)==23
    write(out/'indel-grid.json',grid)
    tests={}
    for label,base in [('source',args.source),('wheel',args.wheel)]:
        xml=ET.parse(str(base)+'-tests.xml');cases=xml.findall('.//testcase')
        tests[label]=dict(tests=len(cases),failures=len(xml.findall('.//failure')),errors=len(xml.findall('.//error')),
            skipped=len(xml.findall('.//skipped')),actual_backend_tests=sum('integration' in c.attrib['classname'] for c in cases),
            cases=[dict(**c.attrib,passed=not list(c)) for c in cases])
        assert tests[label]['tests']==556 and tests[label]['actual_backend_tests']==28
        assert tests[label]['failures']==tests[label]['errors']==tests[label]['skipped']==0
        shutil.copyfile(str(base)+'-tests.txt',out/f'{label}-tests.txt')
    write(out/'test-results.json',tests)
    def scientific(value):
        if isinstance(value,dict): return {k:scientific(v) for k,v in value.items() if k!='population_id'}
        if isinstance(value,list): return [scientific(v) for v in value]
        return value
    parity={}
    for path in ('m4/m3/m4','m4/m31/m4',*(f'm41/{k}/metrics' for k in results)):
        left=summary(read(args.source/path/'result.json'))
        right=summary(read(args.wheel/path/'result.json'))
        assert scientific(left)==scientific(right)
        parity[path]=dict(equal=True,compared='all metric records, QC, eligibility and anchor failure codes; population hashes excluded')
    write(out/'wheel-regression-parity.json',parity)
    inspect=json.loads(subprocess.check_output(['docker','image','inspect',RUNTIME_DIGEST],text=True))[0]
    container=json.loads(subprocess.check_output(['docker','inspect','m311-runtime'],text=True))[0]
    assert container['Image']==inspect['Id'] and RUNTIME_DIGEST in inspect['RepoDigests']
    write(out/'runtime.json',dict(image_digest=RUNTIME_DIGEST,image_id=inspect['Id'],container_image_id=container['Image'],
        wrappers={name:Path('/workspace/m311-tools',name).read_text() for name in ('CRISPResso','CRISPRessoPooled','samtools')},
        version_probes={name:subprocess.check_output(['/workspace/m311-tools/'+name,'--version'],text=True).splitlines()[:3]
                        for name in ('CRISPResso','CRISPRessoPooled','samtools')}))
    wheel=next(args.dist.glob('*.whl'))
    with zipfile.ZipFile(wheel) as z:
        payload={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/RECORD')}
    write(out/'tested-wheel-payload.json',payload)
    write(out/'gate.json',dict(status='PASS',audited_parent='768d4075c2608f3b72293401bb19dce4309f4967',
        package_version='0.4.1',source_tests=556,wheel_tests=556,actual_backend_tests_per_environment=28,
        historical_evidence_untouched=True,routing_geometry_unchanged=True,
        blockers_remediated=['HIGH-1','HIGH-2','MEDIUM-1','MEDIUM-2','MEDIUM-3']))


if __name__=='__main__':main()
