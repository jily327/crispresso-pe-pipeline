# Field-to-backend mapping and ownership

S = stable main `f200e28…`; P = provisional nuclease `be4222b…`; A = proposed adapter, not implemented; D = deferred. Full SHAs and immutable source inventory are in GUI_DESIGN_SPEC.md and reference-extracts/source-inventory.json. Every writable control below must round-trip through authoritative Python validation. Display wording is not a schema field.

## 1. Source and sample fields

| UI input | Exact destination | Requirement/default | Validation / ownership | Basis |
|---|---|---|---|---|
| Analysis display name/group | GUI catalog only | Optional; no biological interpretation | Not passed as sample/target identity | A |
| Report title | `execute_workflow(title=...)`; `generate_report(title=...)` | Optional; backend mode-aware default | Nonblank; preserve labels; rendering can fail XML validation | S/P |
| Input source kind | `execute_workflow(mode='run'|'analyze')` | Required | One choice; not scientific `analysis_mode` | S |
| Raw forward/reverse file | `r1`, `r2` | Both required for run | Python streams bytes, verifies records/mate IDs; filename guess is advisory | S |
| Verified demux folder | `demux_root` | Required for analyze; hides raw cards | `verify_demux_output`; immutable external archive | S |
| Output folder | `output` | New root, unless explicit resume | Backend ownership/containment/symlink/lock validation | S |
| Metadata CSV | `samples`; `load_samples` / `Sample` | Required | Exact imported bytes preserved; explicit edited snapshot | S |
| Display sample name | `Sample.sample_name` | Required identifier; unique | No duplicate names; not the M4 join key | S |
| Stable sample ID | `Sample.barcode_id` | Required identifier; unique | Authoritative M4 sample_id→M5 metadata join; must not change silently | S |
| Forward barcode | `forward_barcode` OR `forward_barcode_id` | One definition required | Sequence or catalog ID; both, if supplied, must resolve consistently | S |
| Reverse barcode | `reverse_barcode` OR `reverse_barcode_id` | One definition required | Backend catalog/orientation rules; no inferred reverse complement | S |
| Editor | `Sample.editor` | Required nonblank text | No invented editor for controls | S |
| Treatment | `Sample.treatment` | Required nonblank text | No separate free-text “condition” field replacing structured condition | S |
| dpi | `Sample.dpi` | Required integer ≥0; **no biological default** | A documented control placeholder may be user supplied, never inferred | S |
| Biological replicate | `Sample.biological_replicate` | Required identifier | M5 duplicate-unit checks; never derive biological n from read files | S |
| Paired experimental design | `Sample.paired` | Required bool; explicit choice/import | Separate from paired-end sequencing; paired rows need block ID | S |
| Block ID | `Sample.block_id` | Required when paired; otherwise optional | Explicit experimental pairing; not inferred by row order | S |
| Barcode catalog | workflow `barcodes`; barcode catalog loader | Bundled `qi_hitom_v1` or explicit custom CSV | Display resolved identities/safety, reject conflicts | S |
| Library profile | `Config.demux.profile` | Backend default `qi_hitom_v1`; user confirms applicability | Only `qi_hitom_v1` or `custom`; custom layout needs explicit supported fields | S |
| Custom extraction layout | `demux.forward_offset`, `reverse_offset`, `forward_length`, `reverse_length`, `forward_bridge`, `reverse_bridge`, `reverse_barcode_orientation` | Advanced; explicit library knowledge | Backend resolves catalog/rules; no adapter inference | S |
| Barcode mismatch policy | `demux.max_mismatches` | GUI v1 selects locked exact `0` | Nonzero backend Hamming support is not advertised as a new GUI default; later capability-gated expert exposure requires safety validation | S/A |
| Demux retention choices | `demux.trim_barcodes`, `trim_bridges`, `ambiguous_policy` | GUI v1 untrimmed archive; ambiguous=`unassigned` | Do not edit existing archive; advanced imported configs shown with exact resolved effects | S |
| Bridge QC | `demux.bridge_qc` | Backend default true | Visible resolved setting; no scientific edit inferred | S |
| Analysis preparation | `analysis_r1_trim_5p`, `analysis_r2_trim_5p` → `PreparationConfig.r1_analysis_trim_5p`, `r2_analysis_trim_5p` | Both absent for supported auto layout OR both explicit ≥0 | `resolve_trims` derives from verified untrimmed Hi-TOM archive; other layouts require explicit sizes | S |

