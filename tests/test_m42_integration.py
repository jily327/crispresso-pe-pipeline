"""Pinned production preprocessing titration and independent M4.2 regressions."""
import gzip
import json
import os
from pathlib import Path

import pytest

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.comparator import run_comparator
from peanalyzer.backend.core import run_confident_core
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.demux import demultiplex
from peanalyzer.fastq import paired_fastq
from peanalyzer.geometry import geometry
from peanalyzer.metrics import collect_metrics,run_metrics,reaggregate
from peanalyzer.metrics.production import RUNTIME_DIGEST
from peanalyzer.remediation import panel,pair,indel_designs
from peanalyzer.routing import route_analysis
from peanalyzer.schemas import Config,Target
from test_m42 import repeat_targets,tolerance_fixture

pytestmark=[pytest.mark.crispresso_integration,
            pytest.mark.skipif(os.environ.get('M42_INTEGRATION')!='1',reason='set M42_INTEGRATION=1 with pinned Core 2.3.4')]


def prepare(root,records):
    root.mkdir(parents=True,exist_ok=False)
    prefixes=('GCTTGCGTTGGAGTGAGTACGGTGTGC','CTGTGTAGTGAGTTGGATGCTGGATGG')
    for mate in (1,2):
        with gzip.open(root/f'raw_R{mate}.fastq.gz','wb') as handle:
            for records_pair in records:
                r=records_pair[mate-1]
                handle.write(r.header+prefixes[mate-1].encode()+r.sequence_line+r.plus+b'I'*27+r.quality_line)
    (root/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nsynthetic,1B,F1,RB\n')
    demultiplex(r1=root/'raw_R1.fastq.gz',r2=root/'raw_R2.fastq.gz',samples_path=root/'samples.csv',config=Config(schema_version=1),output=root/'demux')
    prepare_analysis_fastqs(root/'demux',root/'analysis')


def base_path(tmp_path):
    return Path(os.environ['M42_RESULTS_DIR']) if 'M42_RESULTS_DIR' in os.environ else tmp_path


def core():return resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso'))


@pytest.mark.parametrize('overlap',[4,8,9,10,11,12,13,16,20,28,30,32])
def test_actual_production_merge_overlap_titration(tmp_path,overlap):
    root=base_path(tmp_path)/f'titration/{overlap}'
    targets=panel()[:1];t=targets[0];records=[]
    for state,seq in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]:
        for i in range(5):records.append(pair(seq,identifier=f'control_{state}_{i}',length=150))
        for i in range(10):
            left=(len(seq)+overlap)//2;right=(len(seq)+overlap+1)//2
            records.append((pair(seq,identifier=f'probe_{state}_{i}',length=left)[0],pair(seq,identifier=f'probe_{state}_{i}',length=right)[1]))
    prepare(root,records)
    result=run_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id=f'overlap-{overlap}',output=root/'metrics',core=core())
    native=result.target_metrics.target_crispresso_native_pe
    survived=overlap>=11
    assert native.status=='REPORTABLE' and native.backend_input_reads==30
    assert native.reads_after_preprocessing==native.aligned_reads==(30 if survived else 10)
    assert native.unaligned_reads==0 and native.numerator==(15 if survived else 5)
    child=root/'metrics/comparator/copy1/output/CRISPResso_on_unrouted'
    with gzip.open(child/'out.extendedFrags.fastq.gz','rt') as h:lines=h.read().splitlines()
    headers=lines[::4]
    probe_survivors=sum('probe_' in s for s in headers);controls=sum('control_' in s for s in headers)
    assert probe_survivors==(20 if survived else 0) and controls==10
    evidence=dict(nominal_overlap=overlap,control_pairs=10,submitted_probe_pairs=20,probe_survivors=probe_survivors,
        controls_surviving=controls,native=native.model_dump(),runtime=RUNTIME_DIGEST,
        fastp_invocation=[s for s in (child/'CRISPResso_RUNNING_LOG.txt').read_text().splitlines() if s.startswith('fastp -i')])
    (root/'titration.json').write_text(json.dumps(evidence,indent=2)+'\n')


