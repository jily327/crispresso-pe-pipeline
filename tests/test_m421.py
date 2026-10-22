"""Focused target selection, local policy errors and repeat-length regressions."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from peanalyzer.metrics import aggregate_family,collect_metrics,reaggregate,run_metrics
from peanalyzer.metrics.family import prepared_evidence
from peanalyzer.metrics.policy_requests import prepare_policies
from peanalyzer.observability import assess_pair,state_geometry,population_observability
from peanalyzer.remediation import panel,pair,indel_designs
from peanalyzer.schemas import Target
from test_m4 import archive,collect
from test_m42 import mutate,tolerance_fixture


def copy_panel(kind='deletion',reverse=False):
    targets=panel();t=targets[1]
    if kind=='deletion':transform=lambda s:s[:10]+s[16:]
    elif kind=='insertion':transform=lambda s:s[:10]+'ACGTCA'+s[10:]
    elif kind=='repeat':transform=lambda s:s[:134]+'CA'*8+s[150:]
    elif kind=='low_complexity':transform=lambda s:s[:134]+'A'*16+s[150:]
    else:raise ValueError(kind)
    targets[1]=t.model_copy(update={k:transform(getattr(t,k)) for k in ('wt_sequence','prime_edited_sequence')})
    if reverse:
        targets=[targets[1].model_copy(update={'copy_name':'copy1'}),targets[0].model_copy(update={'copy_name':'copy2'})]
    return targets


def records_for(targets,left,right,tag=""):

    records=[]
    for index,t in enumerate(targets):
        for state,count,seq in [('WT',18 if index==0 else 2,t.wt_sequence),
                                ('PE',2 if index==0 else 18,t.prime_edited_sequence)]:
            for i in range(count):
                identifier=f'{tag}{t.copy_name}_{state}_{i}'
                records.append((pair(seq,identifier=identifier,length=left)[0],pair(seq,identifier=identifier,length=right)[1]))
    return records


def canonical(result):
    data=result.model_dump()
    return {k:data[k] for k in ('target_metrics','copies','qc','eligibility','anchor_evidence','product_evidence')}


@pytest.mark.parametrize('kind,left,right,exact,backend',[
    ('deletion',150,150,False,False),('deletion',125,125,False,True),
    ('deletion',124,125,True,True),('deletion',120,120,False,False),
    ('insertion',150,150,False,False),('insertion',128,128,False,True),
    ('insertion',127,128,True,True),('insertion',124,125,False,False),
    ('repeat',150,106,True,False),('low_complexity',150,106,True,False),
    ('repeat',150,150,False,False),('low_complexity',150,150,False,False)])
@pytest.mark.parametrize('reverse',[False,True])
def test_copy_candidate_geometry_is_symmetric_and_scope_specific(tmp_path,kind,left,right,exact,backend,reverse):
    targets=copy_panel(kind,reverse);records=records_for(targets,left,right)
    files=[tmp_path/f'R{m}.fastq' for m in (1,2)]
    for m,path in enumerate(files):path.write_bytes(b''.join(p[m].to_bytes() for p in records))
    observed=population_observability(files,targets)
    assert ('COPY_DEPENDENT_BACKEND_MERGEABILITY' in observed['backend_reason_counts'])==backend
    assert ('COPY_DEPENDENT_PRODUCT_OBSERVABILITY' in observed['exact_reason_counts'])==exact
    assessments=[assess_pair(p,targets) for p in records]
    if exact:
        assert all(p['canonical']=='other_or_unassessable' and p['reason']=='COPY_DEPENDENT_PRODUCT_OBSERVABILITY' for p in assessments)
        evidence=prepared_evidence(files,targets,population_id='target',population_scope='target_all_prepared',copy_id=None,source_input_reads=40)
        assert all(not p.assessable for p in evidence.products)
        assert all(r.status!='REPORTABLE' for r in reaggregate(evidence,[dict(policy_id=str(n),max_extra_substitutions=n) for n in (0,1)]).values())
    elif all(all(r['exact_states']) for r in state_geometry(targets,left,right)):
        assert sum(p['canonical']=='exact_PE' for p in assessments)==20
        assert sum(p['canonical']=='exact_WT' for p in assessments)==20
    else:assert all(p['canonical']=='other_or_unassessable' for p in assessments)
    for t in targets:
        scoped=population_observability(files,[t])
        assert not any(k.startswith('COPY_DEPENDENT_') for k in (*scoped['backend_reason_counts'],*scoped['exact_reason_counts']))
        if all(state_geometry([t],left,right)[0]['exact_states']):
            assert assess_pair((pair(t.wt_sequence,length=left)[0],pair(t.wt_sequence,length=right)[1]),[t])['canonical']=='exact_WT'


def test_three_copies_with_only_middle_copy_unobservable():
    targets=copy_panel('deletion',True)
    targets.append(targets[0].model_copy(update={'copy_name':'copy3'}))
    assert [all(r['exact_states']) for r in state_geometry(targets,124,125)]==[True,False,True]
    for t in targets:
        assert assess_pair((pair(t.wt_sequence,length=124)[0],pair(t.wt_sequence,length=125)[1]),targets)['reason']=='COPY_DEPENDENT_PRODUCT_OBSERVABILITY'


def test_copy_axis_preserves_within_copy_state_failure_precedence():
    targets=next(ts for d,ts in indel_designs() if d['id']=='insertion_12_seed11')
    other=targets[1]
    targets[1]=other.model_copy(update={k:getattr(other,k)[:10]+getattr(other,k)[30:] for k in ('wt_sequence','prime_edited_sequence')})
    rows=state_geometry(targets,128,128)
    assert rows[0]['exact_states']==[True,False] and rows[1]['exact_states']==[True,True]
    for t in targets:
        assert assess_pair(pair(t.wt_sequence,length=128),targets)['reason']=='STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY'


MOTIFS=['A','CA','CAG','AGCT','ACGTC','GGGGCC','ACGTGCA','ACGTTGCA','ACGTTCGCA','ACGTTCAGCA']


def periodic_case(period,direction,state):
    t=panel()[0];motif=MOTIFS[period-1];prefix=t.wt_sequence[:100];suffix=t.wt_sequence[170:]
    if direction=='expansion':
        delta=period*((6+period-1)//period);ref_length=2*delta;physical_length=3*delta
        total_repeat_reads=physical_length+4
    else:
        delta=period*((10+period-1)//period);ref_length=3*delta;physical_length=2*delta
        total_repeat_reads=ref_length+10
    wt=prefix+motif*(ref_length//period)+suffix
    target=t.model_copy(update={'wt_sequence':wt,'prime_edited_sequence':mutate(wt,55)})
    physical=prefix+motif*(physical_length//period)+suffix
    if state=='PE':physical=mutate(physical,55)
    left=len(prefix)+total_repeat_reads//2;right=len(suffix)+(total_repeat_reads+1)//2
    return target,(pair(physical,length=left)[0],pair(physical,length=right)[1])


@pytest.mark.parametrize('period',range(1,11))
@pytest.mark.parametrize('direction',['expansion','contraction'])
def test_repeat_period_grid_rejects_ambiguous_length_and_accepts_informative_flanks(period,direction):
    for state in ('WT','PE'):
        target,records=periodic_case(period,direction,state)
        assessment=assess_pair(records,[target])
        assert assessment['canonical']=='other_or_unassessable' and assessment['reason']
        # Identical definitions, but 20 informative bases flank both sides of
        # the repeated segment in the overlap; repeat presence alone is valid.
        for label,sequence in [('exact_WT',target.wt_sequence),('exact_PE',target.prime_edited_sequence)]:
            left=len(sequence)-50;right=len(sequence)-80
            assert assess_pair((pair(sequence,length=left)[0],pair(sequence,length=right)[1]),[target])['canonical']==label


def policy_cases():
    valid=dict(policy_id='valid',max_extra_substitutions=1)
    return [
        ('none',[]),('one',[valid]),('two',[valid,dict(policy_id='strict')]),
        ('duplicate',[valid,valid]),('missing_twice',[{},{}]),('missing_valid',[{},valid]),
        *[(name,[value,valid]) for name,value in [('null',None),('integer',7),('string','bad'),('list',[]),('bool',True)]],
        *[(name,[dict(policy_id='bad',**value),valid]) for name,value in [
            ('unknown',{'x':1}),('negative',{'max_extra_substitutions':-1}),('float',{'max_extra_substitutions':1.0}),
            ('bool_count',{'max_extra_substitutions':True}),('indel',{'max_extra_indel_events':1}),
            ('abundance',{'min_haplotype_count':2}),('quality',{'min_base_quality':20}),
            ('position',{'allowed_extra_substitution_positions':[999]})]],
        ('duplicate_and_valid',[dict(policy_id='duplicate'),dict(policy_id='duplicate'),valid]),
        ('all_invalid',[None,{},7,False]),('key_collision',[None,dict(policy_id='__invalid_policy_request_0')])]


@pytest.mark.parametrize('name,policies',policy_cases(),ids=[n for n,_ in policy_cases()])
def test_invalid_policies_are_local_and_canonical_is_unchanged(archive,name,policies):
    baseline=collect(archive);result=collect(archive,tolerance_policies=policies)
    assert canonical(result)==canonical(baseline)
    assert len(result.derived_metrics.get('target',{}))==len(policies)
    fixture=tolerance_fixture();outputs=reaggregate(fixture,policies)
    assert len(outputs)==len(policies)
    targets=[Target.model_validate(t) for t in fixture.targets]
    requests=prepare_policies(policies,targets)
    for request,(key,row) in zip(requests.requests,outputs.items()):
        assert key==request.storage_key and row.policy_id==request.policy_id
        if request.reasons:
            assert row.status=='BLOCKED' and set(request.reasons)<=set(row.reason_codes)
        else:assert row.status=='REPORTABLE'
    if any(p==dict(policy_id='valid',max_extra_substitutions=1) for p in policies) and name!='duplicate':
        assert (outputs['valid'].numerator,outputs['valid'].denominator)==(330,1360)
    for key,evidence in result.product_evidence.items():
        if policies:assert reaggregate(json.loads(evidence.model_dump_json()),policies)==result.derived_metrics[key]


def test_run_metrics_prevalidates_before_canonical_work_and_publishes(archive,tmp_path,monkeypatch):
    import peanalyzer.metrics.production as production
    events=[];original_prepare=production.prepare_policies;original_collect=production.collect_metrics
    def prepare(policies,targets):
        result=original_prepare(policies,targets);events.append('policy_validation');return result
    def collect_spy(**args):
        assert events[0]=='policy_validation';events.append('canonical_collection');return original_collect(**args)
    def comparator(analysis,sample,targets,output,core,**kwargs):
        assert events[0]=='policy_validation';events.append('backend_launch')
        shutil.copytree(archive/'comparator',output)
        return {'anchor_failures':{}}
    def copy_core(routing,copy,output,core,**kwargs):shutil.copytree(archive/'copies'/copy,output)
    monkeypatch.setattr(production,'prepare_policies',prepare)
    monkeypatch.setattr(production,'collect_metrics',collect_spy)
    monkeypatch.setattr(production,'run_comparator',comparator)
    monkeypatch.setattr(production,'run_confident_core',copy_core)
    policies=[dict(policy_id='duplicate'),dict(policy_id='duplicate'),None,{},7,dict(policy_id='valid')]
    result=run_metrics(analysis_root=archive/'analysis',sample_id='1B',targets=panel(),analysis_id='mixed',
        output=tmp_path/'result',core=['unused'],routing_root=archive/'routing',tolerance_policies=policies)
    assert events.index('policy_validation')<events.index('canonical_collection')<events.index('backend_launch')
    assert canonical(result)==canonical(collect(archive))
    assert (tmp_path/'result/result.json').is_file()
    assert len(result.derived_metrics['target'])==6 and result.derived_metrics['target']['valid'].status=='REPORTABLE'


def test_clean_process_reaggregation_handles_invalid_policies_without_backend(tmp_path):
    evidence=tolerance_fixture();policies=[{},None,dict(policy_id='same'),dict(policy_id='same'),dict(policy_id='valid',max_extra_substitutions=1)]
    input_path=tmp_path/'evidence.json';input_path.write_text(evidence.model_dump_json())
    script="""import json,sys
