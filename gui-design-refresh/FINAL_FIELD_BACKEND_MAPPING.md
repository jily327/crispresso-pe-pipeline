# Final field/backend mapping — merged 0.8.0

Authority: `9e9a51fb20e56a3421fdfa156375170cd6b257dc`. All scientific bindings below are **STABLE/CURRENT** at that SHA. Transport endpoints, presentation envelopes and job services remain adapter work. This replaces provisional nuclease rows in the reviewed FIELD_BACKEND_MAPPING; unchanged sample/PE controls retain their exact mappings. No input field or scientific status is invented.

Source anchors: `src/peanalyzer/nuclease/{qualification,targets,models,backend,reporting}.py`, `workflow.py`, `result_dispatch.py`, `statistical_models.py`; exact snapshots/hashes are in SOURCE_INVENTORY.json. QUALIFIED_ARGUMENT_REFERENCE.json is a read-only source extraction, not another executable qualification policy.

## 1. Modes, sources and unchanged PE bindings

| GUI concept | Current backend binding | Rule |
|---|---|---|
| Precise Edit | `schemas.Target.analysis_mode='precise_edit'` | Missing legacy mode resolves to PE; PE serialized target behavior retained |
| Indel / Nuclease | `nuclease.targets.NucleaseTarget.analysis_mode='indel_nuclease'` | Explicit required; no blank-PE-field inference |
| Workflow source mode | `execute_workflow(mode='run'|'analyze')` | Separate from scientific mode |
| Raw inputs | `r1`, `r2` | One raw paired pool; one target-specific biological population |
| Existing archive | `demux_root` + `verify_demux_output` | Verified external M2 archive, not arbitrary prepared FASTQs |
| Sample/metadata | `samples`; `Sample.sample_name`, `barcode_id`, barcode definitions, `editor`, `treatment`, `dpi`, `biological_replicate`, `paired`, `block_id` | Stable barcode_id joins results; no inferred experimental metadata |
| PE target/copies | `Target.target_name`, `copy_name`, `wt_sequence`, `prime_edited_sequence`, `pegRNA_spacer`, `pegRNA_extension`, optional `nicking_guide`, `pegRNA_scaffold` and existing qualified window/scaffold fields | No PE redesign; multiple copies of one target only |
| Prepared-read trimming | Workflow `analysis_r1_trim_5p`, `analysis_r2_trim_5p` → `PreparationConfig` | Auto only for supported recorded library or both explicit values |
| Contrasts / report | `contrasts` / `title` | M5 explicit design and stored outcomes; presentation title separate from science |

## 2. Nuclease input and preview fields

| UI choice/value | Exact field or backend return | Current semantics |
|---|---|---|
| Target/copy | `NucleaseTarget.target_name`, `copy_name` | Exactly one copy and one biological target for execution |
| WT reference | `wt_sequence` | Required DNA reference; no PE/guide fields |
| Explicit qwc | `quantification_window_coordinates` | Ordered disjoint in-bounds zero-based inclusive intervals; `0` invalid, `0-0` valid; backend-normalized string |
| Profile | `nuclease_profile='tigr_tas_v1'` | Explicit alternative to qwc; cannot supply both |
| TIGR target | `tigr_target_sequence` | Exactly 18 nt; backend searches exact forward/reverse and deduplicates physical locus |
| Window selection | `tigr_window` | W1/W2/W3/W4; W2 is the omitted-input default, not an unconditional result label |
| Insertion semantics | `insertion_quantification_mode='current'` | Locked; no legacy selection |
| Preview geometry | `NucleaseTarget.window` | Python return; transport adapter needed, React does not calculate it |
| Persisted geometry | `NucleaseMetricResult.provenance.scientific_identity.resolved_window` | Preferred read-only result binding; preserve actual fields returned |
| Qualified expected arguments | `provenance.scientific_identity.backend_settings` | 58 exact scientific fields; display only |
| Actual resolved arguments | `provenance.execution.resolved_backend_arguments` | Includes qualified scientific fields plus other runtime/presentation fields; display actual types |
| Scientific identity mechanism | root `identity_mechanism='single_copy_identity'` | All verified prepared pairs; never label as PE routing |

### Exact resolved-window shape

Common fields: `derivation`, `profile_version`, `coordinates`, `intervals`. Explicit qwc has `derivation='explicit'`, `profile_version=null`; it has no `selected_window`, target orientation or cut labels. Display “Explicit” plus returned coordinates; do not fill absent TIGR fields.

TIGR fields: `derivation='tigr_tas_v1'`, `profile_version='tigr_tas_v1'`, `target_sequence`, `target_start`, `target_interval`, `orientation`, `physical_nick_boundaries`, `target_oriented_nick_labels`, `amplicon_top_strand_target`, `amplicon_top_strand_between_cuts`, `target_oriented_between_cuts`, `selected_window`, `coordinates`, `intervals`.

`target_interval` and windows are zero-based inclusive on the amplicon top strand. `physical_nick_boundaries` contains two adjacent-position pairs. Orientation is forward/reverse/palindromic. Forward labels are `5|6`, `13|14`; reverse labels swap; palindrome labels and target-oriented between-cut sequence are null. Render returned values; never infer an arrow or recompute `s+4…s+13` in React. Existing returned W1/W2/W3/W4 definitions remain backend-owned.