@pytest.fixture(scope='module',params=['insertion_short','insertion_long','deletion_boundary','substitution','repeat','cross_copy_lengths'])
def experiment(request,tmp_path_factory):
    root=base_path(tmp_path_factory.mktemp('m42'))/request.param
    kind=request.param;length=150
    if kind.startswith('insertion'):
        targets=next(ts for d,ts in indel_designs() if d['id']=='insertion_12_seed11')
        length=128 if kind=='insertion_short' else 150
    elif kind=='deletion_boundary':
        targets=next(ts for d,ts in indel_designs() if d['id']=='deletion_1_seed29');length=125
    elif kind=='repeat':targets,_=repeat_targets();length=180
    else:
        targets=panel()
        if kind=='substitution':length=128
        else:targets[1]=targets[1].model_copy(update={f:'ACGTA'+getattr(targets[1],f) for f in ('wt_sequence','prime_edited_sequence')})
    records=[]
    for t,n in zip(targets,[12,8]):
        for state,seq in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]:
            for i in range(n):records.append(pair(seq,identifier=f'{t.copy_name}_{state}_{i}',length=length))
    prepare(root,records);runtime={'image_digest':RUNTIME_DIGEST};engine=core()
    # Run the raw backend independently of production preflight, retaining the
    # actual selected population that the new metric guard must refuse to report.
    raw=run_comparator(root/'analysis','1B',targets,root/'comparator',engine,runtime_identity=runtime)
    routing=None;copies={}
    if geometry(targets)['status']!='BLOCKED':
        routing=root/'routing';manifest=route_analysis(root/'analysis','1B',targets,routing)
        assert manifest['categories']=={'ASSIGNED_COPY':40}
        for t in targets:
            copies[t.copy_name]=root/'copies'/t.copy_name
            run_confident_core(routing,t.copy_name,copies[t.copy_name],engine,runtime_identity=runtime)
    args=dict(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id=kind,
        comparator_root=root/'comparator',routing_root=routing,copy_roots=copies,runtime_digest=RUNTIME_DIGEST)
    result=collect_metrics(**args,tolerance_policies=[dict(policy_id=str(i),max_extra_substitutions=i) for i in (0,1,2)])
    canonical=collect_metrics(**args)
    for field in ('target_metrics','copies','qc','eligibility','anchor_evidence'):
        assert canonical.model_dump()[field]==result.model_dump()[field]
    (root/'result.json').write_text(result.model_dump_json(indent=2)+'\n')
    (root/'targets.json').write_text(json.dumps([t.model_dump() for t in targets],indent=2)+'\n')
    (root/'raw_backend.json').write_text(json.dumps(raw,indent=2)+'\n')
    return kind,root,targets,result,raw


def test_actual_state_symmetry_prevents_zero_and_one_hundred_percent_bias(experiment):
    kind,_,_,result,raw=experiment
    native=result.target_metrics.target_crispresso_native_pe;exact=result.target_metrics.total_precise_pe
    if kind in ('insertion_short','deletion_boundary'):
        assert native.status=='BLOCKED' and native.numerator is native.denominator is None
        assert 'STATE_DEPENDENT_BACKEND_MERGEABILITY' in native.reason_codes
        assert all('STATE_DEPENDENT_BACKEND_MERGEABILITY' in c.native.reason_codes and c.precise.status=='BLOCKED' for c in result.copies.values())
        expected=(0,20) if kind=='insertion_short' else (20,20)
        assert all((m['native']['numerator'],m['native']['denominator'])==expected for m in raw['backend_metrics'].values())
        if kind=='insertion_short':
            assert exact.status=='NOT_ASSESSABLE'
            assert exact.products.exclusion_reason_counts=={'STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY':40}
            assert all(r.status=='NOT_ASSESSABLE' for r in result.derived_metrics['target'].values())
        else:assert exact.status=='REPORTABLE' and (exact.numerator,exact.denominator)==(20,40)
    else:
        assert native.status==exact.status=='REPORTABLE'
        assert (native.numerator,native.denominator)==(20,40)
        assert (exact.numerator,exact.denominator)==(20,40)
        if kind!='cross_copy_lengths':assert all(c.copy_metric_status=='REPORTABLE' for c in result.copies.values())
        else:
            assert all('UNSUPPORTED_ROUTING_GEOMETRY' in c.native.reason_codes for c in result.copies.values())
            assert result.anchor_evidence['comparison']['cross_copy_length_divergence']