from peanalyzer.metrics import reaggregate
value=json.load(open(sys.argv[1]))
policies=json.loads(sys.argv[2])
print(json.dumps({k:v.model_dump() for k,v in reaggregate(value,policies).items()},sort_keys=True))
"""
    actual=json.loads(subprocess.check_output([sys.executable,'-c',script,str(input_path),json.dumps(policies)],cwd=tmp_path,text=True))
    assert actual=={k:v.model_dump() for k,v in reaggregate(evidence,policies).items()}


@pytest.mark.parametrize('policies',[7,True,'bad',{'max_extra_substitutions':1}])
def test_malformed_top_level_policy_collection_does_not_raise(archive,policies):
    result=collect(archive,tolerance_policies=policies)
    assert canonical(result)==canonical(collect(archive))
    assert len(result.derived_metrics['target'])==1
    assert next(iter(result.derived_metrics['target'].values())).status=='BLOCKED'


def test_mixed_length_population_excludes_entire_biased_class(tmp_path):
    from peanalyzer.metrics.products import prepared_products
    targets=copy_panel()
    records=records_for(targets,150,150,'long_')+records_for(targets,124,125,'short_')
    paths=[tmp_path/f'R{m}.fastq' for m in (1,2)]
    for m,path in enumerate(paths):path.write_bytes(b''.join(p[m].to_bytes() for p in records))
    products=prepared_products(paths,targets)
    assert (products.exact_wt,products.exact_pe,products.classification_input_reads)==(20,20,80)
    assert products.exclusion_reason_counts=={'COPY_DEPENDENT_PRODUCT_OBSERVABILITY':40}
    evidence=prepared_evidence(paths,targets,population_id='mixed',population_scope='target_all_prepared',copy_id=None,source_input_reads=80)
    result=aggregate_family(evidence,dict(policy_id='one',max_extra_substitutions=1))
    # M4.2.2: retain per-pair QC, but never report the selected target subset.
    assert result.status=='NOT_ASSESSABLE'
    assert (result.numerator,result.denominator,result.excluded)==(None,None,80)
    assert result.reason_codes==['COPY_DEPENDENT_PRODUCT_OBSERVABILITY']
    assert population_observability(paths,targets)['backend_reason_counts']=={'COPY_DEPENDENT_BACKEND_MERGEABILITY':40}
