"""Opt-in minimum-distance WT/PE families from immutable observed products.

Coordinates refer to the first copy (lexical order) WT, zero-based forward.
Copy-specific unmappable bases remain explicit; a position whitelist cannot
admit an unmappable extra substitution. Extra indels are recorded but excluded.
"""
import csv
import io
import json
import zipfile
from collections import Counter
from functools import lru_cache

from peanalyzer.fastq import paired_fastq
from peanalyzer.geometry import aligner, columns
from peanalyzer.observability import assess_pair
from peanalyzer.backend.metrics import child_file,integer
from peanalyzer.demux_verify import read_json
from peanalyzer.schemas import Target
from peanalyzer.metrics.family_models import FamilyPolicy,FamilyMetric,ObservedProduct,ProductEvidence
from peanalyzer.metrics.policy_requests import PolicyRequest, prepare_policies
from peanalyzer.metrics.products import selective_observability_reasons


@lru_cache(maxsize=4096)
def correspondence(reference,observed):
    alignments=aligner().align(reference,observed)
    if len(alignments)!=1:return None
    return tuple(columns(alignments[0]))


def candidate_evidence(sequence, targets):
    candidates=[]
    edit_signatures=set()
    anchor=sorted(targets,key=lambda t:t.copy_name)[0].wt_sequence
    for target in sorted(targets,key=lambda t:t.copy_name):
        wt,pe=target.wt_sequence,target.prime_edited_sequence
        design=correspondence(wt,pe);mapping=correspondence(anchor,wt)
        if design is None or mapping is None:
            raise ValueError('UNSUPPORTED_FAMILY_PRODUCT_DEFINITION')
        to_anchor={b:a for a,b in mapping if b is not None}
        pe_to_wt={b:a for a,b in design if b is not None}
        signature=[];previous=-1
        for a,b in design:
            if a is None or b is None or wt[a]!=pe[b]:
                position=to_anchor.get(a) if a is not None else to_anchor.get(previous,-1)
                if position is None:raise ValueError('UNSUPPORTED_FAMILY_PRODUCT_DEFINITION')
                signature.append((position,a is None,wt[a] if a is not None else '-',pe[b] if b is not None else '-'))
            if a is not None:previous=a
        edit_signatures.add(tuple(signature))
        intended={'WT':{a for a,b in design if a is not None and (b is None or wt[a]!=pe[b])},
                  'PE':{b for a,b in design if b is not None and (a is None or wt[a]!=pe[b])}}
        for state,reference in [('WT',wt),('PE',pe)]:
            alignment=correspondence(reference,sequence)
            if alignment is None:
                candidates.append(dict(copy=target.copy_name,family=state,full_product=False,
                    complete_intended_state=False,reason='NONUNIQUE_PRODUCT_ALIGNMENT',extra_substitutions=[],extra_indels=[]))
                continue
            full=bool(alignment) and all(v is not None for v in (*alignment[0],*alignment[-1]))
            lookup=dict(alignment)
            mandatory=all(lookup.get(p) is not None and sequence[lookup[p]]==reference[p] for p in intended[state])
            substitutions=[];indels=[]
            last_kind=None
            for a,b in alignment:
                if a is None or b is None:
                    kind='insertion' if a is None else 'deletion'
                    if last_kind!=kind:indels.append(dict(kind=kind,reference_positions=[],observed_positions=[],sequence=''))
                    event=indels[-1]
                    if a is not None:event['reference_positions'].append(a)
                    if b is not None:event['observed_positions'].append(b)
                    event['sequence']+=sequence[b] if a is None else reference[a]
                    last_kind=kind
                else:
                    last_kind=None
                    if reference[a]!=sequence[b]:
                        w=a if state=='WT' else pe_to_wt.get(a)
                        substitutions.append(dict(position=a,wt_position=w,anchor_position=to_anchor.get(w),
                            reference=reference[a],observed=sequence[b],at_intended_position=a in intended[state]))
            candidates.append(dict(copy=target.copy_name,family=state,full_product=full,
                complete_intended_state=mandatory,extra_substitution_count=len(substitutions),
                extra_substitutions=substitutions,extra_indel_events=len(indels),extra_indels=indels))
    if len(edit_signatures)!=1:raise ValueError('INCONSISTENT_FAMILY_INTENDED_EDIT')
    return candidates