## 3. Qualified scientific configuration

The authoritative set is `qualification.scientific_arguments(wt_sequence, coordinates)`: **56 fixed + 2 target-dependent = 58 fields**. `validate_arguments` requires field presence, identical Python/JSON value type, and exact value. Checks run on completed Core output and serialized result loading. A matching nominal package version or constructed argv is insufficient.

| Example field(s) | Required value/type | UI behavior |
|---|---|---|
| `discard_indel_reads` | boolean false | Locked; no discard-indel toggle |
| `min_bp_quality_or_N` | integer 0 | Locked; no N-masking threshold control |
| `ignore_substitutions`, `ignore_insertions`, `ignore_deletions` | boolean false each | Events retained; not selectable flags |
| `use_legacy_insertion_quantification` | boolean false | Current semantics only |
| `exclude_bp_from_left`, `exclude_bp_from_right` | integer 0 / 0 | Actual nuclease end-exclusion policy; do not apply to PE by analogy |
| `amplicon_name`, `amplicon_seq` | string Reference; exact supplied WT | Single supplied reference; no inferred alternative reference |
| `quantification_window_coordinates` | exact normalized selected string | Show actual returned coordinates |
| `default_min_aln_score` | integer 60 | Locked qualified default, not a GUI homology slider |
| `min_paired_end_reads_overlap` | integer 10 | Locked merging contract |
| `min_average_read_quality`, `min_single_bp_quality` | integer 0 / 0 | Locked filtering defaults |
| `fastp_command`, `fastp_options_string` | string fastp; empty string | Locked qualified merger/resource settings |
| `write_detailed_allele_table` | boolean true | Required authoritative evidence |
| `quantification_window_center`, `quantification_window_size` | strings `-3`, `1` | Retain exact recorded types; explicit qwc remains active window |
| `flexiguide_seq` | literal string `None` | Not JSON null; no type coercion |

Render the full backend-returned 58-field expected map and actual resolved arguments in the read-only Qualified scientific configuration view. Use backend validation status, not a browser-side 58-field validator. Do not copy the snapshot JSON into React as a second contract. Paths to staged R1/R2 are verified separately against the prepared input lineage; they are not among the 58 equality fields. CRISPResso 2.3.4 and the existing pinned runtime digest remain mandatory.

## 4. Result paths and populations

Let **N** be the validated `NucleaseMetricResult` loaded from a workflow metric node's `result.json`; **S** the validated `NucleaseStatisticsResult` from `statistics/result.json`.

| Display | Exact path | Semantics / restrictions |
|---|---|---|
| Contract/mode | `N.schema_version`, `.metric_contract_version`, `.analysis_mode` | 1 / indel-nuclease-v1 / indel_nuclease |
| Sample/target | `N.sample_id`, `.target_id` | Join using stable identity; never display-name join |
| Primary | `N.metrics.indel_fraction.{numerator,denominator,fraction}` | Ordinary authoritative allele reads with n_inserted>0 OR n_deleted>0, once per read / all authoritative aligned reads |
| Scientific state | `N.status`, `N.reason_codes` | Positive aligned population must be REPORTABLE, empty reasons; zero aligned must be NOT_ASSESSABLE with NO_ALIGNED_READS. The enum's BLOCKED spelling is not permission to synthesize a valid blocked nuclease record after a raised gate |
| Input/flow | `N.backend_input_reads`, `.reads_after_preprocessing`, `.aligned_reads`, `.unaligned_reads` | Retain integer counts; no frontend inferred cause/rate |
| Counters/mapping | `N.alignment_counters`, `.mapping_statistics` | Authoritative reconciliation evidence, not a browser calculator |
| Ordinary classes | `N.class_counts.unmodified`, `.substitution_only`, `.indel_only`, `.indel_plus_substitution` | Four exclusive classes exhaust accepted aligned population; their fractions come from stored metric entries below |
| Exceptional serialized keys | `N.class_counts.ambiguous`, `.discarded` | Both zero in accepted results. Nonzero → reject; no normal chart segments |
| Diagnostic population names | parser `aligned_partition` output `ambiguous_aligned_reads`, `discarded_aligned_reads`; rejection message | These are not new root N fields; diagnostics only if provided and reconciled by backend |
| Net-size bins | `N.fraction_of_indel_reads_by_net_size[decimal-string-key]` → `{numerator,denominator,fraction}` | Stored integer net-size bin; denominator = indel-containing reads; do not recompute bins or normalize anew |
| Allele rows | `N.alleles[]` | Separate original rows; no collapse by visible substring |
| Allele counts/events | `.reads`, `.n_inserted`, `.n_deleted`, `.n_mutated`, `.net_delta_bp`, `.product_class` | Core-derived and backend-validated; net zero stays indel |
| Original allele evidence | `.authoritative_fields` (`Aligned_Sequence`, `Reference_Sequence`, `#Reads`, `%Reads`, `n_inserted`, `n_deleted`, `n_mutated`, reference/status and detailed fields) | Preserve original strings; no frontend realignment/event calling |
| S-linked N evidence | `S.nuclease_results[]` | Typed embedded N results; backend validator cross-checks observations against each source |
| M5 primary/secondary observations | `S.observations[]` keyed by sample_id/target_name/metric_name and complete series identity | Stored numerator/denominator/fraction/status/reasons; nonreportable observations have null numeric outcomes |
| Group/contrast | `S.group_summaries[]`, `.contrasts[]`, `.multiple_testing_families[]` | Existing biological-sample logic unchanged; means and p/q already stored |

