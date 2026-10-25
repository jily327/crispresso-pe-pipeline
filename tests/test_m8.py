"""Mode isolation, explicit windows, TIGR geometry and authoritative counts."""
import csv
import io
import json
from pathlib import Path
import shutil
import zipfile

import pytest
from pydantic import ValidationError
from m8_fixtures import target,WT,fixture
from peanalyzer.nuclease.targets import NucleaseTarget,intervals,tigr_geometry
from peanalyzer.nuclease.models import allele,aggregate,NucleaseMetricResult
from peanalyzer.nuclease.backend import parse_nuclease_child,run_nuclease_metrics
from peanalyzer.schemas import Target,reverse_complement
from peanalyzer.validation import load_targets
from peanalyzer import workflow as w

EVIDENCE=Path(__file__).resolve().parents[1]/'docs/validation/m81/allele-probe'


@pytest.mark.parametrize('text',['0','','1','-1-2','4-3','1-4_4-5','8-9_2-3','0-240','240-240','1-2__4-5','1.0-2','1-2x'])
def test_invalid_nuclease_windows(text):
    with pytest.raises(ValueError):intervals(text,240)


@pytest.mark.parametrize('text,expected',[('0-0',[[0,0]]),('239-239',[[239,239]]),('0-1_238-239',[[0,1],[238,239]]),('001-002',[[1,2]])])
def test_inclusive_window_boundaries(text,expected):
    assert intervals(text,240)==expected
    row=target(nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates=text)
    assert row.window['intervals']==expected


@pytest.mark.parametrize('orientation',['forward','reverse','palindromic'])
@pytest.mark.parametrize('start',[0,3,20,40])
@pytest.mark.parametrize('window',['W1','W2','W3','W4'])
def test_tigr_physical_coordinates(orientation,start,window):
    seq='ACGTCAGTACGATCGATC' if orientation!='palindromic' else 'ACGTACGTATACGTACGT'
    assert len(seq)==18
    physical=reverse_complement(seq) if orientation=='reverse' else seq
    wt='G'*start+physical+'T'*(40-start)
    g=tigr_geometry(wt,seq,window)
    assert g['orientation']==orientation and g['target_start']==start
    assert g['physical_nick_boundaries']==[[start+4,start+5],[start+12,start+13]]
    expected={'W1':[[start+4,start+5],[start+12,start+13]],'W2':[[start+4,start+13]],
              'W3':[[start,start+17]],'W4':[[max(0,start-10),min(len(wt)-1,start+27)]]}
    assert g['intervals']==expected[window]
    assert g['target_oriented_nick_labels']==({'forward':['5|6','13|14'],'reverse':['13|14','5|6'],'palindromic':None}[orientation])
    if orientation=='palindromic':assert g['target_oriented_between_cuts'] is None


@pytest.mark.parametrize('problem',['missing','duplicate','length','profile_missing','both_windows','pe_field','implicit_mode','unknown_mode','legacy_insertions'])
def test_nuclease_target_rejects_unsupported_definitions(problem):
    d=target().model_dump()
    if problem=='missing':d['tigr_target_sequence']='A'*18
    elif problem=='duplicate':d['wt_sequence']+=d['tigr_target_sequence']
    elif problem=='length':d['tigr_target_sequence']=d['tigr_target_sequence'][:-1]
    elif problem=='profile_missing':d['nuclease_profile']=None
    elif problem=='both_windows':d['quantification_window_coordinates']='100-110'
    elif problem=='pe_field':d['prime_edited_sequence']=WT
    elif problem=='implicit_mode':del d['analysis_mode']
    elif problem=='unknown_mode':d['analysis_mode']='other'
    else:d['insertion_quantification_mode']='legacy'
    with pytest.raises(ValueError):NucleaseTarget.model_validate(d)


