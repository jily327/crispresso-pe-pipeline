"""Read the deposited EPSPS sequences at each declared site independently of the candidate caller."""
from collections import Counter

from peanalyzer.fastq import paired_fastq
from peanalyzer.schemas import reverse_complement


def site_oracle(reference, a, b):
    # This reference is fixed by the archive identity before the experiment.
    # Each pattern uses only the local flank. Enumerate the two design bases even
    # if the other intended site lies outside this site's 25-base interval.
    patterns = []
    for site in (a, b):
        words = set()
        for left in ('G', 'A'):
            for right in ('G', 'A'):
                seq = reference[:a] + left + reference[a+1:b] + right + reference[b+1:]
                words.add(seq[site-12:site+13])
        patterns.append(tuple((w, reverse_complement(w), w[12] == 'A') for w in words))
    return patterns


def count_marginal(sample, patterns):
    counts = Counter()
    for first, second in paired_fastq(sample.r1, sample.r2):
        s1, s2 = first.sequence[26:].decode(), second.sequence[27:].decode()
        for j, motif in enumerate(patterns):
            calls = []
            for dna, quality, reverse in ((s1, first.quality_line[26:], True),
                                          (s2, second.quality_line[27:], False)):
                matches = [(pos + 12, edit) for forward, rc, edit in motif
                           for word in [rc if reverse else forward]
                           for pos in [dna.find(word)] if pos >= 0 and dna.count(word) == 1]
                if len(matches) == 1 and quality[matches[0][0]] >= 63:
                    calls.append(matches[0][1])
            if len(calls) == 2 and calls[0] == calls[1]:
                counts[j, calls[0]] += 1
    return [(counts[j, True], counts[j, True] + counts[j, False]) for j in (0, 1)]