Accepted N aligned population equals its ordinary classified population because both exceptional counts are zero. Generic reconciliation can recognize exceptions; recognition is not acceptance. A failed qualification must not publish an adjusted indel percentage. The dashboard only renders a verified result; diagnostics can preserve reconciled exception evidence without forming a biological outcome card.

### Exact metric names

All ten entries below are `N.metrics[metric_name]`, each containing stored numerator, denominator, fraction. Each denominator is authoritative aligned reads. No overlapping-membership total is implied.

| Metric name | Category |
|---|---|
| `indel_fraction` | Primary OR of insertion/deletion-containing reads |
| `unmodified_fraction` | Exclusive class |
| `substitution_only_fraction` | Exclusive class |
| `indel_only_fraction` | Exclusive class |
| `indel_plus_substitution_fraction` | Exclusive class |
| `substitution_containing_fraction` | Overlapping descriptive membership |
| `insertion_containing_fraction` | Overlapping descriptive membership |
| `deletion_containing_fraction` | Overlapping descriptive membership |
| `insertion_and_deletion_containing_fraction` | Overlapping descriptive membership |
| `any_modification_fraction` | Overlapping descriptive membership |

Net-size uses stored `net_delta_bp = n_inserted - n_deleted` semantics. Empty indel populations have no invented WT bin; a present zero-size indel bin remains an indel. React may sort numeric bin keys for layout but never reconstruct counts or fractions.

## 5. Window labels, provenance and stale identity

Generic result title: **Selected window: [returned selected_window, or Explicit]; coordinates: [returned coordinates]**. `nuclease.reporting.extend_html` uses that exact distinction. No generic result component says W2 merely because setup defaults to W2. For explicit qwc, profile/orientation labels are unavailable rather than guessed.

`N.provenance.scientific_identity.backend_settings` participates through `NucleaseTarget.scientific_identity` in M7 stage parameters/signatures. `provenance.execution.scientific_identity` must match, and `resolved_backend_arguments` is independently checked. Old pre-M8.1 results may fail loading or stage identity even though package/contract labels still say 0.8.0/v1. Version strings alone are not compatibility validation.

Use `workflow.verify_workflow_output` for read-only completed-workspace validation. It reads original source lineage and may fail if source paths moved/missing; M10 must not weaken that boundary. Resume uses current plan/signatures and can fail `STALE_STAGE_IDENTITY`. Recovery requirements come from Python/M7; neither adapter nor React chooses a force closure to bypass validation.

## 6. Ownership matrix — final main

| Function | Scientific/backend authority | Adapter role | GUI role |
|---|---|---|---|
| Mode validation | Metadata models/loaders and workflow scope | Serialize explicit mode, relay validation | Mode control; no inference from missing PE fields |
| PE target geometry | Existing PE geometry/observability | Project existing validated data if supported | Display only |
| TIGR geometry | `tigr_geometry`, `NucleaseTarget.window` | Serialize returned geometry | Track/pixel layout, no target search or cut math |
| qwc | `intervals`, target validation, actual Core include-index checks | Return normalized/recorded values | Input/formatting; no scientific normalization |
| CRISPResso qualification | `validate_arguments`, runtime/reference/input lineage gates | Relay stored qualification and exact values | Read-only configuration; no validator clone |
| Allele classification | Core + `Allele`/backend parsing | Page/project already validated records | Render supplied strings/classes; no event calling |
| Fractions / classes / net bins | `aggregate` and result validators | Copy stored fields; no fresh metrics | Formatting, filtering/sorting only |
| Statistics | M5 functions and result models | Project stored observations/means/p/q | Charts/tables; no inferential calculations |
| Reportability | Scientific result validators | Preserve states/errors | Distinguish zero, unavailable and failure |
| Stale identity/resume | M7 signatures/verifiers | Relay failures/recovery context | Explain, no silent reuse |
| Force closure/deletion | M7 `force_closure` and ownership/invalidation | Future preview wrapper around existing authority | Request/confirm future action; no closure algorithm |
| Artifacts | Existing manifests/hash/path rules | Safe inventoried discovery/access | Opaque selection and download |
| UI inputs/navigation | Backend final validation | Trivial syntax convenience and serialization | Controls, focus, sorting, accessibility and layout |

Allowed adapter work remains serialization, paging, safe artifact access, presentation projection and trivial syntax feedback. Loading authoritative validators may perform their existing consistency checks; do not replace them with a weaker schema-only load. It must not become a second scientific engine.