def test_legacy_pe_default_and_serialization_remain_unchanged():
    from peanalyzer.backend.synthetic import design
    original=design()['targets'][0]
    before=Target.model_validate(original)
    assert before.analysis_mode=='precise_edit'
    assert 'analysis_mode' not in before.model_dump()
    assert Target.model_validate(dict(original,analysis_mode='precise_edit')).model_dump()==before.model_dump()
    with pytest.raises(ValidationError):Target.model_validate(dict(original,analysis_mode='indel_nuclease'))
    with pytest.raises(ValidationError):Target.model_validate(dict(original,prime_edited_sequence=original['wt_sequence']))


def test_qwc_normalization_and_identity():
    a=target(nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates='010-020')
    b=target(nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates='10-20')
    c=target(nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates='10-21')
    assert a.scientific_identity==b.scientific_identity!=c.scientific_identity
    assert target().tigr_window=='W2'


@pytest.fixture
def archive(tmp_path):
    root=tmp_path/'child';shutil.copytree(EVIDENCE,root)
    return root


def change_rows(root,fn):
    path=root/'Alleles_frequency_table.zip'
    with zipfile.ZipFile(path) as z:
        name=z.namelist()[0];reader=csv.DictReader(io.StringIO(z.read(name).decode()),delimiter='\t');fields=reader.fieldnames;rows=list(reader)
    fn(rows,fields)
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields,delimiter='\t');writer.writeheader();writer.writerows(rows)
    with zipfile.ZipFile(path,'w') as z:z.writestr(name,stream.getvalue())


@pytest.mark.parametrize('attack',['below','above','negative','decimal','missing','read_status','reference','sequence_length','nan_percentage','unknown_reference','mapping','version','window'])
def test_authoritative_artifact_fail_closed(archive,attack):
    def mutate(rows,fields):
        r=rows[0]
        if attack in ('below','above'):r['#Reads']=str(int(r['#Reads'])+(-1 if attack=='below' else 1))
        elif attack=='negative':r['n_deleted']='-1'
        elif attack=='decimal':r['#Reads']='2.5'
        elif attack=='missing':fields.remove('n_mutated');[x.pop('n_mutated') for x in rows]
        elif attack=='read_status':r['Read_Status']='UNKNOWN'
        elif attack=='reference':r['Reference_Name']='Prime-edited'
        elif attack=='sequence_length':r['Aligned_Sequence']+='A'
        elif attack=='nan_percentage':r['%Reads']='NaN'
        elif attack=='unknown_reference':r['Reference_Name']='DISCARDED_Unknown'
    if attack in ('mapping','version','window'):
        p=archive/'CRISPResso2_info.json';data=json.loads(p.read_text())
        if attack=='mapping':data['running_info']['alignment_stats']['N_TOT_READS']+=1
        elif attack=='version':data['running_info']['version']='2.3.5'
        else:data['results']['refs']['Reference']['include_idxs']=[100]
        p.write_text(json.dumps(data))
    else:change_rows(archive,mutate)
    with pytest.raises((ValueError,KeyError)):parse_nuclease_child(archive,target(),20)


@pytest.mark.parametrize('total',['99.9','100.1','87.0'])
def test_rounded_percentages_never_define_counts(archive,total):
    def mutate(rows,fields):
        for row in rows:row['%Reads']=str(float(total)/len(rows))
    change_rows(archive,mutate)
    result=parse_nuclease_child(archive,target(),20)
    assert result['metrics']['indel_fraction'].model_dump()==dict(numerator=10,denominator=20,fraction=0.5)


def test_allele_partition_and_overlapping_memberships():
    original=NucleaseMetricResult.model_validate_json((EVIDENCE/'result.json').read_bytes())
    row=original.alleles[0].authoritative_fields
    rows=[]
    for ins,dele,sub in [(0,0,0),(0,0,1),(1,0,0),(0,2,0),(1,2,0),(1,1,1)]:
        r=dict(row,**{'#Reads':'7','n_inserted':str(ins),'n_deleted':str(dele),'n_mutated':str(sub),
            'Read_Status':'MODIFIED' if ins+dele+sub else 'UNMODIFIED'})
        r.update(insertion_positions='[108, 109]' if ins else '[]',insertion_coordinates='[(108, 109)]' if ins else '[]',
            insertion_sizes=str([ins]) if ins else '[]',deletion_positions=str(list(range(105,105+dele))),
            deletion_coordinates=str([(105,105+dele)]) if dele else '[]',deletion_sizes=str([dele]) if dele else '[]',
            substitution_positions='[112]' if sub else '[]',substitution_values="['A']" if sub else '[]')
        rows.append(allele(r))
    counts,metrics,sizes=aggregate(rows,42)
    assert sum(counts.values())==42
    assert metrics['indel_fraction'].numerator==28
    assert metrics['insertion_and_deletion_containing_fraction'].numerator==14
    assert metrics['substitution_only_fraction'].numerator==7
    assert metrics['substitution_containing_fraction'].numerator==14
    assert sizes['0'].numerator==7 and sizes['0'].denominator==28


