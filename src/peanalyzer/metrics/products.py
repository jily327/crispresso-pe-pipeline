"""Observable products, never inferred WT/PE biological origins."""

import csv
import io
import zipfile
from collections import Counter

from peanalyzer.backend.metrics import child_file, exact_pair_class, integer
from peanalyzer.demux_verify import read_json
from peanalyzer.fastq import paired_fastq, read_id
from peanalyzer.geometry import aligner, columns
from peanalyzer.metrics.models import ProductCounts


def contradictory_products(targets):
    return bool({t.wt_sequence for t in targets} & {t.prime_edited_sequence for t in targets})


def product_counts(counts):
    included = counts['exact_wt'] + counts['exact_pe']
    return ProductCounts(**counts, classification_input_reads=sum(counts.values()),
                         denominator_exclusions=sum(counts.values()) - included)


def prepared_products(paths, targets):
    """Qualified amplicon-end coverage; count a pair once even across shared copies."""
    counts, seen = Counter(), set()
    labels = {'exact_WT': 'exact_wt', 'exact_PE': 'exact_pe',
              'state_collision': 'contradictory_state',
              'other_or_unassessable': 'unresolved_unassessable'}
    for pair in paired_fastq(*paths):
        identifier = read_id(pair[0], 1)
        if identifier in seen:
            raise ValueError('duplicate prepared pair ID')
        seen.add(identifier)
        counts[labels[exact_pair_class(pair, targets)]] += 1
    return product_counts(counts)


def aligned_products(child, target):
    """Full allele sequence identity, plus conservative observable exclusion QC.

    PE-plus-extra is established here only for complete substitution products:
    every intended changed base is present and another base differs. Ambiguous
    indel placement cannot establish that label. Other full products retain an
    observable non-exact class; partials and ambiguous backend rows are unresolved.
    """
    info = read_json(child / 'CRISPResso2_info.json')
    running, refs = info['running_info'], info['results']['refs']
    counts = Counter()
    wt, pe = target.wt_sequence, target.prime_edited_sequence
    edit_alignments = aligner().align(wt, pe)
    substitution_design = (len(edit_alignments) == 1 and
                           all(a is not None and b is not None for a, b in columns(edit_alignments[0])))
    with zipfile.ZipFile(child_file(child, running['allele_frequency_table_zip_filename'])) as archive:
        with archive.open(running['allele_frequency_table_filename']) as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle), delimiter='\t'):
                seq = row['Aligned_Sequence'].replace('-', '')
                name = row['Reference_Name']
                full = (name in refs and row['Reference_Sequence'].replace('-', '') == refs[name]['sequence']
                        and not row['Aligned_Sequence'].startswith('-')
                        and not row['Aligned_Sequence'].endswith('-') and set(seq) <= set('ACGT'))
                if name.startswith(('AMBIGUOUS_', 'DISCARDED_')):
                    label = 'unresolved_unassessable'
                elif seq == wt == pe:
                    label = 'contradictory_state'
                elif seq == wt:
                    label = 'exact_wt'
                elif seq == pe:
                    label = 'exact_pe'
                elif not full:
                    label = 'unresolved_unassessable'
                elif (substitution_design and len(wt) == len(pe) == len(seq) and wt != pe
                      and all(seq[i] == pe[i] for i in range(len(pe)) if wt[i] != pe[i])
                      and any(seq[i] != pe[i] for i in range(len(pe)) if wt[i] == pe[i])):
                    label = 'pe_plus_extra_change'
                else:
                    label = 'other_nonexact_assessable'
                counts[label] += integer(row['#Reads'])
    return product_counts(counts)
