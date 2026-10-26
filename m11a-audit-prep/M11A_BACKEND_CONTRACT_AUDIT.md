# M11A backend contract pre-audit

Authority: main **40bd8ad8844fd07ce8a138b5520f7f0ec948030f**, package **0.8.0**.
Design: **05cfc68b62215a4c52862e09f081eab1c75ba39f**, `gui-design-refresh/`.
All five requested final design documents were read. They describe the older
9e9a51f merge and the full future GUI. Their former “no GUI endpoints” statement
is historical: merged M10/M10.1 now supplies the read-only viewer. The active
M11A brief narrows five setup steps to **Review/preview only**, superseding the
future design's Run button, job, cancel and recovery actions. This is preparation,
not a candidate acceptance report. No backend science or broad M10 audit was run.

## Function/type boundary map

“Safe” means read-only/pure after authorized path/type checks, not permission to
claim biological validity. The strict zero-execution rule applies to setup paths;
retained Open Existing verification is tested separately under its M10 contract.

| Exact authoritative symbol | Classification | Boundary / failure risk |
|---|---|---|
| [`schemas.py:BarcodeSample`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/schemas.py#L33) | SAFE FOR SETUP VALIDATION | Strict identifier and per-direction sequence/ID presence. No global uniqueness or file checks. |
| [`schemas.py:Sample`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/schemas.py#L54) | SAFE FOR SETUP VALIDATION | Adds editor/treatment, integer nonnegative dpi, biological_replicate, paired and conditional block_id. Paired is statistical, not FASTQ design. |
| [`schemas.py:Target`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/schemas.py#L69) | SAFE FOR SETUP VALIDATION | PE only; requires real WT/intended/spacer/extension. Optional nick/scaffold. Sequence normalization and legacy qwc 0 permitted. Model alone does not certify guide compatibility. |
| [`schemas.py:Config`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/schemas.py#L196) | SAFE FOR SETUP VALIDATION | schema_version integer 1, strict nested config; presence of legacy statistics/quantification options is not qualified GUI capability. |
| [`validation.py:load_samples`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/validation.py#L109) | SAFE FOR SETUP VALIDATION | Read-only CSV, optional catalog resolution; metadata_required=True for workflow. Checks names, IDs, casefold output names, complete barcode pairs. |
| [`validation.py:load_targets`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/validation.py#L157) | SAFE FOR SETUP VALIDATION | Mode dispatch, required columns, duplicate copy/WT/RC checks; not a nuclease single-copy execution gate. |
| [`validation.py:load_config`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/validation.py#L58) | SAFE FOR SETUP VALIDATION | Read-only YAML with duplicate-key rejection; no subprocess. |
| [`validation.py:metadata_warnings`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/validation.py#L183) | SAFE FOR SETUP VALIDATION | Metadata-only warnings and some statistics consistency errors; not read assignment, read geometry or complete inferential-design validation. |
| [`validation.py:validate_metadata`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/validation.py#L224) | SAFE FOR SETUP VALIDATION | Returns valid_metadata, counts/warnings/resolved targets. Explicitly excludes FASTQ/execution/biological validity. Does not automatically resolve bundled catalog like workflow builder. |
| [`barcodes.py:Catalog`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/barcodes.py#L31) | SAFE FOR SETUP VALIDATION | Resolve sequences/catalog IDs, reject conflicts/unknown authoritative entries. Non-authoritative custom catalog builds from rows in memory. |
| [`barcodes.py:load_catalog`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/barcodes.py#L69) | SAFE FOR SETUP VALIDATION | Both directions required; duplicate catalog ID and per-direction sequence checks. |
| [`barcodes.py:validate_catalog_matching`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/barcodes.py#L77) | SAFE FOR SETUP VALIDATION | Full-catalog lengths/minimum distance and mismatch-neighborhood warnings, not classification of reads. |
| [`barcodes.py:extraction_rules`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/barcodes.py#L107) | SAFE FOR PREVIEW | Resolve Python-owned profile offsets, lengths, bridges from recorded config/profile. No FASTQ transformation. |
| [`barcodes.py:identify_barcode`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/barcodes.py#L142) | EXECUTION/PROBE — MUST NOT BE CALLED | Read barcode classifier; no preview dry-run demultiplexing to manufacture assigned-sample counts. |
| [`fastq.py:read_fastq`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/fastq.py#L39) | SAFE FOR SETUP VALIDATION | Read-only streaming four-line/quality/IUPAC validation, authorized regular files only. No barcode assignment. |
| [`fastq.py:paired_fastq`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/fastq.py#L83) | SAFE FOR SETUP VALIDATION | Read-only mate counts/IDs/suffix/CASAVA consistency. Cannot prove swapped unmarked mates or distinct file identity. |
| [`demux_verify.py:verify_demux_output`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/demux_verify.py#L71) | SAFE FOR SETUP VALIDATION | Read-only full external M2 archive verification; may be expensive. Required before claiming verified archive. |
| [`analysis_fastq.py:PreparationConfig`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/analysis_fastq.py#L18) | SAFE FOR SETUP VALIDATION | Nonnegative optional trim integers; model itself does not enforce paired supply. |
| [`analysis_fastq.py:resolve_trims`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/analysis_fastq.py#L23) | SAFE FOR PREVIEW | Both explicit trims or supported untrimmed qi_hitom_v1 recorded layout; no file write/read-length validation. |
| [`backend/pooled.py:validate_targets`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/backend/pooled.py#L69) | SAFE FOR SETUP VALIDATION | Pure PE compatibility: identifiers/reference uniqueness, extension RC substring. Do not confuse with writer/executor. |
| [`backend/pooled.py:preflight_guides`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/backend/pooled.py#L82) | SAFE FOR SETUP VALIDATION | Pure exact-spacer forward/RC checks; reverse-only rejected by qualified PE boundary. |
| [`geometry.py:aligner`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/geometry.py#L11) | SAFE FOR PREVIEW | Existing Python alignment engine factory, no read experiment. Only a reviewed pure annotation wrapper should consume it. |
| [`geometry.py:columns`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/geometry.py#L19) | SAFE FOR PREVIEW | Existing aligned coordinate-pair projection, no fabricated gap index. |
| [`geometry.py:edit_regions`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/geometry.py#L34) | SAFE FOR PREVIEW | Coalesces supplied edit evidence into half-open WT regions; not a frontend formula. |
| [`geometry.py:geometry`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/geometry.py#L48) | AMBIGUOUS — NEEDS IMPLEMENTATION REVIEW | Substitution-only branch is pure reference annotation, but any intended indel invokes synthetic route_pair qualification at lines 240–258. NOT a generic zero-execution preview API. |
| [`routing.py:RoutingPolicy`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/routing.py#L19) | SAFE FOR PREVIEW | Qualified immutable policy values; no target/read qualification by constructing it. |
| [`routing.py:policy_identity`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/routing.py#L38) | SAFE FOR PREVIEW | Declared policy identity only; does not establish copy routing availability. |
| [`routing.py:route_pair`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/routing.py#L238) | EXECUTION/PROBE — MUST NOT BE CALLED | Experimental molecule routing/qualification, even with synthetic perfect pairs and no output writes. |
| [`nuclease/targets.py:NucleaseTarget`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/nuclease/targets.py#L50) | SAFE FOR SETUP VALIDATION | Explicit indel_nuclease, one row; profile/qwc exclusive; target matching pure. Collection scope remains separate. |
| [`nuclease/targets.py:intervals`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/nuclease/targets.py#L9) | SAFE FOR SETUP VALIDATION | Nonempty ordered disjoint inclusive in-bounds ranges; 0 invalid, 0-0 valid. Bare helper does not perform outer whitespace/DNA normalization. |
| [`nuclease/targets.py:coordinate_string`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/nuclease/targets.py#L21) | SAFE FOR PREVIEW | Backend canonical range serialization; frontend must not invent equivalent normalization. |
| [`nuclease/targets.py:tigr_geometry`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/nuclease/targets.py#L25) | SAFE FOR PREVIEW | Exact 18nt forward/RC physical-locus matching and W1–W4 geometry; pure. Prefer validated model.window to raw helper on unnormalized inputs. |
| [`nuclease/qualification.py:scientific_arguments`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/nuclease/qualification.py#L72) | SAFE FOR PREVIEW | 58-field expected map. It is a requirement, not actual observed Core arguments. |
| [`nuclease/qualification.py:validate_arguments`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/nuclease/qualification.py#L78) | SAFE FOR SETUP VALIDATION | Pure presence/type/value validator; no actual execution provenance is available in a new draft. |
| [`workflow_models.py:Node`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_models.py#L63) | SAFE FOR PREVIEW | Typed stage identity, kind, dependencies, relative owned output path, stable sample_id/target_name. |
| [`workflow_models.py:dag`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_models.py#L72) | SAFE FOR PREVIEW | Pure DAG constructor. Caller must supply validated sorted identities and valid mode; function alone treats any non-run mode as analyze. |
| [`workflow_models.py:Plan`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_models.py#L93) | AMBIGUOUS — NEEDS IMPLEMENTATION REVIEW | Pure strict model and graph validation, but requires concrete Backend identity. Do not fabricate executable/hash/version to force preview into M7 execution model. |
| [`workflow.py:build_workflow_plan`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L79) | EXECUTION/PROBE — MUST NOT BE CALLED | Hashes/loads inputs, verifies external M2 and resolves actual executable/version via subprocess; no scientific-output writing is NOT zero-execution. |
| [`workflow.py:scientific_target`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L159) | SAFE FOR PREVIEW | Restores PE analysis_mode excluded from legacy Target dump; nuclease includes resolved window and qualified backend settings. |
| [`workflow.py:parameters_for`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L184) | SAFE FOR PREVIEW | Pure stage-specific parameters from a genuine typed plan; no backend execution. |
| [`workflow.py:signature`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L210) | SAFE FOR PREVIEW | Canonical stable M7 stage identity when genuine plan/dependency identities already exist; not a pre-execution completed-stage signature oracle. |
| [`workflow.py:_check_execution_scope`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L545) | SAFE FOR SETUP VALIDATION | Pure scope gate: one target, single-copy nuclease, no PE policies in nuclease. Private interface; adapter contract needs review. |
| [`workflow.py:software_identity`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L54) | AMBIGUOUS — NEEDS IMPLEMENTATION REVIEW | Hashes package code and calls software_provenance; checkout provenance invokes git subprocesses. Cannot be assumed request-safe. |
| [`provenance.py:software_provenance`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/provenance.py#L12) | EXECUTION/PROBE — MUST NOT BE CALLED | Request path may run git rev-parse/status in a checkout. Installed package can hide this. Audit both source and wheel. |
| [`workflow_storage.py:canonical`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_storage.py#L18) | SAFE FOR PREVIEW | Canonical sorted-key strict JSON. Array order is not normalized for you. |
| [`workflow_storage.py:digest`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_storage.py#L24) | SAFE FOR PREVIEW | SHA-256 canonical JSON; choose authoritative semantic input, exclude UI/revision/timestamp metadata. |
| [`workflow_storage.py:sha`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_storage.py#L28) | SAFE FOR SETUP VALIDATION | Streaming byte hash; requires authorized regular path and before/after mutation handling. |
| [`workflow_storage.py:no_symlinks`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_storage.py#L33) | SAFE FOR SETUP VALIDATION | Rejects symlink ancestors; abspath normalizes .., so this is NOT a traversal/approved-root guard by itself. |
| [`workflow_storage.py:owned`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow_storage.py#L41) | SAFE FOR SETUP VALIDATION | Rejects invalid POSIX-relative artifact paths, checks containment/symlinks. Not an allowlist for arbitrary user absolute paths. |
| [`workflow.py:force_closure`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L418) | AMBIGUOUS — NEEDS IMPLEMENTATION REVIEW | Pure graph operation, but M11A has no resume/force feature; trap its use in setup scope. Future recovery remains backend-owned. |
| [`statistics.py:load_contrasts`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/statistics.py#L84) | SAFE FOR SETUP VALIDATION | Read-only strict specification validation, not enough to certify sample coverage/contrast estimability. |
| [`metrics/policy_requests.py:prepare_policies`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/metrics/policy_requests.py#L37) | SAFE FOR SETUP VALIDATION | Pure requests validation; invalid requests retained with reasons rather than raised. Adapter must not treat returned object as all-valid. |
| [`workflow.py:verify_workflow_output`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L520) | AMBIGUOUS — NEEDS IMPLEMENTATION REVIEW | Read-only existing-workspace verifier for retained M10 reader; includes stage validators/PE geometry trials. Not a new-draft validation shortcut. |
| [`workflow.py:execute_workflow`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L557) | EXECUTION/PROBE — MUST NOT BE CALLED | Creates parent/lock before complete plan resolution; then snapshots/stages/results. Not even with a dry-run/invalid draft. |
| [`workflow.py:resume_workflow`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/workflow.py#L667) | EXECUTION/PROBE — MUST NOT BE CALLED | Calls execute_workflow(resume=True); can execute, invalidate, delete, write sessions. |
| [`analysis_fastq.py:prepare_analysis_fastqs`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/analysis_fastq.py#L42) | EXECUTION/PROBE — MUST NOT BE CALLED | Creates transformed FASTQs/manifests/staging. |
| [`demux.py:demultiplex`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/demux.py#L101) | EXECUTION/PROBE — MUST NOT BE CALLED | Classifies and writes samples/QC/staging; same-file guard must be exposed without executing this API. |
| [`routing.py:route_analysis`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/routing.py#L310) | EXECUTION/PROBE — MUST NOT BE CALLED | Runs qualification/routing, writes output. |
| [`metrics/production.py:run_metrics`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/metrics/production.py#L375) | EXECUTION/PROBE — MUST NOT BE CALLED | Core execution and M4 result generation. |
| [`nuclease/backend.py:run_nuclease_metrics`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/nuclease/backend.py#L80) | EXECUTION/PROBE — MUST NOT BE CALLED | Core execution and nuclease result generation. |
| [`aggregation.py:summarize`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/aggregation.py#L329) | EXECUTION/PROBE — MUST NOT BE CALLED | M5 computation even with output=None; no metadata-only shortcut. |
| [`statistics.py:stats`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/statistics.py#L199) | EXECUTION/PROBE — MUST NOT BE CALLED | M5 inferential computation, not setup validation. |
| [`reporting.py:generate_report`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/reporting.py#L332) | EXECUTION/PROBE — MUST NOT BE CALLED | Rendering/writing reports; no draft report preview. |
| [`backend/pooled.py:resolve_executable`](https://github.com/jily327/crispresso-pe-pipeline/blob/40bd8ad8844fd07ce8a138b5520f7f0ec948030f/src/peanalyzer/backend/pooled.py#L51) | EXECUTION/PROBE — MUST NOT BE CALLED | shutil.which then executable --version through subprocess.run. |

## Input and target contracts

One raw R1/R2 **pool**, many sample-sheet rows; alternatively one verified immutable
M2 archive. No one-file-pair-per-biological-row, concatenation, interleaved, single
end or arbitrary prepared FASTQ import contract exists. Full workflow metadata
uses `Sample`; demux-only minimal `BarcodeSample` is insufficient. Every expected
sample joins M4/M5 by `barcode_id`, not `sample_name`. Sample_name is also globally
unique in load_samples; condition tuples are not. Same condition+target+biological
replicate is rejected later by M5 (aggregation.py:collect_observations); do not
invoke M5 to discover this. `paired` means experimental blocking and requires
block_id, independently of paired-end sequencing.

A shared F or R barcode is valid; a duplicate complete F/R pair is not. The full
qi_hitom_v1 catalog intentionally contains unused combinations. `validate_metadata`
does not automatically load that catalog while workflow/demux do. Catalog ID
resolution must be explicit and consistent. Custom catalogs enforce same length
per direction, minimum distance and mismatch constraints through the existing
validator; schema construction alone misses these gates.

PE `Target` accepts SNP/substitution/insertion/deletion intended products, ACGT
references, U→T for RNA guide/extension fields, optional nick/scaffold. It neither
requires 20nt spacers nor proves their compatibility. `validate_targets` and
`preflight_guides` are pure qualified checks. PE reverse-only spacers are rejected;
nuclease TIGR reverse physical matches are supported. Group copies by target_name;
never synthesize copy-specific guides. Geometry enforces shared experimental
spacer/extension/nick/scaffold. Schema validity and unresolved copy-routing
qualification must stay distinct; copy blocking need not erase valid target-level
PE scope. No empirical route_pair trial may run during M11A preview.

Nuclease requires explicit indel_nuclease; single target/copy execution is a
collection gate, not guaranteed by constructing individual NucleaseTarget rows.
Explicit qwc and TIGR profile are alternatives. Explicit qwc is ordered, disjoint,
zero-based inclusive and in bounds. Nuclease rejects `0`, accepts `0-0`, and
canonicalizes leading zeros. PE legacy `0` is accepted and is not the same contract.
TIGR is pure exact 18nt matching, forward/reverse deduplicated by physical start.
Palindromic targets have one resolved physical locus with null directional labels.
W2 defaults only when omitted; W1/W3/W4 are supported. The UI renders Python's
returned window, coordinates, interval, orientation and cuts, never derives them.

## Scientific configuration and identity

Use the expected nuclease map from `scientific_arguments`: 56 literals plus WT and
normalized qwc = 58 typed values. M11A can display the **required configuration**;
it cannot claim an actual executable/version, resolved Core arguments or population
qualification was observed. No execution means no backend-read counts or PE/indel
fractions in Review. Do not fabricate Backend.executable_sha256 to satisfy Plan.

Current M7 Plan is an execution description, not a ready-made zero-probe draft
contract. `build_workflow_plan` always resolves Core; its docstring “without writing”
is not a zero-execution guarantee. A candidate needs a separately reviewable
backend-owned preview contract that reuses pure models/DAG rules and records the
unverified runtime requirement explicitly. No frontend Plan/identity reconstruction.

Current stage signature contains workflow contract, node, software identity,
metric-stage backend identity, normalized stage parameters, relevant input byte
hashes/sizes and dependency signature/output hashes. No execution timestamps.
`scientific_target` inserts PE mode omitted by legacy Target.model_dump; nuclease
identity includes normalized input, resolved geometry and all 58 expected arguments.

Earliest conservative lineage dependencies: raw bytes/samples/config/catalog →
demux; trim settings → analysis; target/copy/intended/profile/window → routing and
metrics; PE policies → metrics; samples/contrasts → statistics; title → report.
Scientific sample metadata (including sample_name) is not just GUI chrome. Full
Plan JSON includes paths, output, software/runtime provenance and title; its digest
need not be invariant to moving files or report-title changes. Require a clearly
defined scientific preview payload/hash distinct from transport revision and any
execution/report identity. Equal normalized qwc or omitted/explicit W2 have equal
scientific target identity, but imported byte hashes may differ. Sorted DAG
semantics survive reordered rows; exact imported file identities must not be erased.

The raw DAG has **6 + 2*S*T nodes**; analyze has **5 + 2*S*T**. Routing/metrics nodes
are per sample×target, not per copy. For two samples/two targets: 14/13 nodes.
Production supports one target, even though pure planning supports multi-target
DAGs. Nuclease retains the routing slot as a single-copy identity check, not PE
routing. Unsupported scope must be explicit and cannot receive an execution-ready
validation claim merely because the DAG/model is structurally valid.

## File/output checks and unresolved validation stages

Authoritative same-file demux guard compares resolved paths; paired_fastq alone
can read the same unmarked file twice. File handles need explicit distinct-file
validation (including same physical inode), authorization/containment and content
identity. Swapped annotated mates are rejected by read_id; swapped unmarked mates
cannot always be proven. Never silently swap roles by filename inference.

Read-only FASTQ synchronization/format/minimum-length inspection is validation,
not demultiplexing. Barcode-to-sample counts are not known without classification;
missing expected reads/unused catalog entries must not become fabricated counts or
inferred sample deletion. Length equal to trim is invalid. For raw pools, do not
claim a short unassigned molecule proves every biological sample invalid: state
whether validation is a conservative all-input check, or evidence is unavailable
until demux. For M2 archives, relevant per-sample lengths can be inspected read-only.

`no_symlinks` normalizes `..` through abspath; it is not an approved-root/traversal
guard. Use the candidate's explicit authorization boundary, raw-path rejection,
regular-file checks, opaque handles and containment. Existing empty output roots
are rejected by current initial execution, so setup must not imply they are safe
new destinations. Do not call execute_workflow even with invalid inputs: it creates
parent/lock first. No test-create/delete writability probe in scientific output;
use read-only permission evidence, report uncertainty, and snapshot attempts plus
final filesystem state. Do not add resume/force as an implicit response to an
existing workspace.

## Likely implementation traps to investigate, not candidate findings

- geometry(indel) silently crosses from reference annotation into experimental routing.
- build_workflow_plan and source-checkout software_provenance can launch processes.
- Model/CSV validity can precede stricter collection/scope/M5 validation.
- The full design's future Run/Recovery controls exceed the current M11A boundary.
- A single shared PE/nuclease form serializer can leak hidden incompatible fields.
- Display row order and asynchronous response order are not stable scientific identity.
- Cheap file stats do not replace content identity, and basename labels are not handles.
- Existing M10 helper capabilities may compute git provenance on request; test the
  actual setup request graph under the subprocess tripwire, not only final handlers.