@pytest.mark.parametrize('attack',['count','fraction','size','mode','window','runtime','boolean_schema','extra'])
def test_strict_nuclease_result_contract(attack):
    d=json.loads((EVIDENCE/'result.json').read_text())
    if attack=='count':d['aligned_reads']+=1
    elif attack=='fraction':d['metrics']['indel_fraction']['fraction']=0.2
    elif attack=='size':d['fraction_of_indel_reads_by_net_size']['1']['numerator']+=1
    elif attack=='mode':d['analysis_mode']='precise_edit'
    elif attack=='window':d['target']['tigr_window']='W1'
    elif attack=='runtime':d['provenance']['runtime_digest']='unknown'
    elif attack=='boolean_schema':d['schema_version']=True
    else:d['extra']=True
    with pytest.raises((ValueError,KeyError)):NucleaseMetricResult.model_validate(d)


def fake_core(tmp_path):
    p=tmp_path/'core';p.write_text('#!/bin/sh\nprintf "CRISPResso 2.3.4\\n"\n');p.chmod(0o755);return str(p)


def test_nuclease_plan_resolves_full_scientific_identity(tmp_path):
    options=fixture(tmp_path/'inputs');options['crispresso']=fake_core(tmp_path)
    plan=w.build_workflow_plan(**options)
    assert plan.normalized_options['analysis_modes']==['indel_nuclease']
    assert plan.normalized_options['scientific_configuration'][0]['resolved_window']['coordinates']=='104-113'
    metrics=next(n for n in plan.nodes if n.stage_kind=='metrics')
    assert w.parameters_for(plan,metrics)['targets'][0]['analysis_mode']=='indel_nuclease'
    assert w._expected(plan,metrics,{})['api_call']=='run_nuclease_metrics'


def test_multicopy_nuclease_rejected_before_execution(tmp_path,monkeypatch):
    from m7_fixtures import write_csv
    options=fixture(tmp_path/'inputs');options['crispresso']=fake_core(tmp_path)
    rows=[target(),target(copy_name='copy2',wt_sequence='A'+WT[1:])]
    write_csv(options['targets'],list(rows[0].model_dump()),[t.model_dump() for t in rows])
    for name in ('demultiplex','route_analysis','run_metrics','run_nuclease_metrics'):
        monkeypatch.setattr(w,name,lambda **k:pytest.fail('execution on unsupported multi-copy panel'))
    with pytest.raises(w.WorkflowError,match='MULTICOPY_NUCLEASE_UNSUPPORTED'):w.execute_workflow(**options)
    assert not options['output'].exists()


def test_mode_switch_rejected_even_force_all(tmp_path):
    from m7_fixtures import fixture as pe_fixture
    old=fixture(tmp_path/'nuclease');old['crispresso']=fake_core(tmp_path);a=w.build_workflow_plan(**old)
    pe=pe_fixture(tmp_path/'pe',samples=4,copies=1);pe['crispresso']=old['crispresso'];pe['output']=old['output'];b=w.build_workflow_plan(**pe)
    for x,y in ((a,b),(b,a)):
        with pytest.raises(w.WorkflowError,match='ANALYSIS_MODE_MISMATCH'):w._graph_change(x,y,['all'])


