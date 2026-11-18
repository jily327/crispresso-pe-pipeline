"""Coordinate transforms for the native 2.3.4 PE interface.

The supplied WT, intended product and experimental RNAs remain the source of
identity. A backend reference is usable only after both strand and the complete
extension have been checked independently for that copy.
"""
from dataclasses import dataclass
from functools import lru_cache

from peanalyzer.schemas import Target, reverse_complement


def occurrences(sequence, pattern):
    return [i for i in range(len(sequence)) if sequence.startswith(pattern, i)]


def mirror_window(window, length):
    if window in (None, '0'):
        return window
    intervals = [tuple(map(int, part.split('-'))) for part in window.split('_')]
    return '_'.join(f'{length - 1 - end}-{length - 1 - start}' for start, end in reversed(intervals))


@dataclass
class NativeReference:
    original: Target
    backend: Target
    orientation: str
    error: str | None
    extension_starts: list[int]

    def original_position(self, backend_position, *, edited=False):
        sequence = self.original.prime_edited_sequence if edited else self.original.wt_sequence
        return len(sequence) - 1 - backend_position if self.orientation == 'reverse' else backend_position

    def provenance(self):
        supported_strand = self.orientation in ('forward', 'reverse')
        return dict(orientation=self.orientation, native_error=self.error,
                    original_wt=self.original.wt_sequence, original_pe=self.original.prime_edited_sequence,
                    backend_wt=self.backend.wt_sequence if supported_strand else None,
                    backend_pe=self.backend.prime_edited_sequence if supported_strand else None,
                    original_window=self.original.quantification_window_coordinates,
                    backend_window=self.backend.quantification_window_coordinates if supported_strand else None,
                    coordinate_transform=('p -> length - 1 - p' if self.orientation == 'reverse' else
                                          'identity' if supported_strand else None),
                    coordinate_system='zero-based bases; WT and PE each use their own length',
                    extension_match=dict(status=('orientation_unresolved' if not supported_strand else
                                                  'exact' if len(self.extension_starts) == 1 else
                                                  'multiple' if self.extension_starts else 'absent'),
                                         backend_pe_starts=self.extension_starts,
                                         mismatch_count=0 if len(self.extension_starts) == 1 else None,
                                         mismatches=[]))


def native_reference(target: Target) -> NativeReference:
    spacer = target.pegRNA_spacer
    forward = occurrences(target.wt_sequence, spacer)
    reverse = occurrences(target.wt_sequence, reverse_complement(spacer))
    if not (forward or reverse):
        return NativeReference(target, target, 'neither', 'PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED', [])
    if len(forward) + len(reverse) != 1:
        return NativeReference(target, target, 'both' if forward and reverse else 'multiple',
                               'NONUNIQUE_SPACER_LOCATION', [])
    backend = target
    if reverse:
        backend = target.model_copy(update=dict(
            wt_sequence=reverse_complement(target.wt_sequence),
            prime_edited_sequence=reverse_complement(target.prime_edited_sequence),
            quantification_window_coordinates=mirror_window(target.quantification_window_coordinates, len(target.wt_sequence))))
    starts = occurrences(backend.prime_edited_sequence, reverse_complement(target.pegRNA_extension))
    error = None if len(starts) == 1 else 'PE_EXTENSION_LOCATION_UNSUPPORTED'
    return NativeReference(target, backend, 'reverse' if reverse else 'forward', error, starts)


def outside_window(edits, window):
    """An inserted base is observed only if both WT flanks are included."""
    covered = set(window)
    result = []
    for edit in edits:
        pos = edit['wt_position']
        positions = [pos] if pos is not None else [edit['wt_boundary'] - 1, edit['wt_boundary']]
        if not set(positions) <= covered:
            result.append(edit)
    return result


