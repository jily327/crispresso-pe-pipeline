"""Supplementary full-allele identities for a unique simple intended insertion."""
from collections import Counter

CLASSES = ('exact_WT','exact_intended_insertion','partial_intended_insert','alternate_same_length_insert',
           'intended_insert_with_flank_substitutions','tandem_intended_insert','unexpected_longer_product',
           'other_observed_product','unresolved_aligned')


def insertion_products(wt, edited, refs, alleles):
    size = len(edited) - len(wt)
    if size <= 0:
        return None
    positions = [p for p in range(len(wt)+1) if edited[:p] + edited[p+size:] == wt]
    if len(positions) != 1:
        return None
    pos, = positions
    left, right, insert = wt[:pos], wt[pos:], edited[pos:pos+size]
    counts = Counter()
    for row in alleles:
        reference = refs.get(row['Reference_Name'])
        query = row['Aligned_Sequence']
        seq = query.replace('-','')
        aligned_ref = row.get('Reference_Sequence','')
        full = (reference is not None and len(aligned_ref) == len(query) and aligned_ref.replace('-','') == reference['sequence']
                and bool(seq) and not query.startswith('-') and not query.endswith('-') and set(seq) <= set('ACGT'))
        label = 'unresolved_aligned'
        if full:
            label = 'other_observed_product'
            if seq == wt:
                label = 'exact_WT'
            elif seq == edited:
                label = 'exact_intended_insertion'
            elif len(seq) >= len(wt) and seq.startswith(left) and seq.endswith(right):
                middle = seq[pos:len(seq)-len(right)]
                if 0 < len(middle) < size and middle in insert:
                    label = 'partial_intended_insert'
                elif len(middle) == size:
                    label = 'alternate_same_length_insert'
                elif len(middle) > size:
                    label = ('tandem_intended_insert' if middle == insert * (len(middle)//size)
                             else 'unexpected_longer_product')
            elif len(seq) == len(edited) and seq[pos:pos+size] == insert:
                label = 'intended_insert_with_flank_substitutions'
            elif len(seq) > len(edited):
                label = 'unexpected_longer_product'
        counts[label] += int(row['#Reads'])
    return dict(method='PEAnalyzer whole-product identities from exclusive native aligned allele rows',
                scope='backend aligned reads', coordinate_system='backend-oriented WT insertion boundary',
                boundary=pos, inserted_length=size,counts={k:counts[k] for k in CLASSES},
                aligned_reads=sum(counts.values()))