@pytest.mark.parametrize('flag',['ignore_substitutions','ignore_insertions','ignore_deletions','use_legacy_insertion_quantification','expand_ambiguous_alignments'])
def test_backend_scientific_flags_are_verified(archive,flag):
    p=archive/'CRISPResso2_info.json';data=json.loads(p.read_text());data['running_info']['args']['value'][flag]=True;p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='UNQUALIFIED_NUCLEASE_CONFIGURATION'):parse_nuclease_child(archive,target(),20)


@pytest.mark.parametrize('field,value',[('insertion_sizes','garbage'),('deletion_sizes','[True]'),('substitution_values','["x"]'),('ref_positions','{}'),('insertion_coordinates','[(1, 3)]')])
def test_malformed_authoritative_event_fields(archive,field,value):
    change_rows(archive,lambda rows,fields:rows[0].update({field:value}))
    with pytest.raises(ValueError):parse_nuclease_child(archive,target(),20)


@pytest.mark.parametrize('kind',['ambiguous','discarded'])
def test_explicit_exceptional_aligned_population(archive,kind):
    # An explicit exceptional row is not reclassified or silently removed.
    data=json.loads((archive/'CRISPResso2_info.json').read_text())
    with zipfile.ZipFile(archive/'Alleles_frequency_table.zip') as z:
        rows=list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode()),delimiter='\t'))
    count=int(rows[0]['#Reads']);status=rows[0]['Read_Status']
    change_rows(archive,lambda rows,fields:rows[0].update(Reference_Name=kind.upper()+'_Reference'))
    data['results']['alignment_stats']['counts_total']['Reference']-=count
    if kind=='ambiguous':data['results']['alignment_stats']['class_counts']['AMBIGUOUS']=count
    else:data['results']['alignment_stats']['counts_discarded']['Reference']=count
    (archive/'CRISPResso2_info.json').write_text(json.dumps(data))
    p=archive/'CRISPResso_quantification_of_editing_frequency.txt'
    with p.open() as h:reader=csv.DictReader(h,delimiter='\t');fields=reader.fieldnames;quant=list(reader)
    quant[0]['Reads_aligned']=str(int(quant[0]['Reads_aligned'])-count)
    if kind=='discarded':quant[0]['Discarded']=str(count)
    key='Unmodified' if status=='UNMODIFIED' else 'Modified';quant[0][key]=str(int(quant[0][key])-count)
    with p.open('w') as h:writer=csv.DictWriter(h,fieldnames=fields,delimiter='\t');writer.writeheader();writer.writerows(quant)
    # Generic reconciliation remains available, but this population is unqualified.
    from peanalyzer.backend.metrics import aligned_partition
    rows[0]['Reference_Name']=kind.upper()+'_Reference'
    partition=aligned_partition(data,rows,data['results']['alignment_stats']['counts_total'])
    assert partition[kind+'_aligned_reads']==count and sum(partition.values())==20
    with pytest.raises(ValueError,match='UNQUALIFIED_NUCLEASE_POPULATION'):
        parse_nuclease_child(archive,target(),20)


@pytest.mark.parametrize('name',['target','result','statistics','report'])
def test_packaged_nuclease_schemas(name):
    from importlib.resources import files
    from peanalyzer.nuclease.models import NucleaseStatisticsResult,NucleaseReportManifest
    model={'target':NucleaseTarget,'result':NucleaseMetricResult,'statistics':NucleaseStatisticsResult,'report':NucleaseReportManifest}[name]
    schema=json.loads(files('peanalyzer.nuclease').joinpath(name+'.schema.json').read_text())
    assert schema==model.model_json_schema() and schema['additionalProperties'] is False


def test_nuclease_samples_are_not_pe_results():
    from peanalyzer.metrics import MetricResult
    data=json.loads((EVIDENCE/'result.json').read_text())
    with pytest.raises(ValidationError):MetricResult.model_validate(data)


def test_nuclease_csv_validation_reports_resolved_window(tmp_path):
    from peanalyzer.validation import validate_metadata
    options=fixture(tmp_path/'inputs')
    result=validate_metadata(options['samples'],options['targets'],options['config'])
    assert result['analysis_modes']==['indel_nuclease']
    assert result['resolved_targets'][0]['resolved_window']['coordinates']=='104-113'
    assert result['nuclease_execution_supported'] is True