Identifiers use the current Python rules (`[A-Za-z0-9][A-Za-z0-9_.-]*`); target/copy IDs also reserve `__`. The browser may flag obvious syntax early, but Python performs final validation. CSV serialization belongs in the adapter: required legacy headers, empty nullable values, integer and boolean encodings must match existing loaders. No spreadsheet “repair” silently rewrites sequence/identity fields.

Batch table means biological samples in one demux pool. It does not create a per-sample arbitrary FASTQ import API. FASTQ file selections count files; sample rows count biological units. Prepared-analysis manifests can be inspected in provenance, but are not a current run/analyze entry option.

## 2. PE target controls

All map to `schemas.Target` through `targets.csv` / `load_targets`; basis S unless noted.

| UI label | Field | Required/default | Conditional behavior |
|---|---|---|---|
| Scientific mode | `analysis_mode='precise_edit'` in emerging loader | Legacy absence resolves to PE (P); stable Target has no mode field | Adapter emits the format appropriate to installed contract; do not send unsupported extra fields to stable model |
| Target name | `target_name` | Required; one biological target per execution | Multiple rows are copies of that target, not multiple targets |
| Copy/homeolog ID | `copy_name` | Required per row | Add copy reveals complete per-copy inputs; no inferred guide/reference |
| WT amplicon | `wt_sequence` | Required A/C/G/T | Python normalizes permitted case; no gaps/ambiguity codes |
| Intended edited reference | `prime_edited_sequence` | Required, different from WT | No browser diff algorithm; backend returns annotations |
| pegRNA spacer | `pegRNA_spacer` | Required | Backend RNA normalization permits U→T; show normalized value explicitly |
| pegRNA extension | `pegRNA_extension` | Required | Backend orientation/reference compatibility remains authoritative |
| Nicking guide | `nicking_guide` | Optional/null | Do not invent when absent |
| Scaffold | `pegRNA_scaffold` | Optional/null | Reveals optional scaffold minimum-match setting |
| Scaffold minimum match | `prime_editing_pegRNA_scaffold_min_match_length` | Optional; if supplied >0 and ≤ scaffold length | Requires scaffold; show backend-resolved default when omitted |
| PE coordinate override | `quantification_window_coordinates` | Optional | Advanced qualified backend choice. Stable PE accepts `0`; do not confuse with forbidden nuclease sentinel. GUI v1 does not offer disable-window sentinel as a casual toggle |
| PE window size/center | `quantification_window_size`, `quantification_window_center` | Optional; no GUI-invented defaults | Show only combinations/precedence resolved by PE backend; unqualified/conflicting imported settings block review rather than guessing |
| Additional PE-family requests | workflow `tolerance_policies` → `metrics.policy_requests.prepare_policies` | Optional imported YAML/JSON | Qualified expert import only; preserve explicit policy identity; never replace exact primary metric |

WT/intended difference tracks and guide/edit coordinates need an **A annotation projection** of authoritative PE geometry/product definitions. Existing internal outputs are not a stable frontend annotation API. Until qualified, show sequence strings and “Annotation unavailable,” not a frontend alignment. Readability normalization may format line breaks visually; exported/sent authoritative sequence values remain backend-normalized, not browser-mutated biology.

## 3. Nuclease controls — all provisional until M8.1 merge

