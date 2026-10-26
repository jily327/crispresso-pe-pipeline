# M8.1: closed nuclease backend qualification

This is a narrow follow-up to `be4222b43db6926e3b89d1d09310e5581bc3f258`.
Version remains 0.8.0. CRISPResso2 2.3.4 remains the sole variant caller; no PE
science, nuclease numerator, denominator, geometry, thresholds or default calls change.

## Qualification gates

`running_info.args.value` in the completed `CRISPResso2_info.json` must contain
every scientific field below with exactly the qualified JSON value **and type**.
Missing fields, bool/int substitutions, and wrapper-injected values fail with
`UNQUALIFIED_NUCLEASE_CONFIGURATION: <field>`. Constructed argv and a version
probe are insufficient. The same check runs when loading serialized nuclease
results, including downstream aggregation/reporting.

Generic `aligned_partition` reconciliation is retained unchanged. After it proves
ordinary/ambiguous/discarded row inventories agree with Core JSON and TSV counts,
M8.1 requires `ambiguous_aligned_reads == discarded_aligned_reads == 0`.
Otherwise `UNQUALIFIED_NUCLEASE_POPULATION` prevents publication. The result
model independently enforces the same zero-population gate. No discarded indels
are reconstructed, rescued, relabeled or silently removed from a denominator.

Primary numerator remains the sum of ordinary authoritative `#Reads` satisfying
`n_inserted > 0 OR n_deleted > 0`, counting each row once. Denominator remains
all authoritative aligned reads. In an accepted result these are exactly the
ordinary classified population. All substitutions, overlapping secondary counts,
net-zero indels, window-aware sizes, 0/0 end exclusions and current insertion
semantics remain unchanged. Nuclease mode never uses the PE router.

## Scientific resolved-argument inventory

The inventory was checked against the pinned runtime's `args.json`, actual
paired-read `CRISPResso2_info.json`, `CRISPRessoCORE.py`,
`CRISPRessoShared.py`, and `CRISPRessoCOREResources.pyx`.
Core lines 766-839 determine alignment/reference/classification; 2890-3266 cover
guide/window construction; 3667-3855 cover preprocessing, merging, filtering and
alignment-path selection; 4093-4114 separate exceptional populations. Shared
lines 1783-1826 resolve explicit windows/end exclusions. COREResources lines
103-163 implement current event counting. `min_bp_quality_or_N` is scientifically
active after merging: Core lines 3800-3823 replace low-quality bases with N.

The invocation keeps its existing qualified options; new restrictions verify
previously implicit defaults. This avoids silently changing M8 science. Empty
strings and the literal string `"None"` below are the values recorded by this
pinned runtime, not interchangeable nulls. The complete set is held centrally in
`nuclease.qualification.scientific_arguments`; it is included in the target
scientific identity and thus routing-identity/metrics stage signatures.

