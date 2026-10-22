"""M4.2 symmetric observability, authenticated reasons and additive families."""
import csv
import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from peanalyzer.backend.metrics import exact_pair_class
from peanalyzer.metrics import FamilyPolicy, aggregate_family, reaggregate, collect_metrics, MetricResult
from peanalyzer.metrics.family import observed_product, candidate_evidence
from peanalyzer.metrics.family_models import ProductEvidence
from peanalyzer.observability import assess_pair, state_geometry, reconstruct
from peanalyzer.remediation import panel,pair,indel_designs
from peanalyzer.schemas import reverse_complement
from test_m4 import archive,collect,write_json


def mutate(seq,position,base=None):
    base=base or next(b for b in 'ACGT' if b!=seq[position])
    return seq[:position]+base+seq[position+1:]


def repeat_targets():
    targets=panel()
    # Locate the edit from the definitions, then place an internal microsatellite
    # 30 nt downstream. Routing diagnostics and the actual spacer stay intact.
    edit=next(i for i,(a,b) in enumerate(zip(targets[0].wt_sequence,targets[0].prime_edited_sequence)) if a!=b)
    start=edit+30
    targets=[t.model_copy(update={f:getattr(t,f)[:start]+'CA'*4+getattr(t,f)[start+8:]
             for f in ('wt_sequence','prime_edited_sequence')}) for t in targets]
    return targets,start


@pytest.mark.parametrize('design,left,right',[('insertion_12_seed11',128,128),('deletion_1_seed29',124,125)])
def test_state_dependent_exact_threshold_excludes_both_states(design,left,right):
    targets=next(ts for d,ts in indel_designs() if d['id']==design)
    for target in targets:
        for seq in (target.wt_sequence,target.prime_edited_sequence):
            records=(pair(seq,length=left)[0],pair(seq,length=right)[1])
            result=assess_pair(records,targets)
            assert result['canonical']=='other_or_unassessable'
            assert result['reason']=='STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY'


def test_backend_and_exact_boundaries_are_distinct_and_within_copy():
    targets=next(ts for d,ts in indel_designs() if d['id']=='deletion_1_seed29')
    rows=state_geometry(targets,125,125)
    assert all(r['exact_states']==[True,True] and r['backend_merge_states']==[False,True] for r in rows)
    for t in targets:
        assert exact_pair_class(pair(t.wt_sequence,length=125),targets)=='exact_WT'
        assert exact_pair_class(pair(t.prime_edited_sequence,length=125),targets)=='exact_PE'
    base=panel();t=base[1]
    base[1]=t.model_copy(update={f:'ACGTA'+getattr(t,f) for f in ('wt_sequence','prime_edited_sequence')})
    for t in base:
        assert exact_pair_class(pair(t.wt_sequence),base)=='exact_WT'
        assert exact_pair_class(pair(t.prime_edited_sequence),base)=='exact_PE'


@pytest.mark.parametrize('motif,units,expanded',[('CAG',4,7),('CA',5,9)])
def test_short_period_alternatives_prevent_false_exact(motif,units,expanded):
    t=panel()[0];prefix=t.wt_sequence[:100];suffix=t.wt_sequence[170:]
    wt=prefix+motif*units+suffix;pe=mutate(wt,55)
    target=t.model_copy(update={'wt_sequence':wt,'prime_edited_sequence':pe})
    for intended_pe in (False,True):
        physical=prefix+motif*expanded+suffix
        if intended_pe:physical=mutate(physical,55)
        left=pair(physical,length=len(prefix)+len(motif)*units)[0]
        right=pair(physical,length=len(suffix)+len(motif)*units)[1]
        result=assess_pair((left,right),[target])
        assert result['canonical']=='other_or_unassessable'
        assert result['reason'] in ('PERIODIC_PRODUCT_RECONSTRUCTION','REFERENCE_PRODUCT_NOT_OBSERVABLE')


def test_internal_microsatellite_preserves_informative_full_product():
    targets,start=repeat_targets()
    for t in targets:
        for state,seq in [('exact_WT',t.wt_sequence),('exact_PE',t.prime_edited_sequence)]:
            result=assess_pair(pair(seq,length=180),targets)
            assert result['canonical']==state and result['reason'] is None
            # Same references, but only the repeat itself overlaps.
            records=(pair(seq,length=start+8)[0],pair(seq,length=len(seq)-start)[1])
            result=assess_pair(records,targets)
            assert result['canonical']=='other_or_unassessable' and result['reason']


