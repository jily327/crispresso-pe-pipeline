"""Conservative diagnostic-allele routing. Alignment scores never assign copies."""

import gzip
import json
import shutil
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from peanalyzer.analysis_verify import verify_analysis_output
from peanalyzer.demux_verify import sha256_file
from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.geometry import aligner, columns, geometry
from peanalyzer.schemas import Target, reverse_complement


@dataclass(frozen=True)
class RoutingPolicy:
    diagnostic_min_quality: int = 30
    min_distinguishing_sites: int = 2
    max_equivalent_alignments: int = 16
    min_alignment_identity: float = 0.8

    def __post_init__(self):
        if type(self.diagnostic_min_quality) is not int or not 0<=self.diagnostic_min_quality<=93:
            raise ValueError('quality must be a Phred integer 0..93')
        if type(self.min_distinguishing_sites) is not int or self.min_distinguishing_sites<1:
            raise ValueError('minimum diagnostic support must be a positive integer')
        if type(self.max_equivalent_alignments) is not int or self.max_equivalent_alignments<1:
            raise ValueError('alignment cap must be positive')
        if not 0<self.min_alignment_identity<=1: raise ValueError('alignment identity must be in (0,1]')


QUALIFIED_POLICY_ID = 'm312-diagnostic-q30-sites2-cap16-identity08-observed-flanks-v1'


def policy_identity(policy: RoutingPolicy) -> dict:
    qualified = policy == RoutingPolicy()
    return dict(id=QUALIFIED_POLICY_ID if qualified else 'experimental-unqualified',
                qualified=qualified, placement_contract='copy-collapsed-state-qc-v1',
                edit_coverage_contract='observed-pair-flanks-v1')


def edit_footprints(target, state, report):
    """Express each WT edit region in the state reference's coordinates.

    Empty intervals are junctions. PE inserted bases are retained here even
    though they have no WT diagnostic coordinate. Deleted PE intervals become
    junctions, which require observed reference sequence on both sides.
    """
    regions=report['copies'][target.copy_name]['edit_regions']
    if state=='WT':
        return [(r['start'],r['end']) for r in regions]
    edits=report['copies'][target.copy_name]['edits']
    anchor_to_wt=dict(report['haplotype_maps'][f'{target.copy_name}:WT'])
    pe_to_wt={p:anchor_to_wt[a] for a,p in report['haplotype_maps'][f'{target.copy_name}:PE']
              if p is not None and a is not None and anchor_to_wt.get(a) is not None}
    footprints=[]
    for region in regions:
        start,end=region['start'],region['end']
        bases=[e['pe_position'] for e in edits if e['pe_position'] is not None and
               (start<=e['wt_position']<end if e['wt_position'] is not None
                else start<=e['wt_boundary']<=end)]
        if bases:
            footprints.append((min(bases),max(bases)+1))
        else:
            boundary=min((p for p,w in pe_to_wt.items() if w>=end),default=len(target.prime_edited_sequence))
            footprints.append((boundary,boundary))
    return footprints


def copy_placements(sequence, qualities, target, mate, report, policy, engine):
    """Discard failed states, retaining *all* qualified equivalent placements.

    State scores are audit data only. No best-state/copy competition is used.
    Query coordinates are retained: identical bases at different read positions
    are not proof of an unambiguous diagnostic projection.
    """
    surviving, audit = [], []
    for state, reference in (('WT', target.wt_sequence), ('PE', target.prime_edited_sequence)):
        alignments = engine.align(reference, sequence)
        try:
            number = len(alignments)
        except OverflowError:
            number = policy.max_equivalent_alignments + 1
        entry = dict(mate=mate, copy=target.copy_name, state=state, score=alignments.score,
                     equivalent_alignments=number, MAPQ=None, XS=None, viable_placements=0,
                     covered_edit_regions=[])
        audit.append(entry)
        if number > policy.max_equivalent_alignments:
            entry['failure'] = 'STATE_EQUIVALENT_PLACEMENT_CAP_EXCEEDED'
            continue
        projection = {b:a for a,b in report['haplotype_maps'][f'{target.copy_name}:{state}']
                      if a is not None and b is not None}
        footprints=edit_footprints(target,state,report)
        for alignment in alignments:
            cols = columns(alignment)
            identity = sum(a is not None and b is not None and reference[a] == sequence[b]
                           for a,b in cols) / len(sequence)
            if identity < policy.min_alignment_identity:
                continue
            surviving.append({projection[a]:(sequence[b], qualities[b], b)
                              for a,b in cols if a in projection and b is not None})
            entry['viable_placements'] += 1
            observed=[a for a,b in cols if a is not None and b is not None]
            if observed:
                lo,hi=min(observed),max(observed)
                covered=[i for i,(start,end) in enumerate(footprints)
                         if (lo<start<=hi if start==end else lo<end and hi>=start)]
                entry['covered_edit_regions']=sorted(set(entry['covered_edit_regions'])|set(covered))
        if not entry['viable_placements']:
            entry['failure'] = 'STATE_IDENTITY_BELOW_MINIMUM'
    return surviving, audit