| Resolved argument | Required value | Selection | Scientific reason |
| --- | --- | --- | --- |
| `aln_seed_count` | `5` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `aln_seed_len` | `10` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `aln_seed_min` | `2` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `amplicon_min_alignment_score` | `""` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `amplicon_name` | `"Reference"` | Require qualified 2.3.4 default | Single supplied WT reference identity; forbid inferred/additional references. |
| `amplicon_seq` | `<target.wt_sequence>` | Explicit existing invocation | Single supplied WT reference identity; forbid inferred/additional references. |
| `assign_ambiguous_alignments_to_first_reference` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `auto` | `false` | Require qualified 2.3.4 default | Single supplied WT reference identity; forbid inferred/additional references. |
| `bam_chr_loc` | `""` | Require qualified 2.3.4 default | Alternative input/filtering or Core alignment-processing paths are not the qualified FASTQ path. |
| `bam_input` | `""` | Require qualified 2.3.4 default | Alternative input/filtering or Core alignment-processing paths are not the qualified FASTQ path. |
| `bam_output` | `false` | Require qualified 2.3.4 default | Alternative input/filtering or Core alignment-processing paths are not the qualified FASTQ path. |
| `crispresso1_mode` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `crispresso_merge` | `false` | Require qualified 2.3.4 default | Paired-read preparation/merging determines which sequences and reads reach alignment. |
| `default_min_aln_score` | `60` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `discard_guide_positions_overhanging_amplicon_edge` | `false` | Require qualified 2.3.4 default | Exact window inclusion and guide-window fallback controls; final include indices are also checked. |
| `discard_indel_reads` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `exclude_bp_from_left` | `0` | Explicit existing invocation | Exact window inclusion and guide-window fallback controls; final include indices are also checked. |
| `exclude_bp_from_right` | `0` | Explicit existing invocation | Exact window inclusion and guide-window fallback controls; final include indices are also checked. |
| `expand_ambiguous_alignments` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `expected_hdr_amplicon_seq` | `""` | Require qualified 2.3.4 default | Single supplied WT reference identity; forbid inferred/additional references. |
| `fastp_command` | `"fastp"` | Require qualified 2.3.4 default | Paired-read preparation/merging determines which sequences and reads reach alignment. |
| `fastp_options_string` | `""` | Require qualified 2.3.4 default | Paired-read preparation/merging determines which sequences and reads reach alignment. |
| `fastq_output` | `false` | Require qualified 2.3.4 default | Alternative input/filtering or Core alignment-processing paths are not the qualified FASTQ path. |
| `flexiguide_gap_extend_penalty` | `-2` | Require qualified 2.3.4 default | No guide/flexible-guide inference; prevent guide-dependent cut incentives and window changes. |
| `flexiguide_gap_open_penalty` | `-20` | Require qualified 2.3.4 default | No guide/flexible-guide inference; prevent guide-dependent cut incentives and window changes. |
| `flexiguide_homology` | `80` | Require qualified 2.3.4 default | No guide/flexible-guide inference; prevent guide-dependent cut incentives and window changes. |
| `flexiguide_seq` | `"None"` | Require qualified 2.3.4 default | No guide/flexible-guide inference; prevent guide-dependent cut incentives and window changes. |
| `force_merge_pairs` | `false` | Require qualified 2.3.4 default | Paired-read preparation/merging determines which sequences and reads reach alignment. |
| `guide_seq` | `""` | Require qualified 2.3.4 default | No guide/flexible-guide inference; prevent guide-dependent cut incentives and window changes. |
| `ignore_deletions` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `ignore_insertions` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `ignore_substitutions` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `min_average_read_quality` | `0` | Require qualified 2.3.4 default | Read filtering or N masking can change calls and denominator; retain zero qualified thresholds. |
| `min_bp_quality_or_N` | `0` | Require qualified 2.3.4 default | Read filtering or N masking can change calls and denominator; retain zero qualified thresholds. |
| `min_paired_end_reads_overlap` | `10` | Require qualified 2.3.4 default | Paired-read preparation/merging determines which sequences and reads reach alignment. |
| `min_single_bp_quality` | `0` | Require qualified 2.3.4 default | Read filtering or N masking can change calls and denominator; retain zero qualified thresholds. |
| `needleman_wunsch_aln_matrix_loc` | `"EDNAFULL"` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `needleman_wunsch_gap_extend` | `-2` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `needleman_wunsch_gap_incentive` | `1` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `needleman_wunsch_gap_open` | `-20` | Require qualified 2.3.4 default | Alignment eligibility, strand/seeds, scoring and gap placement can change authoritative alleles. |
| `prime_editing_gap_extend_penalty` | `0` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_gap_open_penalty` | `-50` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_nicking_guide_seq` | `""` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_override_prime_edited_ref_seq` | `""` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_override_sequence_checks` | `false` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_pegRNA_extension_quantification_window_size` | `5` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_pegRNA_extension_seq` | `""` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_pegRNA_scaffold_min_match_length` | `1` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_pegRNA_scaffold_seq` | `""` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `prime_editing_pegRNA_spacer_seq` | `""` | Require qualified 2.3.4 default | Keep prime-editing reference, scaffold classification and PE alignment/window branches disabled at qualified defaults. |
| `quantification_window_center` | `"-3"` | Require qualified 2.3.4 default | Exact window inclusion and guide-window fallback controls; final include indices are also checked. |
| `quantification_window_coordinates` | `<target.window.coordinates>` | Explicit existing invocation | Exact window inclusion and guide-window fallback controls; final include indices are also checked. |
| `quantification_window_size` | `"1"` | Require qualified 2.3.4 default | Exact window inclusion and guide-window fallback controls; final include indices are also checked. |
| `samtools_exclude_flags` | `"0"` | Require qualified 2.3.4 default | Alternative input/filtering or Core alignment-processing paths are not the qualified FASTQ path. |
| `split_interleaved_input` | `false` | Require qualified 2.3.4 default | Paired-read preparation/merging determines which sequences and reads reach alignment. |
| `trim_sequences` | `false` | Require qualified 2.3.4 default | Paired-read preparation/merging determines which sequences and reads reach alignment. |
| `use_legacy_insertion_quantification` | `false` | Require qualified 2.3.4 default | Preserve allele classes, insertion semantics, aligned population and no-discard/no-ambiguity policy. |
| `write_detailed_allele_table` | `true` | Explicit existing invocation | Required authoritative integer calls and event fields for reconciliation. |

There are **58** fields, including the two target-dependent values.
`fastp_command=fastp` and `needleman_wunsch_aln_matrix_loc=EDNAFULL` identify the
qualified merger/scoring resources inside the pinned image; alternative selectors
require requalification. Host Core executable and output/runtime directory paths
are not compared as scientific settings. Resolved `fastq_r1`/`fastq_r2` paths are
checked separately against the verified staged input files, allowing absolute or
relative spellings without allowing another input population.