@pytest.mark.parametrize('raw,code',[
    ('made_up','UNKNOWN_BACKEND_FAILURE_REASON'),('', 'UNKNOWN_BACKEND_FAILURE_REASON'),
    (' BACKEND_EXECUTION_FAILED ','UNKNOWN_BACKEND_FAILURE_REASON'),
    (None,'INVALID_BACKEND_FAILURE_REASON'),(7,'INVALID_BACKEND_FAILURE_REASON'),
    (['BACKEND_EXECUTION_FAILED'],'INVALID_BACKEND_FAILURE_REASON'),({},'INVALID_BACKEND_FAILURE_REASON'),
    ('BACKEND_EXECUTION_FAILED','BACKEND_EXECUTION_FAILED')])
def test_execution_reason_contract_cannot_crash_or_inject_codes(archive,tmp_path,raw,code):
    root=tmp_path/'run';shutil.copytree(archive,root)
    p=root/'comparator/copy2/execution.json';d=json.loads(p.read_text())
    d.update(status='failed',return_code=0,reason_code=raw);write_json(p,d)
    result=collect(root)
    assert result.target_metrics.target_crispresso_native_pe.reason_codes==[code]
    assert result.target_metrics.total_precise_pe.denominator==55


def evidence_for(targets,products,scope='target_all_prepared',copy=None):
    rows=[observed_product(s,n,targets,eligible=[copy] if copy else None) for s,n in products]
    return ProductEvidence(population_id='synthetic-population',population_scope=scope,copy_id=copy,
        assessment_stage='prepared_pairs' if copy is None else 'backend_aligned_products',
        source_input_reads=sum(n for _,n in products),classification_input_reads=sum(n for _,n in products),
        targets=[t.model_dump() for t in targets],products=rows)


def tolerance_fixture():
    t=panel()[0]
    t=t.model_copy(update={f:mutate(mutate(getattr(t,f),149,'A'),179,'C') for f in ('wt_sequence','prime_edited_sequence')})
    products=[]
    for seq,n in [(t.wt_sequence,1000),(t.prime_edited_sequence,300)]:
        products += [(seq,n),(mutate(seq,149,'G'),20),(mutate(seq,179,'T'),10),
            (mutate(mutate(seq,149,'G'),179,'T'),5),(seq[:60]+'T'+seq[60:],5)]
    return evidence_for([t],products)


@pytest.mark.parametrize('limit,wt,pe,den',[(0,1000,300,1300),(1,1030,330,1360),(2,1035,335,1370)])
def test_symmetric_tolerance_counts_and_complete_intended_edit(limit,wt,pe,den):
    evidence=tolerance_fixture()
    result=aggregate_family(evidence,dict(policy_id=f'sub-{limit}',max_extra_substitutions=limit))
    assert result.status=='REPORTABLE'
    assert (result.wt_family,result.pe_family,result.denominator)==(wt,pe,den)
    assert result.numerator==pe and result.excluded==1380-den
    assert sum(p.count for p in evidence.products if p.canonical_exact_pe)==300
    # WT + an extra substitution never becomes PE-family without the intended edit.
    assert all(c['complete_intended_state'] is False for c in evidence.products[1].candidates if c['family']=='PE')


@pytest.mark.parametrize('positions,pe,den',[([149],320,1340),([179],310,1320),([],300,1300)])
def test_position_specific_tolerance(positions,pe,den):
    result=aggregate_family(tolerance_fixture(),dict(policy_id='position',max_extra_substitutions=2,
        allowed_extra_substitution_positions=positions))
    assert (result.numerator,result.denominator)==(pe,den)


@pytest.mark.parametrize('policy',[
    {'max_extra_substitutions':-1},{'max_extra_substitutions':1.0},{'max_extra_substitutions':True},
    {'max_extra_indel_events':1},{'max_extra_indel_events':False},
    {'allowed_extra_substitution_positions':[999]},{'allowed_extra_substitution_positions':[False]},
    {'min_haplotype_count':2}])