def decide(evidence: list[dict], copies: list[str], policy: RoutingPolicy) -> tuple[str, str | None, list[str]]:
    active = [e for e in evidence if not e['overlaps_edit'] and e['observations']]
    if not active:
        return ('EDIT_DEPENDENT_DIAGNOSTIC_LOSS' if any(e['observations'] for e in evidence) else 'NO_DIAGNOSTIC_COVERAGE'), None, copies
    if any(len({o['base'] for o in e['observations']})>1 for e in active):
        return 'MATE_CONFLICT', None, []
    usable = [e for e in active if all(o['quality']>=policy.diagnostic_min_quality for o in e['observations'])]
    if not usable:
        return 'LOW_QUALITY_DIAGNOSTICS_ONLY', None, copies
    # Even low-quality contradictory alleles veto assignment. Ignoring them can
    # turn a known mosaic into a false unique winner after a quality perturbation.
    compatible = set(copies)
    for e in active:
        compatible &= set(e['compatible_copies'])
    if not compatible:
        return ('LOW_QUALITY_CONFLICT' if len(usable)<len(active) else 'CONFLICTING_DIAGNOSTIC_EVIDENCE'), None, []
    if len(compatible)!=1:
        return 'MULTIPLE_COMPATIBLE_COPIES', None, sorted(compatible)
    candidate = next(iter(compatible))
    for other in copies:
        if other==candidate: continue
        support = sum(candidate in e['compatible_copies'] and other not in e['compatible_copies'] for e in usable)
        if support<policy.min_distinguishing_sites:
            return 'INSUFFICIENT_DIAGNOSTIC_SUPPORT', None, sorted(compatible)
    return 'ASSIGNED_COPY', candidate, [candidate]


def observed_edit_flanking(evidence, alignments, report, policy):
    """Audit observed flanks on one molecule; never bridge an unsequenced mate gap.

    Potential edit coverage in any viable state/placement triggers the flank
    requirement conservatively. Failed states contribute no coverage. Upstream
    and downstream diagnostics may be observed by different synchronized mates.
    """
    usable={e['position']:e for e in evidence if e['observations'] and not e['overlaps_edit']
            and e['mates_agree'] and all(o['quality']>=policy.diagnostic_min_quality for o in e['observations'])}
    flanking=[]
    for comparison in report['pairwise']:
        left,right=comparison['copies']
        for flank in comparison['edit_flanks']:
            copy,region=flank['copy'],flank['region']
            index=report['copies'][copy]['edit_regions'].index(region)
            covering_mates=sorted({a['mate'] for a in alignments if a['copy']==copy and
                                   index in a.get('covered_edit_regions',[])})
            observed=[d['positions'][copy] for d in report['diagnostics'] if d['position'] in usable
                      and d['usable_for_routing'] and d['alleles'][left]!=d['alleles'][right]
                      and set(usable[d['position']]['compatible_copies']) & {left,right}]
            upstream=sorted(p for p in observed if p in flank['upstream'])
            downstream=sorted(p for p in observed if p in flank['downstream'])
            flanking.append(dict(copies=[left,right],copy=copy,edit_region=region,
                                 pair_covers_edit=bool(covering_mates),covering_mates=covering_mates,
                                 observed_upstream_diagnostics=upstream,observed_downstream_diagnostics=downstream,
                                 flanking_eligible=not covering_mates or bool(upstream and downstream)))
    return flanking