def test_actual_stored_evidence_reaggregates_without_backend(experiment):
    _,_,_,result,_=experiment
    for key,evidence in result.product_evidence.items():
        policies=[r.policy for r in result.derived_metrics[key].values()]
        assert reaggregate(json.loads(evidence.model_dump_json()),policies)==result.derived_metrics[key]


def test_actual_distinct_copy_lengths_with_individually_qualified_routing(tmp_path):
    root=base_path(tmp_path)/'single_copy_lengths';targets=panel()
    targets[1]=targets[1].model_copy(update={f:'ACGTA'+getattr(targets[1],f) for f in ('wt_sequence','prime_edited_sequence')})
    for t in targets:
        work=root/t.copy_name;records=[]
        for state,seq in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]:
            records.extend(pair(seq,identifier=f'{state}_{i}') for i in range(10))
        prepare(work,records);route_analysis(work/'analysis','1B',[t],work/'routing')
        result=run_metrics(analysis_root=work/'analysis',sample_id='1B',targets=[t],analysis_id=t.copy_name,
            routing_root=work/'routing',output=work/'metrics',core=core())
        assert result.copies[t.copy_name].copy_metric_status=='REPORTABLE'
        assert (result.copies[t.copy_name].precise.numerator,result.copies[t.copy_name].precise.denominator)==(10,20)


def test_actual_symmetric_extra_substitution_families(tmp_path):
    fixture=tolerance_fixture();targets=[Target.model_validate(t) for t in fixture.targets]
    root=base_path(tmp_path)/'tolerance';records=[]
    for rownum,row in enumerate(fixture.products):
        records.extend(pair(row.sequence,identifier=f'haplotype_{rownum}_{i}') for i in range(row.count))
    prepare(root,records);route_analysis(root/'analysis','1B',targets,root/'routing')
    result=run_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id='tolerance',
        routing_root=root/'routing',output=root/'metrics',core=core(),
        tolerance_policies=[dict(policy_id=str(i),max_extra_substitutions=i) for i in (0,1,2)])
    for key in ('target','copy1'):
        values=result.derived_metrics[key]
        assert [(r.wt_family,r.pe_family,r.denominator) for r in values.values()]==[(1000,300,1300),(1030,330,1360),(1035,335,1370)]
    assert (result.target_metrics.total_precise_pe.numerator,result.target_metrics.total_precise_pe.denominator)==(300,1300)
    assert (result.copies['copy1'].precise.numerator,result.copies['copy1'].precise.denominator)==(300,1300)


def test_actual_deletion_exact_boundary_cannot_report_selected_one_hundred_percent(tmp_path):
    targets=next(ts for d,ts in indel_designs() if d['id']=='deletion_1_seed29')
    root=base_path(tmp_path)/'deletion_exact_boundary';records=[]
    for target,n in zip(targets,[12,8]):
        for state,seq in [('WT',target.wt_sequence),('PE',target.prime_edited_sequence)]:
            for i in range(n):
                identifier=f'{target.copy_name}_{state}_{i}'
                records.append((pair(seq,identifier=identifier,length=124)[0],pair(seq,identifier=identifier,length=125)[1]))
    prepare(root,records);route_analysis(root/'analysis','1B',targets,root/'routing')
    result=run_metrics(analysis_root=root/'analysis',sample_id='1B',targets=targets,analysis_id='deletion-exact-boundary',
        routing_root=root/'routing',output=root/'metrics',core=core(),
        tolerance_policies=[dict(policy_id='tolerant',max_extra_substitutions=2)])
    exact=result.target_metrics.total_precise_pe
    assert exact.status=='NOT_ASSESSABLE' and exact.numerator is exact.denominator is None
    assert exact.products.exclusion_reason_counts=={'STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY':40}
    assert result.target_metrics.target_crispresso_native_pe.status=='BLOCKED'
    assert all(c.native.status==c.precise.status=='BLOCKED' for c in result.copies.values())
    assert result.derived_metrics['target']['tolerant'].status=='NOT_ASSESSABLE'
    (root/'targets.json').write_text(json.dumps([t.model_dump() for t in targets],indent=2)+'\n')