def unmatched_extension(plan):
    """Describe the closest contiguous placement without treating it as proof of origin."""
    pattern = reverse_complement(plan.original.pegRNA_extension)
    seq = plan.backend.prime_edited_sequence
    scores = [sum(a != b for a, b in zip(seq[i:i+len(pattern)], pattern))
              for i in range(len(seq) - len(pattern) + 1)]
    if not scores:
        return dict(status='absent', mismatch_count=None, mismatches=[], candidate_status='longer_than_reference')
    minimum = min(scores)
    if scores.count(minimum) != 1:
        return dict(status='absent', mismatch_count=None, mismatches=[], candidate_status='multiple_closest_ungapped_placements')
    start = scores.index(minimum)
    rows = []
    for offset, expected in enumerate(pattern):
        observed = seq[start+offset]
        if observed == expected:
            continue
        if plan.orientation == 'reverse':
            expected, observed = reverse_complement(expected), reverse_complement(observed)
        rows.append(dict(original_pe_position=plan.original_position(start+offset,edited=True),
                         experimental_extension_index=len(pattern)-1-offset, expected=expected, observed=observed))
    return dict(status='absent', mismatch_count=None, mismatches=[], candidate_status='unique_closest_ungapped_placement',
                candidate_mismatch_count=minimum, candidate_mismatches=rows,
                limitation='A closest contiguous sequence is descriptive only. Its biological correspondence is unverified.')


@lru_cache(maxsize=512)
def _base_map(source, destination):
    from peanalyzer.geometry import aligner, columns
    alignments = aligner().align(source, destination)
    if len(alignments) != 1:
        return None
    return {a: b for a, b in columns(alignments[0]) if a is not None}


def extension_polymorphism(plan, peers):
    """Project a unique exact experimental extension from another panel copy.

    A natural SNP requires concordant WT and intended bases on *both* copies.
    Disagreement between anchors, gaps and nonunique alignments are insufficient.
    Mismatch bases and positions are reported on the supplied strand as well as
    positions in the experimental 5'-to-3' extension. No RTT/PBS split is inferred.
    """
    if plan.orientation not in ('forward', 'reverse') or plan.extension_starts:
        return None
    target = plan.backend
    experimental = reverse_complement(target.pegRNA_extension)
    candidates = []
    for donor in peers:
        if donor.error or donor.original.copy_name == target.copy_name:
            continue
        donor_target = donor.backend
        mapping = _base_map(donor_target.prime_edited_sequence, target.prime_edited_sequence)
        left = donor.extension_starts[0]
        if mapping is None:
            return None
        positions = [mapping.get(p) for p in range(left, left + len(experimental))]
        if None in positions or positions != list(range(positions[0], positions[0] + len(experimental))):
            return None
        to_wt = _base_map(target.prime_edited_sequence, target.wt_sequence)
        donor_wt = _base_map(donor_target.prime_edited_sequence, donor_target.wt_sequence)
        if to_wt is None or donor_wt is None:
            return None
        rows = []
        for offset, pos in enumerate(positions):
            expected = experimental[offset]
            observed = target.prime_edited_sequence[pos]
            if observed == expected:
                continue
            wt_pos = to_wt.get(pos)
            donor_pos = donor_wt.get(left + offset)
            natural = (wt_pos is not None and target.wt_sequence[wt_pos] == observed
                       and donor_pos is not None and donor_target.wt_sequence[donor_pos] == expected)
            if plan.orientation == 'reverse':
                expected, observed = reverse_complement(expected), reverse_complement(observed)
            rows.append(dict(original_pe_position=plan.original_position(pos, edited=True),
                             original_wt_position=plan.original_position(wt_pos) if wt_pos is not None else None,
                             experimental_extension_index=len(experimental)-1-offset,
                             expected=expected, observed=observed, natural_copy_snp=natural))
        candidates.append((donor.original.copy_name, rows))
    if not candidates or not candidates[0][1] or any(rows != candidates[0][1] for _, rows in candidates):
        return None
    rows = candidates[0][1]
    return dict(status='copy_polymorphism' if all(r['natural_copy_snp'] for r in rows) else 'reference_mismatch',
                anchor_copies=[name for name, _ in candidates], mismatch_count=len(rows), mismatches=rows,
                region='experimental extension; RTT/PBS split unspecified')
