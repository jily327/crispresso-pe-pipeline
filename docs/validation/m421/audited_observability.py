"""State-symmetric product reconstruction and pinned backend merge geometry."""

from collections import Counter
from functools import lru_cache

from peanalyzer.fastq import paired_fastq
from peanalyzer.schemas import reverse_complement

MIN_EXACT_PAIR_OVERLAP = 10
# Measured through production Core 2.3.4 / fastp 1.3.3, not a fastp default.
MIN_PINNED_BACKEND_OVERLAP = 11


@lru_cache(maxsize=8192)
def reconstruct(left, right):
    """Reject distinct long placements and short period-shifted alternatives.

    A chance short border of an otherwise aperiodic long overlap is not a
    tandem-repeat length ambiguity. A repeated period fitting at least twice
    in the observed overlap is; it permits a different complete molecule.
    """
    overlaps = [n for n in range(1, min(len(left), len(right))+1) if left[-n:]==right[:n]]
    qualified = [n for n in overlaps if n>=MIN_EXACT_PAIR_OVERLAP]
    if not qualified:
        return None, 'INSUFFICIENT_EXACT_PAIR_OVERLAP'
    if len(qualified)!=1:
        return None, 'AMBIGUOUS_PRODUCT_RECONSTRUCTION'
    n=qualified[0]
    if any(0<n-short<=n//2 for short in overlaps if short<n):
        return None, 'PERIODIC_PRODUCT_RECONSTRUCTION'
    return left+right[n:], None


@lru_cache(maxsize=8192)
def reference_observable(sequence, left_length, right_length):
    # A fully observed shorter state can end before the sequencing read length.
    # Read-through must not exclude that counterfactual while retaining the
    # longer state. Actual observed adapter/extra sequence still fails identity.
    left_length=min(left_length,len(sequence));right_length=min(right_length,len(sequence))
    reconstructed,_=reconstruct(sequence[:left_length],sequence[-right_length:])
    return reconstructed==sequence


def state_geometry(targets, left_length, right_length):
    """Compare states within each copy; cross-copy length equality is unnecessary."""
    rows=[]
    for target in targets:
        wt,pe=target.wt_sequence,target.prime_edited_sequence
        exact=[reference_observable(s,left_length,right_length) for s in (wt,pe)]
        merge=[left_length+right_length-len(s)>=MIN_PINNED_BACKEND_OVERLAP for s in (wt,pe)]
        rows.append(dict(copy=target.copy_name,wt_length=len(wt),pe_length=len(pe),
                         exact_states=exact,backend_merge_states=merge))
    return rows


def assess_pair(pair, targets):
    left=pair[0].sequence.decode().upper()
    right=reverse_complement(pair[1].sequence.decode().upper())
    rows=state_geometry(targets,len(left),len(right))
    asymmetric=[r for r in rows if len(set(r['exact_states']))>1]
    sequence,reason=reconstruct(left,right)
    if asymmetric:
        reason=('STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY' if any(r['wt_length']!=r['pe_length'] for r in asymmetric)
                else 'STATE_DEPENDENT_PRODUCT_OBSERVABILITY')
    eligible={r['copy'] for r in rows if all(r['exact_states'])}
    if not reason and not eligible:
        reason='REFERENCE_PRODUCT_NOT_OBSERVABLE'
    states=set()
    if not reason:
        for target in targets:
            if target.copy_name not in eligible: continue
            if sequence==target.wt_sequence:states.add('exact_WT')
            if sequence==target.prime_edited_sequence:states.add('exact_PE')
    canonical=(next(iter(states)) if len(states)==1 else 'state_collision' if states else 'other_or_unassessable')
    return dict(sequence=sequence,reason=reason,canonical=canonical,eligible_copies=sorted(eligible),geometry=rows)


def population_observability(paths, targets):
    lengths=Counter();ambiguity=Counter()
    for pair in paired_fastq(*paths):
        lengths[len(pair[0].sequence),len(pair[1].sequence)]+=1
        _,reason=reconstruct(pair[0].sequence.decode().upper(),reverse_complement(pair[1].sequence.decode().upper()))
        if reason in ('AMBIGUOUS_PRODUCT_RECONSTRUCTION','PERIODIC_PRODUCT_RECONSTRUCTION'):ambiguity[reason]+=1
    rows=[];backend=Counter();exact=Counter()
    for (left,right),count in sorted(lengths.items()):
        copies=state_geometry(targets,left,right)
        rows.append(dict(left_length=left,right_length=right,pairs=count,copies=copies))
        if any(len(set(c['backend_merge_states']))>1 for c in copies):
            backend['STATE_DEPENDENT_BACKEND_MERGEABILITY']+=count
        if any(len(set(c['exact_states']))>1 for c in copies):
            exact['STATE_DEPENDENT_PRODUCT_OBSERVABILITY']+=count
    return dict(pair_geometries=rows,backend_reason_counts=dict(backend),exact_reason_counts=dict(exact),
                reconstruction_ambiguity_reason_counts=dict(ambiguity),
                cross_copy_length_divergence=len({len(t.wt_sequence) for t in targets})>1,
                exact_minimum_overlap=MIN_EXACT_PAIR_OVERLAP,backend_minimum_overlap=MIN_PINNED_BACKEND_OVERLAP)