def test_unsupported_policies_are_explicitly_blocked(policy):
    result=aggregate_family(tolerance_fixture(),dict(policy_id='invalid',**policy))
    assert result.status=='BLOCKED' and result.reason_codes==['UNSUPPORTED_TOLERANCE_POLICY']
    assert result.numerator is result.denominator is None


def distance_fixture():
    t=panel()[0];wt=t.wt_sequence
    other_wt=wt[:118]+'A'+wt[118:123]+wt[124:]
    other_pe=mutate(other_wt,123,'T')
    other=t.model_copy(update={'copy_name':'copy2','wt_sequence':other_wt,'prime_edited_sequence':other_pe})
    sequence=mutate(other_pe,118,'G')
    return [t,other],sequence


def test_minimum_family_distance_does_not_become_ambiguous_at_larger_radius():
    targets,seq=distance_fixture();evidence=evidence_for(targets,[(seq,7)])
    candidates=evidence.products[0].candidates
    distances={f:min(c['extra_substitution_count'] for c in candidates if c['family']==f and c['complete_intended_state'] and c.get('extra_indel_events')==0) for f in ('WT','PE')}
    assert distances=={'WT':3,'PE':1}
    for n in (1,3):
        result=aggregate_family(evidence,dict(policy_id=str(n),max_extra_substitutions=n))
        assert (result.pe_family,result.wt_family,result.family_ambiguous)==(7,0,0)
    tied=evidence_for(targets,[(mutate(seq,119,'T'),7)])
    result=aggregate_family(tied,dict(policy_id='tie',max_extra_substitutions=3))
    assert result.family_ambiguous==7 and result.status=='NOT_ASSESSABLE'
    assert result.reason_codes==['ZERO_FAMILY_DENOMINATOR']


def test_same_family_copy_ties_collapse_and_policy_counts_are_monotone():
    base=tolerance_fixture();target=base.targets[0]
    from peanalyzer.schemas import Target
    t=Target.model_validate(target);targets=[t,t.model_copy(update={'copy_name':'copy2'})]
    evidence=evidence_for(targets,[(p.sequence,p.count) for p in base.products])
    outputs=reaggregate(evidence,[dict(policy_id=str(n),max_extra_substitutions=n) for n in range(4)])
    assert [r.pe_family for r in outputs.values()]==[300,330,335,335]
    assert [r.wt_family for r in outputs.values()]==[1000,1030,1035,1035]
    assert all(r.family_ambiguous==0 for r in outputs.values())
    restored=ProductEvidence.model_validate_json(evidence.model_dump_json())
    assert reaggregate(restored,[r.policy for r in outputs.values()])==outputs


def test_tolerance_does_not_rescue_unobservable_or_modify_canonical(archive):
    original=collect(archive)
    policies=[dict(policy_id=str(n),max_extra_substitutions=n) for n in range(3)]
    selected=collect(archive,tolerance_policies=policies)
    for field in ('target_metrics','copies','qc','eligibility','anchor_evidence'):
        assert json.dumps(getattr(original,field).model_dump() if hasattr(getattr(original,field),'model_dump') else {k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in getattr(original,field).items()},sort_keys=True)==json.dumps(getattr(selected,field).model_dump() if hasattr(getattr(selected,field),'model_dump') else {k:v.model_dump() if hasattr(v,'model_dump') else v for k,v in getattr(selected,field).items()},sort_keys=True)
    assert original.product_evidence==selected.product_evidence
    for key,evidence in selected.product_evidence.items():
        assert reaggregate(ProductEvidence.model_validate_json(evidence.model_dump_json()),policies)==selected.derived_metrics[key]
        assert sum(p.count for p in evidence.products)==evidence.classification_input_reads
        assert all(not p.canonical_exact_pe and not p.canonical_exact_wt for p in evidence.products if not p.assessable)
    assert MetricResult.model_validate_json(selected.model_dump_json())==selected


def test_full_product_read_through_is_symmetric_across_state_lengths():
    targets=next(ts for d,ts in indel_designs() if d['id']=='insertion_12_seed11')
    for t in targets:
        for expected,seq in [('exact_WT',t.wt_sequence),('exact_PE',t.prime_edited_sequence)]:
            assert exact_pair_class(pair(seq,length=len(seq)),targets)==expected


