"""State-symmetric product reconstruction and pinned backend merge geometry."""

from collections import Counter
from functools import lru_cache

from peanalyzer.fastq import paired_fastq
from peanalyzer.schemas import reverse_complement

MIN_EXACT_PAIR_OVERLAP = 10
MIN_ALTERNATIVE_PAIR_OVERLAP = 4
# Measured through production Core 2.3.4 / fastp 1.3.3, not a fastp default.
MIN_PINNED_BACKEND_OVERLAP = 11


@lru_cache(maxsize=8192)
def reconstruct(left, right):
    """Reject distinct long placements and short period-shifted alternatives.

    A self-consistent alternative with at least four matching bases supports a
    different complete product length, even if its period exceeds half the
    qualifying overlap. Shorter borders also reject a demonstrable repeated
    period fitting twice. No motif or reference length selects a placement.
    """
    overlaps = [n for n in range(1, min(len(left), len(right))+1) if left[-n:]==right[:n]]
    qualified = [n for n in overlaps if n>=MIN_EXACT_PAIR_OVERLAP]
    if not qualified:
        return None, 'INSUFFICIENT_EXACT_PAIR_OVERLAP'
    if len(qualified)!=1:
        return None, 'AMBIGUOUS_PRODUCT_RECONSTRUCTION'
    n=qualified[0]
    if any(short>=MIN_ALTERNATIVE_PAIR_OVERLAP or 0<n-short<=n//2
           for short in overlaps if short<n):
        return None, 'PERIODIC_PRODUCT_RECONSTRUCTION'
    return left+right[n:], None


@lru_cache(maxsize=8192)
def reconstruct_product(left, right, references):
    """Exact candidate products with uniquely established terminal read-through.

    Reads retain their amplicon-end 5-prime anchors: left is forward, right is
    reverse-complemented. Only a complete exact candidate in an overlong mate
    can establish a 3-prime boundary. Both mates must match their entire
    biological portions, and their clipped overlap must pass the unchanged
    conservative reconstructor. All WT/PE/copy sequences are considered together.
    Distinct supported products or additional complete-reference occurrences
    reject boundary ambiguity. No selected allele, motif or vendor determines
    trimming. Non-exact products never gain exact status through this path.
    """
    original = reconstruct(left, right)
    supported = set()
    ambiguous = False
    for reference in references:
        size = len(reference)
        if len(left) <= size and len(right) <= size:
            continue
        clipped_left, clipped_right = left[:size], right[-size:]
        if not reference.startswith(clipped_left) or not reference.endswith(clipped_right):
            continue
        sequence, reason = reconstruct(clipped_left, clipped_right)
        if reason or sequence != reference:
            continue
        supported.add(reference)
    if not supported:
        return original
    # Inspect every complete candidate occurrence, including alternative copies
    # and states inside an overhang; never choose the first or longest match.
    for reference in references:
        for read, expected in ((left, 0), (right, len(right)-len(reference))):
            start = read.find(reference)
            while start >= 0:
                if start != expected:
                    ambiguous = True
                start = read.find(reference, start+1)
    if ambiguous or len(supported) != 1:
        return None, 'AMBIGUOUS_PRODUCT_RECONSTRUCTION'
    return next(iter(supported)), None


@lru_cache(maxsize=8192)
def reference_observable(sequence, left_length, right_length):
    # A fully observed shorter state can end before the sequencing read length.
    # Read-through must not exclude that counterfactual while retaining the
    # longer state. Actual read-through additionally requires unique exact
    # candidate support in reconstruct_product(); geometry alone never trims.
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


def copy_dependent(rows, field):
    """Compare candidate eligibility, not absolute lengths, across copies."""
    return len({tuple(row[field]) for row in rows})>1


@lru_cache(maxsize=128)
def _strand_words(definitions):
    """Edit-independent words in either copy, excluding every opposite-strand word."""
    width = 10
    def words(ref):
        return {ref[i:i+width] for i in range(len(ref) - width + 1)}
    invariant, possible = set(), set()
    for wt, pe in definitions:
        wt_words, pe_words = words(wt), words(pe)
        invariant.update(wt_words & pe_words)
        possible.update(wt_words | pe_words)
    forward = invariant - {reverse_complement(word) for word in possible}
    return width, forward, {reverse_complement(word) for word in forward}


