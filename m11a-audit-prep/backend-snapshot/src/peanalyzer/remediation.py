"""M3.1.1 synthetic routing qualification only; no production metric reports."""

from collections import Counter
import random

from peanalyzer.backend.synthetic import design, changed
from peanalyzer.fastq import FastqRecord
from peanalyzer.geometry import geometry
from peanalyzer.routing import route_pair, RoutingPolicy
from peanalyzer.schemas import Target, reverse_complement


def pair(sequence, identifier='challenge', *, length=150, quality=40):
    reads=(sequence[:length],reverse_complement(sequence[-length:]))
    return tuple(FastqRecord(f'@{identifier}/{m}\n'.encode(),(s+'\n').encode(),b'+\n',
                            (chr(quality+33)*len(s)+'\n').encode()) for m,s in enumerate(reads,1))


def panel(positions=(40,80,165,205), *, three=False):
    first=Target.model_validate(design()['targets'][0])
    def mutate(seq, sites):
        chars=list(seq)
        for p in sites: chars[p]=changed(chars[p])
        return ''.join(chars)
    second=first.model_copy(update={'copy_name':'copy2','wt_sequence':mutate(first.wt_sequence,positions),
                                   'prime_edited_sequence':mutate(first.prime_edited_sequence,positions)})
    result=[first,second]
    if three:
        result.append(first.model_copy(update={'copy_name':'copy3','wt_sequence':mutate(first.wt_sequence,(60,185)),
                                               'prime_edited_sequence':mutate(first.prime_edited_sequence,(60,185))}))
    return result


def indel_designs():
    # All prespecified seeds/lengths are retained, including ambiguous alignments.
    # Random sequence is not selected/retried to make the alignment pass.
    for kind in ('insertion','deletion'):
        for size in (1,12,28,30,40,60):
            for seed in (11,29,47):
                rng=random.Random(seed)
                inserted=''.join(rng.choice('ACGT') for _ in range(size))
                start=122 if seed==11 else 123 if seed==29 else 124
                targets=[]
                for t in panel():
                    wt=t.wt_sequence
                    pe=wt[:start]+inserted+wt[start:] if kind=='insertion' else wt[:start]+wt[start+size:]
                    targets.append(t.model_copy(update={'prime_edited_sequence':pe}))
                # One actual shared experimental extension, across the intended edit.
                end=start+(size if kind=='insertion' else 0)+1
                extension=reverse_complement(targets[0].prime_edited_sequence[105:end])
                targets=[t.model_copy(update={'pegRNA_extension':extension}) for t in targets]
                yield dict(id=f'{kind}_{size}_seed{seed}',edit_type=kind,edit_length=size,seed=seed,
                           edit_start=start,inserted_sequence=inserted if kind=='insertion' else None),targets


def qualify_indels(router=route_pair, geometry_fn=geometry):
    results=[]
    for descriptor,targets in indel_designs():
        report=geometry_fn(targets)
        trials=[]
        for t in targets:
            for state,sequence in (('WT',t.wt_sequence),('PE',t.prime_edited_sequence)):
                for length in (100,150,len(sequence)):
                    row=router(pair(sequence,length=length),targets,report,RoutingPolicy())
                    trials.append(dict(copy=t.copy_name,state=state,mate_length=length,
                                       assigned_copy=row['assigned_copy'],category=row['category'],reason=row['reason']))
        retention={state:dict(assigned=sum(r['assigned_copy']==r['copy'] for r in trials if r['state']==state),
                              total=sum(r['state']==state for r in trials)) for state in ('WT','PE')}
        cross=sum(r['assigned_copy'] is not None and r['assigned_copy']!=r['copy'] for r in trials)
        assigned=sum(r['assigned_copy'] is not None for r in trials)
        results.append(dict(**descriptor,geometry_status=report['status'],geometry_reasons=report['reasons'],
                            retention=retention,confident_assignments=assigned,quarantine_count=len(trials)-assigned,
                            cross_assignments=cross,placement_failure_reasons=dict(Counter(r['reason'] for r in trials if r['assigned_copy'] is None)),trials=trials,
                            passed=cross==0 and (report['status']=='BLOCKED' or (retention['WT']==retention['PE'] and assigned==len(trials)))))
    return results