| UI label | Observed field/path | Required/default | Rule |
|---|---|---|---|
| Mode | `NucleaseTarget.analysis_mode='indel_nuclease'` | Explicit required | Cannot infer nuclease from blank PE fields |
| Target / copy | `target_name`, `copy_name` | Required; exactly one copy and target | Backend refuses `MULTICOPY_NUCLEASE_UNSUPPORTED` |
| WT amplicon | `wt_sequence` | Required | No intended edited reference or PE guide fields |
| Window method | Presence of explicit qwc versus profile fields | Required exclusive choice | GUI-only radio translated by adapter; no invented serialized `method` field |
| Explicit coordinates | `quantification_window_coordinates` | Required for explicit choice | Ordered disjoint in-bounds zero-based inclusive ranges; `0` invalid; `0-0` valid |
| Profile | `nuclease_profile='tigr_tas_v1'` | Required for TIGR choice | Versioned backend capability, not free-text arbitrary profile |
| TIGR 18-nt target | `tigr_target_sequence` | Required for TIGR | Exact length/unique physical locus checked by backend |
| Qualified window | `tigr_window` | W2 default; W1/W3/W4 advanced if enabled | Backend computes selected coordinates; GUI sends only enum |
| Insertion semantics | `insertion_quantification_mode='current'` | Locked | No legacy toggle |
| Window preview | `NucleaseTarget.window` / `scientific_identity.resolved_window` | Read-only | Proposed API exposes validated return, not property evaluation in browser |
| Orientation | `resolved_window.orientation` | Read-only | forward / reverse / palindromic |
| Target placement | `target_start`, `target_interval` | Read-only | Inclusive amplicon-top-strand coordinates |
| Cuts | `physical_nick_boundaries` | Read-only | Backend returns both anchor pairs |
| Nick labels | `target_oriented_nick_labels` | Nullable read-only | Reverse labels can swap; palindrome labels unavailable |
| Window identity | `selected_window`, `coordinates`, `intervals`, `profile_version`, `derivation` | Read-only | Show profile and explicit override distinction |

Do not send blank PE-specific columns in nuclease CSVs. Remediation may refine output models or rejection conditions; regenerate exact bindings and schema-based tests after merge rather than preserving this snapshot by force.

## 4. Statistics and locked execution settings

| Control/display | Backend mapping | Exposure decision |
|---|---|---|
| Descriptive only / explicit tests | No `contrasts` → `summarize`; supplied `contrasts` → `stats` | Default descriptive only; user opts into explicit specification |
| Contrast ID / family | `Contrast.contrast_id`, `family_id`; `ContrastSpecification.families` | Explicit IDs/family membership; validate uniqueness |
| Metric and scope selector | `target_name`, `metric_name`, `copy_name`, `policy_id` | Backend enumerates eligible series; default PE `total_precise_pe`, nuclease `indel_fraction` |
| A and B conditions | `group_a`, `group_b`: `editor`, `treatment`, `dpi` | Structured tuples; display all three. Do not infer A/B from sort order |
| Pairing | `pairing_mode='unpaired'|'block'` | Explicit, checked against `paired` and block metadata |
| Alternative | `alternative='two-sided'` | Locked current contract |
| Permutation budget | Existing standalone stats argument; M7 uses existing default | Read-only effective budget in first GUI, not an invented workflow flag |
| Generalized/factorial settings | `Config.statistics` legacy schema fields | Do **not** expose as active generalized M5 modeling; M7 explicit contrasts are authoritative |
| Runtime | workflow `crispresso`, `runtime_digest`; executable resolver | Deployment/operator configuration; normal user chooses only a verified installed runtime, never types an assumed digest |
| Backend flags | Mode-specific execution/resolved args | Locked. Nuclease current snapshot: retain substitutions/indels; end exclusions zero; detailed alleles; no legacy insertion mode |
| PE routing | `RoutingPolicy()` and policy identity | Read-only qualified policy; no identity threshold slider |
| Worker/resource settings | Existing workflow serial execution; `Config.n_processes` is not a promise of DAG concurrency | Show actual capabilities; no parallelism control in GUI v1 |
| QC thresholds in config | Existing `Config.qc` fields | Inspect resolved configuration; do not expose as universal active scientific filters absent actual execution mapping |

## 5. Result binding register

These are source paths, not permission for the frontend to recompute missing values. Proposed result adapter cross-links M5 observations and verified source metric artifacts by sample/target/metric/population/copy/policy identity.