def observed_product(sequence,count,targets,*,reason=None,mates=None,eligible=None,canonical=None):
    candidates=[]
    if sequence is not None and not set(sequence)<=set('ACGT'):
        reason=reason or 'AMBIGUOUS_OBSERVED_BASE'
    if sequence is not None and reason is None:
        candidates=candidate_evidence(sequence,targets)
        if eligible is not None:candidates=[c for c in candidates if c['copy'] in eligible]
    full=[c for c in candidates if c['full_product']]
    assessable=bool(full) and reason is None
    valid=[c for c in full if c['complete_intended_state'] and c.get('extra_indel_events')==0]
    states=[c for c in full if c['complete_intended_state']]
    minimum=min(((c['extra_indel_events'],c['extra_substitution_count']) for c in states),default=None)
    families={c['family'] for c in states if (c['extra_indel_events'],c['extra_substitution_count'])==minimum}
    state=next(iter(families)) if len(families)==1 else 'ambiguous' if families else 'neither'
    return ObservedProduct(sequence=sequence,count=count,assessable=assessable,
        reason_codes=[reason] if reason else [] if assessable else ['FULL_PRODUCT_NOT_ESTABLISHED'],
        canonical_exact_wt=canonical=='exact_WT' if canonical else any(c['family']=='WT' and c.get('extra_substitution_count')==0 for c in valid),
        canonical_exact_pe=canonical=='exact_PE' if canonical else any(c['family']=='PE' and c.get('extra_substitution_count')==0 for c in valid),
        intended_state=state,candidates=candidates,observed_mates=mates,eligible_copies=eligible or [])


def prepared_evidence(paths,targets,**identity):
    groups=Counter()
    for pair in paired_fastq(*paths):
        result=assess_pair(pair,targets)
        key=(result['sequence'],result['reason'],result['canonical'],tuple(result['eligible_copies']),
             tuple(r.sequence.decode() for r in pair) if result['reason'] else None)
        groups[key]+=1
    rows=[];reasons=[]
    for (seq,reason,canonical,eligible,mates),count in sorted(groups.items(),key=lambda x:repr(x[0])):
        try:row=observed_product(seq,count,targets,reason=reason,mates=list(mates) if mates else None,eligible=list(eligible),canonical=canonical)
        except ValueError:
            reasons.append('UNSUPPORTED_FAMILY_PRODUCT_DEFINITION')
            row=observed_product(seq,count,targets,reason='UNSUPPORTED_FAMILY_PRODUCT_DEFINITION',mates=list(mates) if mates else None)
        rows.append(row)
    return ProductEvidence(**identity,assessment_stage='prepared_pairs',classification_input_reads=sum(groups.values()),
        targets=[t.model_dump() for t in targets],products=rows,blocking_reasons=sorted(set(reasons)))


def aligned_evidence(child,target,*,targets=None,**identity):
    targets=targets or [target]
    info=read_json(child/'CRISPResso2_info.json');running=info['running_info'];refs=info['results']['refs']
    groups=Counter()
    with zipfile.ZipFile(child_file(child,running['allele_frequency_table_zip_filename'])) as z:
        rows=csv.DictReader(io.StringIO(z.read(running['allele_frequency_table_filename']).decode()),delimiter='\t')
        for row in rows:
            seq=row['Aligned_Sequence'].replace('-','');name=row['Reference_Name']
            full=(name in refs and row['Reference_Sequence'].replace('-','')==refs[name]['sequence']
                  and not row['Aligned_Sequence'].startswith('-') and not row['Aligned_Sequence'].endswith('-') and set(seq)<=set('ACGT'))
            reason=None if full else 'BACKEND_PRODUCT_NOT_FULLY_ASSESSABLE'
            groups[seq,reason]+=integer(row['#Reads'])
    products=[];reasons=[]
    for (seq,reason),count in sorted(groups.items(),key=lambda x:repr(x[0])):
        try:products.append(observed_product(seq,count,targets,reason=reason,eligible=[target.copy_name]))
        except ValueError:
            reasons.append('UNSUPPORTED_FAMILY_PRODUCT_DEFINITION')
            products.append(observed_product(seq,count,targets,reason='UNSUPPORTED_FAMILY_PRODUCT_DEFINITION',eligible=[target.copy_name]))
    return ProductEvidence(**identity,assessment_stage='backend_aligned_products',classification_input_reads=sum(groups.values()),
        targets=[t.model_dump() for t in targets],products=products,blocking_reasons=sorted(set(reasons)))


