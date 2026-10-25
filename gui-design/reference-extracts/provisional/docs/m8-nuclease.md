# M8: precise edit and indel/nuclease modes

Version 0.8.0 adds **single-copy nuclease analysis**. CRISPResso2 2.3.4 remains
the authoritative variant caller. The new modules configure Core, validate its
artifacts, classify its allele rows and aggregate integer counts. They never
realign FASTQs or aligned allele strings to call variants.

## Inputs and compatibility

Existing target CSVs without `analysis_mode` resolve to `precise_edit`. All PE
requirements, routing, observability, references, products and metric contracts
remain unchanged. `Target.analysis_mode` resolves the input default, while legacy
PE target serialization is preserved to retain existing M4 reference identities.
Normalized workflow configuration, stage parameters/signatures and the final
workflow manifest explicitly record the resolved scientific mode. The existing
`m4-v1`, `m5-v1` and `m6-v1` PE result schemas are unchanged.

New nuclease rows must explicitly say `analysis_mode=indel_nuclease`. Use a
separate target file and workspace for each mode. PE-specific columns are not
accepted in a nuclease target, even as blank cells. No edited reference or guide
is invented. Example generic target header:

```csv
analysis_mode,target_name,copy_name,wt_sequence,quantification_window_coordinates
indel_nuclease,T1,copy1,<ACGT amplicon>,104-113
```

`quantification_window_coordinates` uses CRISPResso zero-based inclusive ranges:
`0-0` is one base; `10-20_30-40` is two disjoint intervals. Ranges must be ordered,
non-overlapping and in bounds. Leading zeros normalize away. The disable sentinel
`0`, empty windows, reversed ranges and malformed coordinates are rejected.

An alternative profile header is:

```csv
analysis_mode,target_name,copy_name,wt_sequence,nuclease_profile,tigr_target_sequence,tigr_window
indel_nuclease,T1,copy1,<ACGT amplicon>,tigr_tas_v1,<18-nt DNA target>,W2
```

Specify explicit coordinates **or** a profile, never both. Omitting `tigr_window`
selects W2. `insertion_quantification_mode` is `current`; legacy insertion
quantification is not implemented and is rejected. Existing `samples.csv` and
preparation contracts apply. PE tolerance-policy requests are rejected in
nuclease workflows. Existing PE-specific `config.yaml` quantification fields
remain PE settings; nuclease scientific settings come from the nuclease target.

## Versioned TIGR–Tas geometry

`tigr_tas_v1` searches the exact 18-nt DNA target and its reverse complement.
Matches are deduplicated by physical interval. Missing or multiple physical loci
fail closed. One self-reverse-complementary target is one palindromic locus.

For physical start `s`, the cuts are `[s+4,s+5]` and `[s+12,s+13]`, separated by
8 nt. Coordinates are amplicon-top-strand positions, zero-based and inclusive.

| Window | Coordinates | Use |
|---|---|---|
| W1 | `s+4-s+5_s+12-s+13` | Strict sensitivity; both insertion anchors at each cut |
| W2 | `s+4-s+13` | **Primary**, continuous 10-bp cut span |
| W3 | `s-s+17` | Full-target sensitivity |
| W4 | `max(0,s-10)-min(len(wt)-1,s+27)` | Broad sensitivity with explicit clipping |

The physical cut-coordinate set is identical for forward and reverse hits.
Target-oriented labels are `5|6, 13|14` in forward coordinate order and
`13|14, 5|6` for reverse hits. Palindromic hits have unavailable target-oriented
nick labels and between-cut sequence orientation. The amplicon-top-strand target,
amplicon-top-strand between-cut sequence and target-oriented between-cut sequence
are separate fields. No unsupported strand-specific overhang assignment is made.

This analysis uses CRISPResso2 with an explicit quantification window derived
from the experimentally mapped/reported TIGR–Tas cleavage geometry. It does not
claim to reproduce unpublished CRISPResso options from the original paper.
Changing this derivation requires a new profile version.

## Backend and populations

The nuclease workflow consumes the **complete verified prepared sample
population**. `single_copy_identity` records experimental identity without PE
routing, WT/PE state alignment or exact-product classification. A legacy DAG node
named `routing::<sample>::<target>` remains an ownership/dependency slot; its API
is `single_copy_identity` and its artifact is `identity.json`, not a PE routing
manifest or read partition.

More than one copy fails before scientific execution with
`MULTICOPY_NUCLEASE_UNSUPPORTED`. Multi-target execution remains unsupported until
separate target-specific read selection is qualified. No PE identity threshold
is used to reject large nuclease deletions; Core preprocessing/alignment may
still exclude reads under its own recorded criteria.

