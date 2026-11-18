"""Join strict per-reference Core calls to one verified merged-read population."""
import ast
from collections import Counter, defaultdict
from itertools import combinations

from peanalyzer.schemas import reverse_complement

MECHANISM = 'conservative_flanking_markers_v1'
FLANK = 5


def sequence_key(sequence):
    return min(sequence, reverse_complement(sequence))


def check_panel(targets):
    if len({t.target_name for t in targets}) != 1 or len({t.copy_name for t in targets}) != len(targets):
        raise ValueError('NUCLEASE_PANEL_IDENTITY_MISMATCH')
    if len({(t.nuclease_profile, t.tigr_window) for t in targets}) != 1:
        raise ValueError('NUCLEASE_WINDOW_POLICY_MISMATCH: select one profile and window per comparison')


def _loci(target):
    """Unique strand-independent 5+5 flanks with exactly one intervening base."""
    sequence = target.wt_sequence
    protected = list(target.window['intervals'])
    if target.nuclease_profile:
        start = target.window['target_start']
        protected = [(start - 10, start + 27)]  # identical mask for W1-W4
    candidates = defaultdict(list)
    for pos in range(FLANK, len(sequence) - FLANK):
        word = sequence[pos-FLANK:pos+FLANK+1]
        reversed_word = reverse_complement(word)
        forward = word[:FLANK] + word[FLANK+1:]
        backward = reversed_word[:FLANK] + reversed_word[FLANK+1:]
        if forward == backward:
            continue
        context = min(forward, backward)
        usable = all(pos + FLANK < start or pos - FLANK > end for start, end in protected)
        candidates[context].append((word if forward == context else reversed_word, usable))
    return {key: rows[0][0] for key, rows in candidates.items() if len(rows) == 1 and rows[0][1]}


def marker_panel(targets):
    check_panel(targets)
    loci = {t.copy_name: _loci(t) for t in targets}
    panel = []
    for left, right in combinations(sorted(loci), 2):
        sites = [(loci[left][k], loci[right][k]) for k in sorted(loci[left].keys() & loci[right])
                 if loci[left][k] != loci[right][k]]
        panel.append((left, right, sites))
    return panel


def assign_origin(sequence, names, panel):
    read_words = {sequence_key(sequence[i:i+2*FLANK+1]) for i in range(len(sequence)-2*FLANK)}
    candidates = set(names)
    for left, right, sites in panel:
        left_hits = sum(sequence_key(a) in read_words for a, _ in sites)
        right_hits = sum(sequence_key(b) in read_words for _, b in sites)
        if left_hits < 2 or right_hits:
            candidates.discard(left)
        if right_hits < 2 or left_hits:
            candidates.discard(right)
    return next(iter(candidates)) if len(candidates) == 1 else None


def local_window(target):
    """Concordance across unknown origins requires identical local WT context."""
    window = target.window
    intervals = window['intervals']
    origin = intervals[0][0]
    start = max(0, origin - FLANK)
    end = min(len(target.wt_sequence), intervals[-1][1] + 1 + FLANK)
    return (tuple((a-origin, b-origin) for a,b in intervals), origin-start, target.wt_sequence[start:end])


def observable(row, target):
    fields = row.authoritative_fields
    start, end = target.window['intervals'][0][0], target.window['intervals'][-1][1]
    # An internal deletion can span the window. Require observed bases on both
    # sides (or an observed boundary base at an amplicon end).
    positions = ast.literal_eval(fields['ref_positions'])
    bases = [(p, b) for p, b in zip(positions, fields['Aligned_Sequence']) if p >= 0 and b != '-']
    return (any(p <= max(0, start-1) and b in 'ACGT' for p, b in bases) and
            any(p >= min(len(target.wt_sequence)-1, end+1) and b in 'ACGT' for p, b in bases) and
            all(b in 'ACGT' for p,b in bases if start <= p <= end))


def event_signature(row, target):
    fields = row.authoritative_fields
    origin = target.window['intervals'][0][0]
    values = []
    for field in ('insertion_positions', 'deletion_positions', 'substitution_positions'):
        values.append(tuple(p-origin for p in ast.literal_eval(fields[field])))
    # Identical WT contexts can recur within an amplicon. The same positions in
    # the original molecule must support all references' concordant calls.
    aligned = fields['Aligned_Sequence']
    read = aligned.replace('-', '')
    reversed_read = read != sequence_key(read)
    selected = {p for a,b in target.window['intervals'] for p in range(a,b+1)}
    footprint = []
    index = 0
    for base, ref_pos in zip(aligned, ast.literal_eval(fields['ref_positions'])):
        if base != '-':
            if ref_pos in selected:
                footprint.append(len(read)-1-index if reversed_read else index)
            index += 1
    return (row.n_inserted,row.n_deleted,row.n_mutated,*values,fields['substitution_values'],tuple(footprint))


def calculate(targets, reference_runs, merged_counts):
    from peanalyzer.nuclease.models import PopulationMetrics

    names = sorted(reference_runs)
    by_name = {t.copy_name: t for t in targets}
    panel = marker_panel(targets)
    shared_window = len({local_window(t) for t in targets}) == 1
    by_sequence = defaultdict(dict)
    for name,run in reference_runs.items():
        for row in run.alleles:
            seq = sequence_key(row.authoritative_fields['Aligned_Sequence'].replace('-', ''))
            by_sequence[seq].setdefault(name, []).append(row)
    if not by_sequence.keys() <= merged_counts.keys():
        raise ValueError('NUCLEASE_ALLELE_OUTSIDE_MERGED_POPULATION')
    confident = Counter(dict.fromkeys(names, 0))
    accepted = {name: [] for name in names}
    combined = []
    ambiguous = unaligned = unavailable = ambiguous_accepted = 0
    for seq,count in sorted(merged_counts.items()):
        if seq != sequence_key(seq) or not seq or set(seq) - set('ACGTN') or count < 1:
            raise ValueError('NUCLEASE_INVALID_MERGED_POPULATION')
        hits = by_sequence.get(seq, {})
        if not hits:
            unaligned += count
            continue
        for rows in hits.values():
            if sum(row.reads for row in rows) != count:
                raise ValueError('NUCLEASE_ALLELE_MULTIPLICITY_MISMATCH')
        origin = assign_origin(seq, names, panel)
        if origin is None:
            ambiguous += count
        else:
            confident[origin] += count
        chosen = None
        if origin is not None:
            if origin in hits and all(observable(r, by_name[origin]) for r in hits[origin]):
                chosen = origin
                accepted[origin].extend(hits[origin])
        elif shared_window and set(hits) == set(names):
            signatures = {event_signature(r, by_name[k]) for k,rows in hits.items() for r in rows}
            if len(signatures) == 1 and all(observable(r, by_name[k]) for k,rows in hits.items() for r in rows):
                chosen = names[0]
                ambiguous_accepted += count
        if chosen is None:
            unavailable += count
        else:
            combined.extend(hits[chosen])
    n_input = reference_runs[names[0]].backend_input_reads
    population = dict(backend_input_reads=n_input, reads_after_preprocessing=sum(merged_counts.values()),
        unaligned_reads=unaligned, aligned_unassessable_reads=unavailable, copy_ambiguous_reads=ambiguous,
        copy_ambiguous_assessable_reads=ambiguous_accepted, confident_copy_reads=dict(confident))
    return population, PopulationMetrics.from_rows(combined), {n:PopulationMetrics.from_rows(accepted[n]) for n in names}