def enforce_edit_flanking(decision, flanking):
    category,assigned,compatible=decision
    if category=='ASSIGNED_COPY' and any(assigned in f['copies'] and not f['flanking_eligible'] for f in flanking):
        return 'EDIT_COVERAGE_NOT_FLANKED_BY_OBSERVED_DIAGNOSTICS',None,compatible
    return decision


def route_pair(pair, targets: list[Target], report: dict, policy: RoutingPolicy) -> dict:
    identifier=read_id(pair[0],1).decode()
    copies=sorted(t.copy_name for t in targets)
    evidence=[]; scores=[]; placements={}
    engine=aligner(reads=True)
    for mate,record in enumerate(pair,1):
        sequence=record.sequence.decode().upper()
        qualities=[q-33 for q in record.quality_line.rstrip(b'\r\n')]
        if mate==2:
            sequence=reverse_complement(sequence); qualities.reverse()
        for target in sorted(targets,key=lambda t:t.copy_name):
            alternatives,audit=copy_placements(sequence,qualities,target,mate,report,policy,engine)
            scores.extend(audit)
            if not alternatives:
                return dict(read_id=identifier,category='ALIGNMENT_FAILURE',assigned_copy=None,
                            compatible_copies=copies,evidence=[],alignments=scores,
                            reason='COPY_HAS_NO_QUALIFIED_STATE_PLACEMENT')
            placements[mate,target.copy_name]=alternatives
    if len(copies)==1:
        # In an explicitly single-copy assay panel there is no competing copy;
        # retain placement checks and collapse WT/PE before assigning identity.
        for mate in (1,2):
            spans={(min(a),max(a)) for key, alternatives in placements.items() if key[0]==mate for a in alternatives if a}
            if len(spans)!=1:
                return dict(read_id=identifier,category='ALIGNMENT_FAILURE',assigned_copy=None,compatible_copies=copies,evidence=[],alignments=scores,reason='nonunique single-copy placement')
        return dict(read_id=identifier,category='ASSIGNED_COPY',assigned_copy=copies[0],compatible_copies=copies,
                    evidence=[],alignments=scores,edit_flanking=[],reason='single-copy assay panel with compatible WT/PE placements')
    for diagnostic in report['diagnostics']:
        # Edited sites cannot affect copy evidence, including placement vetoes.
        if not diagnostic['usable_for_routing']:
            continue
        observations=[]; placement_conflict=False
        position=diagnostic['position']
        for mate in (1,2):
            values=[alternative.get(position) for key, alternatives in placements.items() if key[0]==mate for alternative in alternatives]
            if len(set(values))!=1:
                placement_conflict=True
            elif values and values[0] is not None:
                base,quality,query_position=values[0]
                observations.append(dict(mate=mate,base=base,quality=quality,query_position=query_position))
        if placement_conflict:
            return dict(read_id=identifier,category='ALIGNMENT_FAILURE',assigned_copy=None,compatible_copies=copies,evidence=evidence,alignments=scores,reason='diagnostic placement differs across competing alignments')
        bases={o['base'] for o in observations}
        compatible=sorted(c for c,a in diagnostic['alleles'].items() if bases=={a})
        evidence.append(dict(position=position,observations=observations,compatible_copies=compatible,
                             both_mates_cover=len(observations)==2,mates_agree=len(bases)<=1,
                             overlaps_edit=diagnostic['overlaps_edit'],
                             ignored_for_quality=bool(observations) and any(o['quality']<policy.diagnostic_min_quality for o in observations)))
    flanking=observed_edit_flanking(evidence,scores,report,policy)
    category,assigned,compatible=enforce_edit_flanking(decide(evidence,copies,policy),flanking)
    return dict(read_id=identifier,category=category,assigned_copy=assigned,compatible_copies=compatible,
                diagnostics_covered=sum(bool(e['observations']) for e in evidence),
                diagnostics_usable=sum(bool(e['observations']) and not e['ignored_for_quality'] and not e['overlaps_edit'] for e in evidence),
                evidence=evidence,alignments=scores,edit_flanking=flanking,reason=category)


