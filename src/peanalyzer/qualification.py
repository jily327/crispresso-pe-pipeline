"""Synthetic-only qualification; no biological report or statistical inference."""

import csv
import json
import io
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.backend.core import run_confident_core
from peanalyzer.backend.metrics import exact_pair_class, fraction
from peanalyzer.demux import demultiplex
from peanalyzer.demux_verify import read_json
from peanalyzer.fastq import paired_fastq
from peanalyzer.geometry import geometry
from peanalyzer.routing import route_analysis, route_pair, routing_gate, RoutingPolicy
from peanalyzer.schemas import Config
from peanalyzer.synthetic_routing import write_challenges


def synthetic_exclusions(child: Path, records: list[dict], wt: str, pe: str) -> dict:
    """Origin attribution is permitted only from independent synthetic truth.

    Attribute acceptance by observed sequence multiplicities, never invent an
    alignment-failure cause. Stop if backend transformations prevent matching.
    """
    by_sequence=defaultdict(Counter)
    for record in records: by_sequence[record['sequence']][record['origin']]+=1
    info=read_json(child/'CRISPResso2_info.json')['running_info']
    with zipfile.ZipFile(child/info['allele_frequency_table_zip_filename']) as archive:
        with archive.open(info['allele_frequency_table_filename']) as handle:
            rows=list(csv.DictReader(io.TextIOWrapper(handle),delimiter='\t'))
    accepted=Counter()
    for row in rows: accepted[row['Aligned_Sequence'].replace('-','')]+=int(row['#Reads'])
    excluded=Counter();unaligned=Counter();total=Counter()
    if set(accepted)-set(by_sequence): raise ValueError('synthetic backend transformations require additional trace evidence')
    for sequence,origins in by_sequence.items():
        count=sum(origins.values());n=accepted[sequence]
        if n>count or (n not in (0,count) and len(origins)>1):
            raise ValueError('cannot resolve synthetic origin of partial sequence-class acceptance')
        for origin,amount in origins.items():
            kept=amount if n==count else n if len(origins)==1 else 0
            unaligned[origin]+=amount-kept
            if sequence not in (wt,pe): excluded[origin]+=kept
            total[origin]+=amount
    labels={'WT':'WT_derived','PE':'PE_derived','unresolved':'origin_unresolved'}
    translate=lambda values:{label:values[origin] for origin,label in labels.items()}
    return dict(evidence='independent synthetic origin + actual allele sequence multiplicities',
                aligned_exact_denominator_excluded=translate(excluded),backend_unaligned=translate(unaligned),
                all_backend_input_exact_denominator_excluded=translate(excluded+unaligned),
                failure_reason='unknown_backend_alignment_failure')