def chimera_challenges():
    results=[]
    for name,targets in [('flanked',panel()),('upstream',panel((20,45,70,90))),
                         ('downstream',panel((150,170,195,220))),('three_copy',panel(three=True))]:
        report=geometry(targets)
        for left in targets:
            for right in targets:
                if left==right: continue
                for state in ('WT','PE'):
                    a=left.wt_sequence if state=='WT' else left.prime_edited_sequence
                    b=right.wt_sequence if state=='WT' else right.prime_edited_sequence
                    for breakpoint in (100,140):
                        row=route_pair(pair(a[:breakpoint]+b[breakpoint:]),targets,report,RoutingPolicy())
                        blocked=report['status']=='BLOCKED'
                        results.append(dict(geometry=name,geometry_status=report['status'],left=left.copy_name,
                                            right=right.copy_name,state=state,breakpoint=breakpoint,
                                            assigned_copy=row['assigned_copy'],category=row['category'],
                                            production_admitted=not blocked and row['assigned_copy'] is not None,
                                            passed=blocked if name in ('upstream','downstream') else row['assigned_copy'] is None))
    return results


def difficult_challenges():
    """Matched backgrounds. Internal WT/PE fragments excluding edit are disclosed."""
    targets=panel();report=geometry(targets);results=[]
    for target,other in ((targets[0],targets[1]),(targets[1],targets[0])):
        for kind in ('one_error','two_errors','one_site','two_sites','low_quality',
                     'low_quality_conflict','mosaic','mate_conflict','terminal_truncation'):
            for state,seq in (('WT',target.wt_sequence),('PE',target.prime_edited_sequence)):
                if kind in ('one_error','two_errors'):
                    for pos in ((40,) if kind=='one_error' else (40,80)):
                        # Distinct from mosaics: an allele from neither copy.
                        novel=next(b for b in 'ACGT' if b not in (target.wt_sequence[pos],other.wt_sequence[pos]))
                        seq=seq[:pos]+novel+seq[pos+1:]
                if kind in ('mosaic','low_quality_conflict'):
                    seq=seq[:165]+other.wt_sequence[165]+seq[166:]
                if kind=='one_site': seq=seq[90:190]  # includes edit + diagnostic 165
                if kind=='two_sites': seq=seq[60:190]  # includes edit + diagnostics 80/165
                if kind=='terminal_truncation': seq=seq[30:210]
                records=list(pair(seq,length=200 if kind=='mate_conflict' else 150,quality=20 if kind=='low_quality' else 40))
                if kind=='low_quality_conflict':
                    rec=records[1];q=bytearray(rec.quality_line);q[239-165]=53
                    records[1]=FastqRecord(rec.header,rec.sequence_line,rec.plus,bytes(q))
                if kind=='mate_conflict':
                    rec=records[1];s=bytearray(rec.sequence_line);s[239-80]=ord(reverse_complement(other.wt_sequence[80]))
                    records[1]=FastqRecord(rec.header,bytes(s),rec.plus,rec.quality_line)
                row=route_pair(tuple(records),targets,report,RoutingPolicy())
                expect=kind in ('two_sites','terminal_truncation')
                import hashlib
                content=b''.join(r.sequence_line+r.quality_line for r in records)
                results.append(dict(copy=target.copy_name,truth_class=kind,state=state,
                                    content_sha256=hashlib.sha256(content).hexdigest(),expected_assigned=expect,
                                    assigned_copy=row['assigned_copy'],category=row['category'],
                                    passed=(row['assigned_copy']==target.copy_name if expect else row['assigned_copy'] is None)))
    return results