@pytest.fixture
def measurements(tmp_path):
    from m7_fixtures import write_csv
    options=fixture(tmp_path/'inputs');rows=[]
    for i in range(4):
        data=json.loads((EVIDENCE/'result.json').read_text());data['sample_id']=f'bc{i+1:03}';data['analysis_id']=f'synthetic-{i}'
        path=tmp_path/f'metric{i}.json';path.write_text(json.dumps(data));rows.append({'result_json':path.name})
    manifest=tmp_path/'manifest.csv';write_csv(manifest,['result_json'],rows)
    return dict(manifest_path=manifest,samples_path=options['samples']),options['samples'].parent/'contrasts.yaml'


def test_nuclease_m5_m6_statistics_determinism_and_no_recomputation(measurements,tmp_path,monkeypatch):
    from peanalyzer.aggregation import summarize
    from peanalyzer.statistics import stats
    from peanalyzer.reporting import generate_report
    import peanalyzer.aggregation as aggregation
    import peanalyzer.statistics as statistics
    import xml.etree.ElementTree as ET
    options,contrasts=measurements
    summary=summarize(**options)
    assert not summary.contrasts and len(summary.observations)==40
    result=stats(**options,contrasts_path=contrasts,output=tmp_path/'stats')
    assert result.contrasts[0].p_value==result.contrasts[0].q_value==1.0
    assert result.contrasts[0].used_group_a_count==result.contrasts[0].used_group_b_count==2
    for module,names in [(aggregation,['collect_observations','summarize_groups']),
                         (statistics,['calculate_contrasts','exact_unpaired','exact_paired','benjamini_hochberg'])]:
        for name in names:monkeypatch.setattr(module,name,lambda *a,**k:pytest.fail('report recomputed statistics'))
    for name in ('one','two'):
        manifest=generate_report(result_path=tmp_path/'stats/result.json',output=tmp_path/name)
        assert manifest.report_contract_version=='indel-nuclease-report-v1'
        assert manifest.title=='Indel/nuclease amplicon analysis report'
        page=(tmp_path/name/'report.html').read_text()
        assert 'Top 20 CRISPResso allele' in page and '104-113' in page and 'single_copy_identity' in page
        assert 'M4 upstream observability' not in page and 'Copy metrics are routing-conditioned.' not in page
        assert (tmp_path/name/'source/result.json').read_bytes()==(tmp_path/'stats/result.json').read_bytes()
        for path in (tmp_path/name/'figures').glob('*.svg'):
            svg=path.read_text();ET.fromstring(svg);assert svg in page
    def files(root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert files(tmp_path/'one')==files(tmp_path/'two')


@pytest.mark.parametrize('control',['\x01','\x0b'])
def test_nuclease_keeps_m61_fail_closed(measurements,tmp_path,control):
    from peanalyzer.aggregation import summarize
    from peanalyzer.reporting import generate_report,ReportingError
    from matplotlib import pyplot as plt
    options,_=measurements
    samples=options['samples_path'];samples.write_text(samples.read_text().replace('synthetic-nuclease','ed'+control+'x'))
    summarize(**options,output=tmp_path/'stats')
    before=plt.get_fignums()
    with pytest.raises(ReportingError,match='INVALID_GENERATED_SVG'):
        generate_report(result_path=tmp_path/'stats/result.json',output=tmp_path/'report')
    assert not (tmp_path/'report').exists() and not list(tmp_path.glob('.report*'))
    assert plt.get_fignums()==before


def test_nuclease_duplicate_replicates_rejected(measurements,tmp_path):
    from peanalyzer.aggregation import summarize,AggregationError
    options,_=measurements
    samples=options['samples_path'];samples.write_text(samples.read_text().replace('bc002,AAAAAAAC,CCCCCCCC,synthetic-nuclease,A,6,2','bc002,AAAAAAAC,CCCCCCCC,synthetic-nuclease,A,6,1'))
    with pytest.raises(AggregationError,match='duplicate biological_replicate'):summarize(**options)


def test_nuclease_partial_coverage_rejected(measurements,tmp_path):
    from peanalyzer.aggregation import summarize,AggregationError
    from peanalyzer.metrics.production import digest
    options,_=measurements
    path=tmp_path/'metric0.json';data=json.loads(path.read_text())
    data['target_id']=data['target']['target_name']='T2'
    t=NucleaseTarget.model_validate(data['target'])
    data['provenance']['target_definitions_sha256']=digest([t.model_dump()])
    data['provenance']['scientific_identity']=t.scientific_identity
    data['provenance']['execution']['scientific_identity']=t.scientific_identity
    path.write_text(json.dumps(data))
    with pytest.raises(AggregationError,match='PARTIAL_SAMPLE_TARGET_COVERAGE'):summarize(**options)


def test_window_changes_stage_identity_and_requires_upstream_force(tmp_path):
    from m7_fixtures import write_csv
    options=fixture(tmp_path/'inputs');options['crispresso']=fake_core(tmp_path)
    before=w.build_workflow_plan(**options)
    t=target(tigr_window='W1');write_csv(options['targets'],list(t.model_dump()),[t.model_dump()])
    after=w.build_workflow_plan(**options)
    n=next(n for n in before.nodes if n.stage_kind=='routing')
    assert w.signature(before,n,{})!=w.signature(after,n,{})
    assert n.stage_id not in w.force_closure(after,['report'])
    assert n.stage_id in w.force_closure(after,['routing'])


@pytest.mark.parametrize('raw',[[],None,'invalid',1,True])
def test_dispatch_preserves_typed_report_rejection(raw,tmp_path):
    from peanalyzer.reporting import generate_report,ReportingError
    path=tmp_path/'invalid.json';path.write_text(json.dumps(raw))
    with pytest.raises(ReportingError,match='invalid M5 result'):
        generate_report(result_path=path,output=tmp_path/'report')
    assert not (tmp_path/'report').exists() and not list(tmp_path.glob('.report*'))


def test_nuclease_contract_footer_does_not_rewrite_labels(measurements,tmp_path):
    from peanalyzer.aggregation import summarize
    from peanalyzer.reporting import generate_report
    import xml.etree.ElementTree as ET
    label='report contract: m6-v1; source statistics contract: m5-v1'
    options,_=measurements
    samples=options['samples_path']
    samples.write_text(samples.read_text().replace('synthetic-nuclease',label))
    summarize(**options,output=tmp_path/'stats')
    manifest=generate_report(result_path=tmp_path/'stats/result.json',output=tmp_path/'report',title=label)
    page=(tmp_path/'report/report.html').read_text()
    assert manifest.title==label and '<title>'+label+'</title>' in page
    assert 'report contract: indel-nuclease-report-v1; source statistics contract: indel-nuclease-stats-v1' in page
    for path in (tmp_path/'report/figures').glob('*.svg'):
        svg=path.read_text();ET.fromstring(svg)
        assert label in svg and svg in page


@pytest.mark.parametrize('field',sorted(target().scientific_identity['backend_settings']))
@pytest.mark.parametrize('attack',['value','missing','type'])
def test_closed_resolved_scientific_contract(archive,field,attack):
    path=archive/'CRISPResso2_info.json';data=json.loads(path.read_text())
    args=data['running_info']['args']['value'];value=args[field]
    if attack=='missing':args.pop(field)
    elif attack=='type':args[field]=0 if type(value) is bool else str(value) if type(value) is int else None
    else:args[field]=not value if type(value) is bool else value+1 if type(value) is int else value+'__drift'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='UNQUALIFIED_NUCLEASE_CONFIGURATION: '+field):
        parse_nuclease_child(archive,target(),20)