def qualify(root: Path, *, core=None, runtime_identity=None, edited_diagnostic=False) -> dict:
    root.mkdir(parents=True,exist_ok=False)
    targets,truth=write_challenges(root/'synthetic',edited_diagnostic=edited_diagnostic)
    demultiplex(r1=root/'synthetic/raw_R1.fastq.gz',r2=root/'synthetic/raw_R2.fastq.gz',
                samples_path=root/'synthetic/samples.csv',config=Config(schema_version=1),output=root/'demux')
    prepare_analysis_fastqs(root/'demux',root/'analysis')
    verified=verify_analysis_output(root/'analysis')
    manifest=route_analysis(root/'analysis','1B',targets,root/'routing')
    ledger=[json.loads(line) for line in (root/'routing/routing_ledger.jsonl').read_text().splitlines()]
    lookup={r['read_id']:r for r in truth}
    matrix=Counter();classes=defaultdict(Counter);cross=[];unsafe=[];lost=[]
    for row in ledger:
        original=lookup[row['read_id']];copy=row['assigned_copy'];cls=original['truth_class']
        matrix[original['copy'],copy or 'quarantine']+=1
        classes[cls]['total']+=1
        classes[cls][row['category']]+=1
        classes[cls]['correctly_assigned']+=int(copy==original['copy'])
        classes[cls]['cross_assigned']+=int(copy is not None and copy!=original['copy'])
        if copy is not None and copy!=original['copy']: cross.append(row['read_id'])
        if copy is not None and not original['expected_assigned']: unsafe.append(row['read_id'])
        if copy is None and original['expected_assigned']: lost.append(row['read_id'])
    paths=[verified.root/verified.manifest['samples']['1B']['files'][f'r{m}']['path'] for m in (1,2)]
    pairs=list(paired_fastq(*paths))
    report=geometry(targets);permuted=geometry(list(reversed(targets)))
    order_same=True;quality={};product=Counter();excluded_origin=Counter()
    for pair,row in zip(pairs,ledger):
        other=route_pair(pair,list(reversed(targets)),permuted,RoutingPolicy())
        order_same &= row==other
        cls=exact_pair_class(pair,targets);product[cls]+=1
        if cls not in ('exact_WT','exact_PE'): excluded_origin[lookup[row['read_id']]['origin']]+=1
    for q in (20,30,40):
        by_class=defaultdict(Counter);bad=[]
        for pair in pairs:
            row=route_pair(pair,targets,report,RoutingPolicy(diagnostic_min_quality=q))
            orig=lookup[row['read_id']]
            by_class[orig['truth_class']][row['category']]+=1
            if row['assigned_copy'] is not None and (row['assigned_copy']!=orig['copy'] or 'mosaic' in orig['truth_class'] or orig['truth_class'] in ('low_quality_conflict','mate_conflict')):
                bad.append(row['read_id'])
        quality[str(q)]={'by_class':{k:dict(v) for k,v in by_class.items()},'unsafe_assignments':bad}
    retention={k:dict(assigned=classes[k]['correctly_assigned'],total=classes[k]['total']) for k in ('WT','precise_PE','edit_loss_WT','edit_loss_PE')}
    controlled=retention['WT']==retention['precise_PE'] and retention['edit_loss_WT']==retention['edit_loss_PE']
    gate=routing_gate(cross_assignments=len(cross),unsafe_assigned=len(unsafe)+sum(len(v['unsafe_assignments']) for v in quality.values()),
        input_pairs=len(truth),terminal_pairs=len(ledger),order_invariant=order_same,edit_bias_controlled=controlled,
        lost_expected_informative=len(lost),informative_evaluated=sum(r['expected_assigned'] for r in truth))
    backend={}
    if core is not None:
        for target in targets:
            backend[target.copy_name]=run_confident_core(root/'routing',target.copy_name,root/f'backend_{target.copy_name}',core,runtime_identity=runtime_identity)
            records=[dict(sequence=lookup[r['read_id']]['fragment_sequence'],origin=lookup[r['read_id']]['origin']) for r in ledger if r['assigned_copy']==target.copy_name]
            backend[target.copy_name]['synthetic_exclusion_origins']=synthetic_exclusions(root/f'backend_{target.copy_name}/output/CRISPResso_on_confident',records,target.wt_sequence,target.prime_edited_sequence)
    # This primary exact call includes all prepared pairs, including quarantine.
    # Backend counters describe the separately identified confident subcohort only.
    overall=dict(**fraction(product['exact_PE'],product['exact_PE']+product['exact_WT']),product_classes=dict(product),
                 excluded_reads=len(truth)-product['exact_PE']-product['exact_WT'],excluded_synthetic_origin=dict(excluded_origin),
                 cohort='all prepared pairs, independent of copy routing; exact amplicon-end assessability',
                 backend_input_reads=sum(v['native']['backend_input_reads'] for v in backend.values()),
                 aligned_reads=sum(v['native']['aligned_reads'] for v in backend.values()),
                 unaligned_reads=sum(v['native']['unaligned_reads'] for v in backend.values()),
                 backend_counts_scope='confident subcohort only; not the overall exact metric denominator',
                 backend_not_submitted_pairs=len(truth)-sum(v['native']['backend_input_reads'] for v in backend.values()))
    result=dict(**gate,input_pairs=len(truth),assigned_pairs=manifest['categories'].get('ASSIGNED_COPY',0),
                quarantined_pairs=manifest['cohorts']['quarantine']['pairs'],quarantine_reasons={k:v for k,v in manifest['categories'].items() if k!='ASSIGNED_COPY'},
                cross_routed_ids=cross,unsafe_assigned_ids=unsafe,unexpected_informative_losses=lost,
                by_truth_class={k:dict(v) for k,v in classes.items()},reference_order_invariant=order_same,
                quality_sensitivity=quality,editing_state_retention=retention,copy_agnostic_exact=overall,
                backend_metrics=backend,policy=manifest['policy'])
    with (root/'routing_confusion_matrix.csv').open('w') as handle:
        writer=csv.writer(handle,lineterminator='\n');writer.writerow(['truth_copy','copy1','copy2','quarantine'])
        for copy in ('copy1','copy2'):writer.writerow([copy,*(matrix[copy,c] for c in ('copy1','copy2','quarantine'))])
    (root/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