| View value | Authoritative field/source | If unavailable |
|---|---|---|
| Sample percentage | `StatisticsResult.observations[].fraction` | Em dash + status/reason, never numerator/denominator division in browser |
| Sample integer ratio | Same observation `numerator`, `denominator` | Show unavailable; M4 counts can be separately identified evidence |
| Condition mean/range | `group_summaries[].mean_biological_sample_fraction`, `minimum_biological_sample_fraction`, `maximum_biological_sample_fraction`; median if shown | No frontend recomputation; no invented SD/CI |
| Replicate inventory | `expected_sample_count`, `reportable_count`, status counts and `sample_assessments` | Missing is explicit |
| Effect / p / q | `contrasts[].difference_in_biological_sample_fraction`, `p_value`, `q_value` | No testing requested or nonreportable reason |
| PE target exact/native | M4 `target_metrics.total_precise_pe`, `target_crispresso_native_pe`; corresponding M5 observations | Independent state for each card |
| PE exact WT / exclusions | `MetricRecord.products.exact_wt`, `denominator_exclusions`, component counts and `exclusion_reason_counts` | Count only if no qualified fraction supplied; do not label excluded origin WT/PE without evidence |
| PE copy metrics | `copies[copy_id].precise`, `.native`; family metrics separately | Routing-conditioned label always |
| PE assessment relationship | `assessment_stage`, `backend_counts_role`, `population_scope`, `population_id` | No generic funnel fallback |
| Nuclease primary/secondary | `NucleaseMetricResult.metrics[metric_name]` with `numerator`, `denominator`, `fraction` | P; obey final reportability gate |
| Nuclease exclusive/exceptional classes | `class_counts` and stored metric ratios | P; display exceptional categories; adapter supplies any missing presentation ratio with denominator provenance |
| Net-size bins | `fraction_of_indel_reads_by_net_size` | P; no chart if no indel denominator; zero-size bin retained |
| Nuclease alleles | `alleles[].authoritative_fields`, `.reads`, `.product_class`, `.net_delta_bp` | P; preserve each row; do not merge by visible substring |
| Native PE alleles | Core allele ZIP inventoried by M4 provenance | A typed artifact reader; unavailable until qualified. PE exact `product_evidence` is a different source, never relabelled as Core alignment |
| Position plots | Native `Modification_count_vectors`, qwc vectors, nucleotide tables | A/D typed, reference-specific reader with denominator/coordinate validation; unavailable today as a universal GUI contract |
| Provenance | Workflow plan/manifests + M4/nuclease provenance + M5 provenance + M6 manifest | Read-only chain; hashes validated server-side |

## 6. Ownership matrix

| Function | Backend responsibility | GUI responsibility |
|---|---|---|
| Required-name / numeric syntax | Final schema validation | Early convenience feedback |
| Barcode/catalog resolution, FASTQ pairing | Authoritative checks/classification | Source controls; display row errors and counts |
| Sample and target identity | Resolve/validate exact scientific keys | Labels and stable selections; never substitute display names |
| TIGR search, orientation, cuts, qwc | Authoritative geometry | Submit target/profile/window enum; render returned tracks |
| Explicit qwc | Validate/normalize bounds and semantics | Input string; show normalized answer |
| PE WT/intended geometry | Authoritative sequence/observability logic | Render returned annotations; no alignment algorithm |
| Routing and quarantine | Qualified routing | Display decisions/reasons |
| Alleles and event calls | CRISPResso; backend validates | Render original row/annotated glyphs, no independent calls |
| Indel/PE fractions and populations | Existing scientific layers | Formatting only; no denominator repair |
| Means, ranges, p/q, pairing | M5 | Render stored results; filter existing series |
| Sequence-to-pixel layout | Adapter provides coordinates/glyph annotations | Pixel layout, zoom/pan and accessible text |
| Stage signatures, reuse, force closure | M7 | Show validated impact and collect confirmation |
| Job liveness/cancellation | Proposed worker service | Request and display acknowledged states |
| Artifact discovery/hash/path checks | Proposed read-only server adapter + existing verifiers | Opaque artifact selection/download |
| Native HTML trust/isolation | Proposed artifact server/output qualification | Separate native view with clear provenance label |
| Export scientific data | Existing exact artifacts or qualified adapter | Download; no spreadsheet recalculation |