@lru_cache(maxsize=16384)
def _read_strand(dna, definitions):
    width, forward, reverse = _strand_words(definitions)
    seen = set()
    for start in range(len(dna) - width + 1):
        word = dna[start:start+width]
        if word in forward:
            seen.add(1)
        if word in reverse:
            seen.add(-1)
        if len(seen) == 2:
            return 0
    return next(iter(seen)) if seen else 0


def physical_forward_mate(pair, targets):
    """Require complementary directional evidence in the two physical mates."""
    definitions = tuple(sorted((t.wt_sequence, t.prime_edited_sequence) for t in targets))
    max_length = max(max(len(wt), len(pe)) for wt, pe in definitions)
    strands = tuple(_read_strand(rec.sequence[:max_length].decode().upper(), definitions) for rec in pair)
    if strands == (1, -1):
        return 1
    if strands == (-1, 1):
        return 2
    return None


def oriented_pair(pair, targets):
    forward = physical_forward_mate(pair, targets)
    # Use the original ordering only to retain diagnostic information from a
    # failed reconstruction. Unknown orientation can never admit a product.
    first, second = (pair[1], pair[0]) if forward == 2 else pair
    return first.sequence.decode().upper(), reverse_complement(second.sequence.decode().upper()), forward


def assess_pair(pair, targets):
    left, right, forward = oriented_pair(pair, targets)
    rows=state_geometry(targets,len(left),len(right))
    asymmetric=[r for r in rows if len(set(r['exact_states']))>1]
    references=tuple(sorted({s for t in targets for s in (t.wt_sequence,t.prime_edited_sequence)}))
    sequence,reason=reconstruct_product(left,right,references)
    if forward is None:
        sequence, reason = None, reason or 'UNRESOLVED_READ_ORIENTATION'
    if asymmetric:
        reason=('STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY' if any(r['wt_length']!=r['pe_length'] for r in asymmetric)
                else 'STATE_DEPENDENT_PRODUCT_OBSERVABILITY')
    elif copy_dependent(rows,'exact_states'):
        reason='COPY_DEPENDENT_PRODUCT_OBSERVABILITY'
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
    return dict(sequence=sequence,reason=reason,canonical=canonical,eligible_copies=sorted(eligible),geometry=rows,forward_mate=forward)


def population_observability(paths, targets):
    lengths=Counter();ambiguity=Counter()
    references=tuple(sorted({s for t in targets for s in (t.wt_sequence,t.prime_edited_sequence)}))
    orientation = Counter()
    for pair in paired_fastq(*paths):
        left, right, forward = oriented_pair(pair, targets)
        orientation[f'R{forward}_forward' if forward else 'unresolved'] += 1
        lengths[len(left),len(right)]+=1
        _,reason=reconstruct_product(left,right,references)
        if reason in ('AMBIGUOUS_PRODUCT_RECONSTRUCTION','PERIODIC_PRODUCT_RECONSTRUCTION'):ambiguity[reason]+=1
    rows=[];backend=Counter();exact=Counter()
    for (left,right),count in sorted(lengths.items()):
        copies=state_geometry(targets,left,right)
        rows.append(dict(left_length=left,right_length=right,pairs=count,copies=copies))
        if any(len(set(c['backend_merge_states']))>1 for c in copies):
            backend['STATE_DEPENDENT_BACKEND_MERGEABILITY']+=count
        if copy_dependent(copies,'backend_merge_states'):
            backend['COPY_DEPENDENT_BACKEND_MERGEABILITY']+=count
        if copy_dependent(copies,'exact_states'):
            exact['COPY_DEPENDENT_PRODUCT_OBSERVABILITY']+=count
        if any(len(set(c['exact_states']))>1 for c in copies):
            exact['STATE_DEPENDENT_PRODUCT_OBSERVABILITY']+=count
    return dict(pair_geometries=rows,physical_orientation=dict(orientation),backend_reason_counts=dict(backend),exact_reason_counts=dict(exact),
                reconstruction_ambiguity_reason_counts=dict(ambiguity),
                cross_copy_length_divergence=len({len(t.wt_sequence) for t in targets})>1,
                exact_minimum_overlap=MIN_EXACT_PAIR_OVERLAP,backend_minimum_overlap=MIN_PINNED_BACKEND_OVERLAP)
