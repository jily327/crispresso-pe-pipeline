"""Closed scientific argument contract for the pinned Core 2.3.4 nuclease path.

Values are the resolved JSON values, including the string "None" emitted for
some unset options. See docs/m81-backend-qualification.md for the source inventory.
This gate validates caller configuration and populations; it never calls variants.
"""

QUALIFIED_ARGUMENTS = {
    # Single WT reference and no guide/HDR/prime-editing reference construction.
    'amplicon_name': 'Reference',
    'auto': False,
    'expected_hdr_amplicon_seq': '',
    'guide_seq': '',
    'flexiguide_seq': 'None',
    'flexiguide_homology': 80,
    'flexiguide_gap_open_penalty': -20,
    'flexiguide_gap_extend_penalty': -2,
    'prime_editing_pegRNA_spacer_seq': '',
    'prime_editing_pegRNA_extension_seq': '',
    'prime_editing_pegRNA_scaffold_seq': '',
    'prime_editing_nicking_guide_seq': '',
    'prime_editing_override_prime_edited_ref_seq': '',
    'prime_editing_override_sequence_checks': False,
    'prime_editing_pegRNA_extension_quantification_window_size': 5,
    'prime_editing_pegRNA_scaffold_min_match_length': 1,
    'prime_editing_gap_open_penalty': -50,
    'prime_editing_gap_extend_penalty': 0,
    # Window and classification semantics, including exceptional populations.
    'exclude_bp_from_left': 0,
    'exclude_bp_from_right': 0,
    'quantification_window_center': '-3',
    'quantification_window_size': '1',
    'discard_guide_positions_overhanging_amplicon_edge': False,
    'ignore_substitutions': False,
    'ignore_insertions': False,
    'ignore_deletions': False,
    'use_legacy_insertion_quantification': False,
    'discard_indel_reads': False,
    'expand_ambiguous_alignments': False,
    'assign_ambiguous_alignments_to_first_reference': False,
    'crispresso1_mode': False,
    'write_detailed_allele_table': True,
    # Preserve the existing paired FASTQ preprocessing and alignment path.
    'split_interleaved_input': False,
    'trim_sequences': False,
    'crispresso_merge': False,
    'force_merge_pairs': False,
    'fastp_command': 'fastp',
    'fastp_options_string': '',
    'min_paired_end_reads_overlap': 10,
    'min_average_read_quality': 0,
    'min_single_bp_quality': 0,
    'min_bp_quality_or_N': 0,
    'bam_input': '',
    'bam_chr_loc': '',
    'samtools_exclude_flags': '0',
    'bam_output': False,
    'fastq_output': False,
    # Alignment eligibility, score matrix, gap placement and strand seeding.
    'amplicon_min_alignment_score': '',
    'default_min_aln_score': 60,
    'needleman_wunsch_gap_open': -20,
    'needleman_wunsch_gap_extend': -2,
    'needleman_wunsch_gap_incentive': 1,
    'needleman_wunsch_aln_matrix_loc': 'EDNAFULL',
    'aln_seed_count': 5,
    'aln_seed_len': 10,
    'aln_seed_min': 2,
}


def scientific_arguments(wt_sequence, coordinates):
    """Return the complete target-dependent scientific backend identity."""
    return dict(QUALIFIED_ARGUMENTS, amplicon_seq=wt_sequence,
                quantification_window_coordinates=coordinates)


def validate_arguments(arguments, expected):
    """Check resolved values and types, never just the constructed argv."""
    if not isinstance(arguments, dict):
        raise ValueError('BACKEND_ARGUMENTS_INVALID')
    for name, value in expected.items():
        if name not in arguments or type(arguments[name]) is not type(value) or arguments[name] != value:
            raise ValueError('UNQUALIFIED_NUCLEASE_CONFIGURATION: ' + name)


def validate_population(ambiguous, discarded):
    """Exceptional aligned reads are unqualified, not biological outcomes."""
    if ambiguous or discarded:
        raise ValueError('UNQUALIFIED_NUCLEASE_POPULATION: '
                         f'ambiguous_aligned_reads={ambiguous}; discarded_aligned_reads={discarded}')