Core receives paired FASTQs, one WT amplicon, explicit window coordinates and
`--write_detailed_allele_table`. It receives no guide, PE parameters,
`--ignore_substitutions`, legacy insertion mode or no-rerun request. The driver
sets `--exclude_bp_from_left 0 --exclude_bp_from_right 0` so end exclusions cannot
silently shrink the explicitly selected window, including boundary profiles.
Other quality, scoring and merging options use pinned Core defaults; no TIGR
Q30/Q20/70%-alignment assumptions are introduced. Actual argv and the backend's
resolved arguments are preserved. Runtime identity must equal the existing
qualified pinellolab/crispresso2 SHA-256 digest; only 2.3.4 is accepted.

The parser verifies actual reference, actual include indices, scientific flags,
completion/version, mapping table, alignment counters, quantification table and
allele table. `N_TOT_READS` equals aligned plus unaligned. Backend input equals
prepared pairs; preprocessing may reduce this population. No unaligned cause is
invented. Required allele integer fields, status, aligned-string shape and
CRISPResso event-list/count consistency are validated without making new calls.
Original authoritative fields, including `%Reads`, remain in every allele record.

## Counts and denominators

Primary **indel_fraction** numerator is the sum of `#Reads` for ordinary
CRISPResso-classified rows with `n_inserted > 0 OR n_deleted > 0`, counted once.
The denominator is **all authoritative aligned reads**. Rounded `%Reads` never
supplies counts, denominators or reconciliation repairs.

The mutually exclusive ordinary classes are unmodified, substitution-only,
indel-only and indel-plus-substitution. Ambiguous/discarded aligned categories
remain separate and in the aligned denominator; they never become unmodified.
The sum of all ordinary and explicit exceptional row counts must equal aligned
reads exactly, with reference/discard inventories also matching Core JSON and
quantification tables. Any unexplained difference fails validation.

Secondary fractions expose unmodified, substitution-only, indel-only, mixed,
substitution-containing, insertion-containing, deletion-containing,
insertion-and-deletion-containing and any-modification counts. The latter
membership categories overlap; only the four ordinary classes are a partition.
Every fraction retains exact numerator and denominator. These are **window-aware
CRISPResso calls**: an outside-window change can be unmodified for this metric.
Current insertion semantics require both anchors in the selected window. A
CRISPResso deletion overlapping the window can contribute its full called length.

Net-size bins use exactly `n_inserted - n_deleted` for indel-containing rows,
weighted by `#Reads`, divided by total indel-containing reads. Net zero remains
an indel. Binning never merges the retained allele records. Reports show the top
20 rows and retain all rows in their exact source result. Position-level
substitution spectra are deferred; counts and original detailed event fields
remain available.

## Statistics, reports and workflow

Separate strict contracts are `indel-nuclease-v1`, `indel-nuclease-stats-v1` and
`indel-nuclease-report-v1`, all schema version 1. Packaged JSON schemas accompany
the typed models. PE validators remain separate. Nuclease observations reuse the
existing biological-sample summary and exact contrast algorithms: unweighted
sample means, explicit contrasts, paired design checks, permutation limits and
family-scoped BH. Reads never become inferential replicates. Default primary
outcome is `indel_fraction`; no contrasts are inferred. Use that exact metric
name in an explicit contrast specification.

```sh
peanalyzer run --r1 raw_R1.fastq.gz --r2 raw_R2.fastq.gz \
  --samples samples.csv --targets nuclease-targets.csv --config config.yaml \
  --output results --crispresso CRISPResso --runtime-digest <qualified-digest> \
  --contrasts contrasts.yaml
```

`analyze --demux-root ...` starts from an immutable verified archive. The existing
`summarize`, `stats`, and `report` commands dispatch by strict result contract.
Reports preserve M6 deterministic rendering, exact source copying and the M6.1
XML validity gate, adding stored nuclease counts, alleles, net-size bins, window
geometry, configuration and limitations. No statistical recalculation occurs in
reporting.

Existing M7 locks, content hashes, source snapshots, validation, orphan rejection,
selective force and completion marker rules apply. Mode switching always requires
a new workspace, including with force-all. Window/profile changes conservatively
require routing force (identity stage plus metrics and descendants); report-title
changes need report force only. Software identity includes version, code/resource
hash and Git provenance. A 0.7.1 workspace cannot silently reuse 0.8.0 science.

This milestone adds no GUI, generalized statistical modeling, alternative
aligner, multi-copy nuclease routing or automatic biological interpretation.