### Reviewed fields outside scientific equality

All 48 remaining recorded argument names were reviewed:

`allele_plot_pcts_only_for_assigned_reference`, `amplicon_coordinates`, `annotate_wildtype_allele`, `base_editor_consider_changes_outside_qw`, `base_editor_output`, `base_editor_target_ref_skip_allele_count`, `bowtie2_index`, `coding_seq`, `coding_seq_name`, `config_file`, `conversion_nuc_from`, `conversion_nuc_to`, `debug`, `disable_guardrails`, `display_name`, `dsODN`, `dump`, `expand_allele_plots_by_quantification`, `fastq_r1`, `fastq_r2`, `file_prefix`, `flash_command`, `flexiguide_name`, `guide_name`, `halt_on_plot_fail`, `keep_intermediate`, `max_paired_end_reads_overlap`, `max_rows_alleles_around_cut_to_plot`, `min_frequency_alleles_around_cut_to_plot`, `n_processes`, `name`, `no_rerun`, `output_folder`, `place_report_in_output_folder`, `plot_histogram_outliers`, `plot_window_size`, `save_also_png`, `stringent_flash_merging`, `suppress_amplicon_name_truncation`, `suppress_plots`, `suppress_report`, `trimmomatic_command`, `trimmomatic_options_string`, `use_matplotlib`, `vcf_output`, `verbosity`, `write_cleaned_report`, `zip_output`.

- `fastq_r1` and `fastq_r2`: dynamic input lineage, checked separately as above;
  prepared input hashes and manifest identity remain mandatory.
- Names, output paths, logging, report placement, colors, plotting limits, PNG/HTML,
  intermediate/debug exports and process count do not define these allele calls.
  `no_rerun` cannot reuse a child in the newly created staging root.
- `config_file` configures colors and guardrail warnings (Shared 2215-2300), not
  variant/filter arguments. Guardrails remain warnings, not custom QC thresholds.
- `plot_window_size` can matter to guide placement in other modes, but all guide,
  flexiguide and PE sequence inputs are disabled here. Pure plotting changes remain
  allowed. Guide names and flexible-guide names cannot add a sequence.
- `coding_seq`/`coding_seq_name` only annotate frameshift/exon summaries;
  `dsODN` adds annotations. Neither changes the consumed I/D/M calls/population.
  Base-editor output/conversion options affect ancillary plots, with guides off.
- `vcf_output`/`amplicon_coordinates` describe additional output; detailed allele
  output remains required independently. `bowtie2_index` is inactive with BAM
  input/output disabled.
- `trimmomatic_command`, `trimmomatic_options_string`, `flash_command`,
  `max_paired_end_reads_overlap`, and `stringent_flash_merging` are deprecated and
  unused by the 2.3.4 Core execution path. Actual fastp controls are qualified.

This is a closed scientific set for this pinned single-reference path, not a
blanket comparison of every argparse field. Tests mutate each qualified field,
remove it, and replace its type, while allowing presentation/runtime variations.
Backend upgrades require a new source/argument inventory and qualification.

## Real injection evidence

The same 12-pair 50-bp deletion crossing W2 was run before and after remediation.
Before: default 12/12; a version-preserving wrapper adding `--discard_indel_reads`
returned a REPORTABLE 0/12 with 12 discarded rows. After: qualified 12/12 remains;
the injected run fails on the resolved discard flag and publishes no result.

A second fixture gives both mates a Q10 substitution (merged Q20). Default calls
12/12 substitution-containing reads. A wrapper adding `--min_bp_quality_or_N 30`
masks the substitution and produces 12 unmodified backend reads. The old candidate
accepted this change; the new gate rejects it before publication. The raw caller
outputs are preserved, not repaired. `tests/test_m81_integration.py` repeats both
attacks against real pinned Core and verifies no REPORTABLE output is created.

Focused population tests separately inject self-consistent ambiguous/discarded
inventories while leaving resolved options qualified: generic reconciliation
counts them, then the qualified result gate rejects both. Serialized-result tests
exercise the same protection downstream. Ordinary-only and large-deletion
populations remain accepted.

## Stale identity and evidence discipline

The scientific-settings digest changes because the identity includes the newly
qualified defaults. Tests demonstrate stage signatures differ even with identical
software identity when only this contract changes. A real completed pre-remediation
workspace is retained outside the repository; candidate resume must reject stale
identity before executing stages. Explicit force recomputes science, and identical
post-remediation resume executes zero scientific stages.

Original `docs/validation/m8` and all PE evidence are unchanged. The current unit
fixture in `docs/validation/m81/allele-probe` is a new real qualified 20-pair run
with the same 10/20 primary fraction and four allele rows. A dedicated test rejects
the pre-remediation serialized result instead of treating it as newly qualified.
See the accompanying validation summary for source/wheel, integration, before/after
and stale-workspace results. Full raw runs are retained under
`/workspace/m81-remediation/` outside Git.