def routing_gate(*, cross_assignments: int, unsafe_assigned: int, input_pairs: int, terminal_pairs: int,
                 duplicate_ids: int=0, order_invariant: bool=True, edit_bias_controlled: bool=True,
                 lost_expected_informative: int=0, informative_evaluated: int=1) -> dict:
    checks=dict(no_cross_assignments=cross_assignments==0,ambiguous_quarantined=unsafe_assigned==0,
                counts_reconcile=input_pairs==terminal_pairs,no_duplicates=duplicate_ids==0,
                reference_order_invariant=order_invariant,edit_bias_controlled=edit_bias_controlled,
                no_unexplained_informative_loss=lost_expected_informative==0,informative_tested=informative_evaluated>0)
    return dict(routing_gate='PASS' if all(checks.values()) else 'FAIL',checks=checks)


def route_analysis(analysis_root: Path, sample_id: str, targets: list[Target], output: Path,
                   policy: RoutingPolicy=RoutingPolicy()) -> dict:
    verified=verify_analysis_output(analysis_root)
    report=geometry(targets,min_distinguishing_sites=policy.min_distinguishing_sites)
    if any(t.copy_name.casefold()=='quarantine' for t in targets): raise ValueError('quarantine is a reserved cohort name')
    if report['status']=='BLOCKED': raise ValueError(f"target geometry BLOCKED: {report['reasons']}")
    sample=verified.manifest['samples'][sample_id]
    paths=[verified.root/sample['files'][f'r{m}']['path'] for m in (1,2)]
    output=Path(output).absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(verified.root):
        raise ValueError('routing destination must be new and separate')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=f'.{output.name}.incomplete-',dir=output.parent))
    handles={}; counts=Counter(); seen=set()
    try:
        for cohort in [*(t.copy_name for t in targets),'quarantine']:
            for mate in (1,2): handles[cohort,mate]=gzip.open(stage/f'{cohort}_R{mate}.fastq.gz','wb')
        with (stage/'routing_ledger.jsonl').open('w') as ledger:
            for pair in paired_fastq(*paths):
                row=route_pair(pair,targets,report,policy)
                if row['read_id'] in seen: raise ValueError('duplicate input ID')
                seen.add(row['read_id'])
                cohort=row['assigned_copy'] or 'quarantine'
                for mate,record in enumerate(pair,1): handles[cohort,mate].write(record.to_bytes())
                counts[row['category']]+=1
                ledger.write(json.dumps(row,sort_keys=True)+'\n')
        for handle in handles.values(): handle.close()
        cohorts={}
        for cohort in [*(t.copy_name for t in targets),'quarantine']:
            files=[stage/f'{cohort}_R{m}.fastq.gz' for m in (1,2)]
            n=sum(1 for _ in paired_fastq(*files))
            cohorts[cohort]=dict(pairs=n,files={f'r{m}':dict(path=p.name,sha256=sha256_file(p),size_bytes=p.stat().st_size) for m,p in enumerate(files,1)})
        if sum(v['pairs'] for v in cohorts.values())!=sample['pairs'] or sum(counts.values())!=sample['pairs']:
            raise ValueError('routing count mismatch')
        for mate,path in enumerate(paths,1):
            if sha256_file(path)!=sample['files'][f'r{mate}']['sha256']: raise ValueError('analysis changed while routing')
        manifest=dict(schema_version=1,status='completed',scope='routing_only_not_scientific_qualification',
                      analysis_root=str(verified.root),analysis_manifest_sha256=verified.manifest_sha256,sample_id=sample_id,
                      policy=asdict(policy),policy_identity=policy_identity(policy),targets=[t.model_dump() for t in sorted(targets,key=lambda t:t.copy_name)],
                      input_pairs=sample['pairs'],categories=dict(counts),cohorts=cohorts,
                      ledger_sha256=sha256_file(stage/'routing_ledger.jsonl'))
        (stage/'geometry.json').write_text(json.dumps(report,indent=2)+'\n')
        (stage/'routing_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        stage.rename(output)
        return manifest
    finally:
        for handle in handles.values(): handle.close()
        if stage.exists(): shutil.rmtree(stage)