@pytest.mark.parametrize('field,value',[
    ('output_folder','/another/output'),('name','another-name'),('display_name','Another title'),
    ('verbosity',1),('plot_window_size',10),('n_processes','4'),('config_file','/another/colors.json'),
    ('suppress_plots',False),('suppress_report',False)])
def test_presentation_and_runtime_locations_are_not_scientific_drift(archive,field,value):
    path=archive/'CRISPResso2_info.json';data=json.loads(path.read_text())
    data['running_info']['args']['value'][field]=value;path.write_text(json.dumps(data))
    result=parse_nuclease_child(archive,target(),20)
    assert result['metrics']['indel_fraction'].numerator==10
    assert result['class_counts']['ambiguous']==result['class_counts']['discarded']==0


@pytest.mark.parametrize('kind',['ambiguous','discarded'])
def test_serialized_nuclease_results_reject_exceptional_populations(kind):
    data=json.loads((EVIDENCE/'result.json').read_text());row=data['alleles'][0]
    row['authoritative_fields']['Reference_Name']=kind.upper()+'_Reference';row['product_class']=kind
    counts,metrics,sizes=aggregate([allele(a['authoritative_fields']) for a in data['alleles']],data['aligned_reads'])
    data['class_counts']=counts;data['metrics']={k:v.model_dump() for k,v in metrics.items()}
    data['fraction_of_indel_reads_by_net_size']={k:v.model_dump() for k,v in sizes.items()}
    with pytest.raises(ValueError,match='UNQUALIFIED_NUCLEASE_POPULATION'):
        NucleaseMetricResult.model_validate(data)