def test_anchor_partitions_are_per_anchor_without_preferred_common_qc(archive,tmp_path):
    root=tmp_path/'run';shutil.copytree(archive,root)
    child=root/'comparator/copy2/output/CRISPResso_on_unrouted'
    path=child/'CRISPResso2_info.json';data=json.loads(path.read_text());running=data['running_info']
    stats=data['results']['alignment_stats'];stats['counts_total']['Reference']-=1;stats['counts_discarded']['Reference']+=1
    write_json(path,data)
    path=child/running['quant_of_editing_freq_filename']
    rows=list(csv.DictReader(io.StringIO(path.read_text()),delimiter='\t'))
    for row in rows:
        if row['Amplicon']=='Reference':row['Reads_aligned']=str(int(row['Reads_aligned'])-1);row['Discarded']='1'
    buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=rows[0].keys(),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows);path.write_text(buffer.getvalue())
    path=child/running['allele_frequency_table_zip_filename']
    with zipfile.ZipFile(path) as z:rows=list(csv.DictReader(io.StringIO(z.read(running['allele_frequency_table_filename']).decode()),delimiter='\t'))
    row=next(r for r in rows if r['Reference_Name']=='Reference' and int(r['#Reads'])>1)
    row['#Reads']=str(int(row['#Reads'])-1);rows.append({**row,'Reference_Name':'DISCARDED_Reference','#Reads':'1'})
    buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=rows[0].keys(),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    with zipfile.ZipFile(path,'w') as z:z.writestr(running['allele_frequency_table_filename'],buffer.getvalue())
    result=collect(root);native=result.target_metrics.target_crispresso_native_pe
    assert native.status=='REPORTABLE' and (native.numerator,native.denominator)==(30,105)
    assert native.ordinary_classified_aligned_reads is native.ambiguous_aligned_reads is native.discarded_aligned_reads is None
    comparison=result.anchor_evidence['comparison']
    assert comparison['anchor_invariant'] and not comparison['partition_common']
    assert comparison['anchor_partitions']['copy1']['discarded_aligned_reads']==0
    assert comparison['anchor_partitions']['copy2']['discarded_aligned_reads']==1
    assert result.target_metrics.total_precise_pe.denominator==55


def test_ambiguous_bases_and_partial_products_cannot_be_rescued_by_tolerance():
    t=panel()[0]
    products=[(mutate(t.prime_edited_sequence,55,'N'),5),(t.prime_edited_sequence[25:210],7)]
    evidence=evidence_for([t],products)
    assert all(not p.assessable for p in evidence.products)
    result=aggregate_family(evidence,dict(policy_id='wide',max_extra_substitutions=100))
    assert result.status=='NOT_ASSESSABLE' and result.pe_family==result.wt_family==0
    assert result.excluded==12


def test_position_policy_uses_same_anchor_coordinates_for_shifted_copy():
    first,second=panel()
    second=second.model_copy(update={f:'ACGTA'+getattr(second,f) for f in ('wt_sequence','prime_edited_sequence')})
    targets=[first,second];seq=mutate(second.prime_edited_sequence,60)
    target=evidence_for(targets,[(seq,5)])
    copy=evidence_for(targets,[(seq,5)],scope='confident_copy',copy='copy2')
    policy=dict(policy_id='anchor-55',max_extra_substitutions=1,allowed_extra_substitution_positions=[55])
    assert aggregate_family(target,policy).pe_family==aggregate_family(copy,policy).pe_family==5
    policy['allowed_extra_substitution_positions']=[60]
    assert aggregate_family(target,policy).pe_family==aggregate_family(copy,policy).pe_family==0


def test_policy_iterables_apply_to_every_population_and_duplicate_ids_fail(archive):
    policies=(dict(policy_id=str(n),max_extra_substitutions=n) for n in (0,1))
    result=collect(archive,tolerance_policies=policies)
    assert all(set(rows)=={'0','1'} for rows in result.derived_metrics.values())
    with pytest.raises(ValueError,match='duplicate tolerance policy ID'):
        reaggregate(tolerance_fixture(),[dict(policy_id='duplicate'),dict(policy_id='duplicate')])