def aggregate_family(evidence,policy):
    """Reaggregate stored evidence without FASTQ or backend access."""
    evidence=ProductEvidence.model_validate(evidence.model_dump() if isinstance(evidence,ProductEvidence) else evidence)
    targets=[Target.model_validate(t) for t in evidence.targets]
    request=policy if isinstance(policy,PolicyRequest) else prepare_policies([policy],targets).requests[0]
    reasons=list(evidence.blocking_reasons)+list(request.reasons)
    # Apply the population guard to stored evidence as well as fresh evidence,
    # before any tolerance policy can aggregate a surviving biological subset.
    excluded_reasons=Counter()
    if evidence.population_scope=='target_all_prepared' and evidence.assessment_stage=='prepared_pairs':
        for row in evidence.products:
            if not row.assessable:
                for reason in row.reason_codes:excluded_reasons[reason]+=row.count
    selective=selective_observability_reasons(excluded_reasons)
    policy=request.policy
    policy_dict=policy.model_dump() if policy else request.raw
    policy_id=request.policy_id
    if policy:
        try:candidate_evidence(targets[0].wt_sequence,targets)
        except (ValueError,IndexError):reasons.append('UNSUPPORTED_FAMILY_PRODUCT_DEFINITION')
    counts=Counter()
    for row in evidence.products:
        if reasons or selective or not policy or not row.assessable or row.sequence is None:
            counts['excluded']+=row.count;continue
        # Recompute distances from immutable sequence and definitions; stored
        # candidate annotations remain explanatory evidence, not trusted calls.
        candidates=candidate_evidence(row.sequence,targets)
        eligible=[]
        for c in candidates:
            if row.eligible_copies and c['copy'] not in row.eligible_copies:continue
            if not c['full_product'] or not c['complete_intended_state'] or c.get('extra_indel_events')!=0:continue
            if c['extra_substitution_count']>policy.max_extra_substitutions:continue
            if policy.allowed_extra_substitution_positions is not None and any(s['anchor_position'] not in policy.allowed_extra_substitution_positions for s in c['extra_substitutions']):continue
            eligible.append(c)
        best=min((c['extra_substitution_count'] for c in eligible),default=None)
        families={c['family'] for c in eligible if c['extra_substitution_count']==best}
        label=next(iter(families)) if len(families)==1 else 'family_ambiguous' if families else 'excluded'
        counts[label]+=row.count
    denominator=counts['WT']+counts['PE']
    if reasons:status='BLOCKED'
    elif selective:status='NOT_ASSESSABLE';reasons=selective
    elif not denominator:status='NOT_ASSESSABLE';reasons=['ZERO_FAMILY_DENOMINATOR']
    else:status='REPORTABLE'
    return FamilyMetric(metric_name='total_pe_family' if evidence.copy_id is None else evidence.copy_id+'_pe_family',
        policy_id=policy_id,policy=policy_dict,population_id=evidence.population_id,population_scope=evidence.population_scope,
        copy_id=evidence.copy_id,status=status,numerator=counts['PE'] if status=='REPORTABLE' else None,
        denominator=denominator if status=='REPORTABLE' else None,wt_family=counts['WT'],pe_family=counts['PE'],
        family_ambiguous=counts['family_ambiguous'],excluded=counts['excluded'],classification_input_reads=evidence.classification_input_reads,
        reason_codes=sorted(set(reasons)))


def reaggregate(evidence, policies):
    """Evaluate several named policies on the same retained aggregate products."""
    evidence=ProductEvidence.model_validate(evidence.model_dump() if isinstance(evidence,ProductEvidence) else evidence)
    targets=[Target.model_validate(t) for t in evidence.targets]
    requests=prepare_policies(policies,targets)
    return {request.storage_key:aggregate_family(evidence,request) for request in requests.requests}
