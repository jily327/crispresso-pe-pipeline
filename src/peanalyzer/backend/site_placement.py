"""Site identifiability on a Core 2.3.4 conventional WT allele.

For EDNAFULL, zero positional incentives, and affine opening/extension penalties,
test whether any global alignment that changes a site can achieve the native
row's score. The supplementary classifier does not select a new alignment.
"""
from functools import lru_cache
from itertools import groupby

from Bio.Align import PairwiseAligner, substitution_matrices


def scoring_parameters(args, reference):
    vector = reference['gap_incentive']
    if isinstance(vector, dict) and vector.get('_type') == 'np.ndarray':
        vector = vector['value']
    if not isinstance(vector, list) or len(vector) != len(reference['sequence']) + 1:
        raise ValueError('Malformed native gap incentive vector')
    opening, extension = args['needleman_wunsch_gap_open'], args['needleman_wunsch_gap_extend']
    if (args['needleman_wunsch_aln_matrix_loc'] != 'EDNAFULL' or any(v != 0 for v in vector)
            or type(opening) is not int or type(extension) is not int or not opening <= extension < 0):
        return None
    return opening, extension


def weight(r, q):
    return -2 if q == 'N' else (5 if r == q else -4)


def row_score(ref, query, opening, extension):
    # Pinned global_align charges extension from the first base of a terminal gap.
    score = 0
    pos = 0
    for kind, columns in groupby(zip(ref, query), key=lambda x: 'I' if x[0]=='-' else 'D' if x[1]=='-' else 'M'):
        if kind == 'M':
            for r,q in columns:
                score += weight(r,q)
                pos += 1
        else:
            size = sum(1 for _ in columns)
            end = pos + size
            score += size * extension
            if pos and end != len(ref):
                score += opening - extension
            pos = end
    return score


@lru_cache(maxsize=256)
def _aligner(base, forbidden, reward, opening, extension):
    # X tags one WT coordinate. For a native base call forbid just that
    # pairing. For a native deletion, reward any pairing at that coordinate.
    matrix = substitution_matrices.Array(alphabet='ACGTNX', dims=2)
    for r in 'ACGTX':
        for q in 'ACGTN':
            matrix[r,q] = weight(base if r == 'X' else r, q)
            if r == 'X':
                matrix[r,q] += -reward if q == forbidden else reward if forbidden == '-' else 0
    aligner = PairwiseAligner(mode='global', substitution_matrix=matrix)
    aligner.open_gap_score = opening
    aligner.extend_gap_score = extension
    aligner.end_open_gap_score = extension
    return aligner


def uncertain_sites(ref, query, sites, bases, scoring):
    if scoring is None:
        return set(range(len(sites)))
    opening, extension = scoring
    wt, seq = ref.replace('-', ''), query.replace('-', '')
    if not seq:
        return set(range(len(sites)))
    # A literal A/C/G/T match to the full reference uniquely attains 5*length.
    if seq == wt:
        return set()
    native = row_score(ref, query, opening, extension)
    # Dominates the entire possible score range, so a forbidden/required
    # pairing cannot be offset by changes elsewhere in either sequence.
    reward = (len(seq) + len(wt) + 1) * (10 + abs(opening) + abs(extension))
    uncertain = set()
    for i,(site, base) in enumerate(zip(sites, bases)):
        if base is None:
            continue
        tagged = wt[:site] + 'X' + wt[site+1:]
        aligner = _aligner(wt[site], base, reward, opening, extension)
        threshold = native + (reward if base == '-' else 0)
        if aligner.score(tagged, seq) >= threshold:
            uncertain.add(i)
        elif base == '-':
            # An internal deletion and missing terminal coverage carry different
            # evidence. Bound the best alignment deleting a full end through the
            # site. Restoring cheaply scored new ends only raises this bound.
            for tail, removed in ((wt[:site], len(wt)-site), (wt[site+1:], site+1)):
                if tail and removed * extension + min(len(tail),len(seq)) * 5 >= native:
                    if removed * extension + aligner.score(tail, seq) >= native:
                        uncertain.add(i)
                        break
    return uncertain