@pytest.mark.parametrize('field,value',[('discard_indel_reads',True),('min_bp_quality_or_N',30)])
def test_serialized_nuclease_results_recheck_resolved_arguments(field,value):
    data=json.loads((EVIDENCE/'result.json').read_text())
    data['provenance']['execution']['resolved_backend_arguments'][field]=value
    with pytest.raises(ValueError,match='UNQUALIFIED_NUCLEASE_CONFIGURATION: '+field):
        NucleaseMetricResult.model_validate(data)


def test_pre_remediation_scientific_identity_is_not_reusable():
    from peanalyzer.metrics.production import digest
    before=json.loads((EVIDENCE.parents[1]/'m8/allele-probe/result.json').read_text())
    assert digest(before['provenance']['scientific_identity'])!=digest(target().scientific_identity)
    with pytest.raises(ValueError,match='nuclease provenance mismatch'):
        NucleaseMetricResult.model_validate(before)


def test_selected_tigr_window_prose_is_not_static_w2(measurements,tmp_path):
    from peanalyzer.aggregation import summarize
    from peanalyzer.reporting import generate_report
    options,_=measurements;t=target(tigr_window='W1')
    for path in tmp_path.glob('metric*.json'):
        data=json.loads(path.read_text());data['target']=t.model_dump()
        from peanalyzer.metrics.production import digest
        data['provenance']['target_definitions_sha256']=digest([t.model_dump()])
        data['provenance']['scientific_identity']=t.scientific_identity
        data['provenance']['execution']['scientific_identity']=t.scientific_identity
        data['provenance']['execution']['resolved_backend_arguments']['quantification_window_coordinates']=t.window['coordinates']
        path.write_text(json.dumps(data))
    summarize(**options,output=tmp_path/'stats')
    generate_report(result_path=tmp_path/'stats/result.json',output=tmp_path/'report')
    page=(tmp_path/'report/report.html').read_text()
    assert 'Selected window: W1; zero-based inclusive coordinates: 104-105_112-113.' in page
    assert 'primary window is W2' not in page


def test_scientific_contract_alone_changes_stage_signatures(tmp_path,monkeypatch):
    options=fixture(tmp_path/'inputs');options['crispresso']=fake_core(tmp_path)
    plan=w.build_workflow_plan(**options)
    old=json.loads((EVIDENCE.parents[1]/'m8/allele-probe/result.json').read_text())['provenance']['scientific_identity']
    for node in plan.nodes:
        if node.stage_kind not in ('routing','metrics'):continue
        current=w.signature(plan,node,{})
        with monkeypatch.context() as patch:
            patch.setattr(w,'scientific_target',lambda t:old)
            previous=w.signature(plan,node,{})
        assert previous!=current
