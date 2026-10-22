# Pipeline architecture and contracts

## Current M4 layer

The audited M3.1.2 merge `550df70f9f9627c7218b9f047d0b6bf3023b8d25` is
the routing/backend boundary for M4. [M4 measurement contracts](m4-metrics.md)
supersede the historical proposed metric formulas and future-module descriptions
below. `metrics/models.py` defines the strict versioned result,
`metrics/products.py` accounts for observable exact products, and
`metrics/production.py` executes/collects verified Core analyses. The packaged
`metrics/result.schema.json` exposes JSON Schema; model validators additionally
enforce arithmetic and population consistency.

Target native uses empirically invariant conventional Core anchors on **all
prepared target reads**. Target precise uses exact amplicon-end assessment of
that same original population, independently of copy routing. Copy native and
precise metrics describe **only verified M3.1.2 confident cohorts**. Native
denominator is authoritative aligned reads; precise denominator is exact WT +
exact PE, never the older generic `analyzable_reads` proposal. Target and copy
population IDs, input counts and assessment stages are explicit. Empty
authoritative native quantification windows BLOCK production reporting.

Routing, backend preprocessing/alignment and product assessability each affect
the applicable denominator. No single stage defines all denominators. Exact PE
may be higher or lower than native PE; direction alone has no quality meaning.
Insertion-bearing fragments may be preferentially quarantined by the existing
observed-flank rule, so copy cohorts may be PE-depleted. M4 exposes these counts
and this limitation without correction. All 23 previously blocked indel designs
remain blocked. M2 behavior and M3–M3.1.2 evidence remain unchanged.

## Historical M1–M3 design and investigation

M3.1 update: [explicit routing/preflight/metric contracts](m31-routing.md) qualify
a conservative replacement for the failed default Pooled routing behavior below.
The historical M3 result remains FAIL. M3.1's tested explicit routing gate is PASS;
only supported target geometry is eligible, and final production PE metrics are
not implemented. `analysis_verify.py`, `geometry.py`, `routing.py`, `backend/core.py`
and `backend/metrics.py` implement the new boundaries without changing M2.

Status: metadata validation, paired barcode demultiplexing/QC, completion
verification, analysis preparation and external CRISPResso2 diagnostics are
implemented. **ROUTING GATE: FAIL** in the actual 2.3.4 synthetic experiment;
production copy quantification and downstream analyses remain blocked.
See [M3 contracts, evidence and reproduction](m3-backend-validation.md).
Repository inspection found only a two-line README at `9262a3d` on `main`, with
no code, tests, CI, dependency pins or agent instructions. Development belongs on
feature branches; M3 uses `feat/crispresso-integration` from
`ae7e7f3e1f9144ea2092d9a6201a4d137a024214`. `main` remains the stable integration branch.

## Workflow and module boundaries

Raw paired FASTQ → inline barcode demultiplexing → sample FASTQ pairs →
**validated copy-routing gate** → CRISPRessoPooled → machine-readable PE metrics →
copy/target aggregation → biological statistics → tables, plots and HTML.

The gate is necessary because default Pooled routing cannot ensure the requested
homeolog ambiguity policy. It must not be bypassed to make an end-to-end run pass.
Keep CRISPResso as the editing alignment/classification engine. Do not implement
an alternative editing aligner or modify its source.

Current files:

```text
pyproject.toml                    package metadata, CLI, pytest configuration
MANIFEST.in                       include docs, fixtures and tests in source builds
requirements-dev.lock            exact tested Python development dependencies
src/peanalyzer/
    __init__.py, __main__.py       package version and python -m entry point
    cli.py                        argparse boundary; validate and demux
    schemas.py                    typed, extra-field-forbidding metadata models
    validation.py                 CSV/YAML readers and cross-row diagnostics
    barcodes.py                   catalog resolution, extraction, independent matching
    fastq.py                      lossless four-line streaming and paired-ID validation
    demux.py, demux_output.py      staged publication, classification, accounting, gzip and QC
    provenance.py                 demux software/environment identity
    demux_verify.py               independent completed-archive integrity/recount
    analysis_fastq.py             verified archive → separate trimmed inputs
    backend/pooled.py             exact TSV, preflight, external execution/provenance
    backend/synthetic.py          artificial copies and independent read truth
    backend/routing_validation.py  synthetic-only BAM/handoff/reference audit
    barcode_sets/qi_hitom_v1.csv   canonical 12-forward/8-reverse catalog data
    profiles/qi_hitom_v1.yaml      verified extraction/bridge layout data
examples/{samples.csv,targets.csv,config.yaml}
examples/{ev_only_1005_samples.csv,qi_hitom_config.yaml}
tests/{conftest.py,test_metadata.py,test_config.py,test_cli.py}
tests/{synthetic.py,test_barcodes.py,test_fastq.py,test_demux.py}
docs/{architecture.md,demultiplexing.md}
README.md
```

Planned modules, **not placeholder implementations in this milestone**:

| Module | Responsibility / contract |
| --- | --- |
| `reference_qc.py` | Compare WT/PE references using a tested library alignment; report SNPs/indels, diagnostic variants and edit-site proximity with explicit coordinates |
| `backend/outputs.py` | Versioned JSON/TSV/ZIP adapters; fail on unknown layouts or inconsistent counts; no HTML scraping |
| `quantification.py` | Pure count-to-metric functions; distinguish exact PE from PE-reference assignment |
| `aggregation.py` | Long-form sample × target × copy results; weighted/unweighted target summaries and copy balance |
| `statistics.py` | Biological sample/block design, contrasts, model fitting and multiple-test correction |
| `reporting.py` | CSV/TSV, plots, report and links to individual CRISPResso reports |
| `workflow.py`, future provenance extensions | DAG, stage manifests, resume, logs and `--force`; basic demux provenance is implemented |

CLI remains a thin caller of reusable Python functions so a future GUI can
use the same contracts. Future commands: `run`, `analyze`, `summarize`,
`stats`, `report`. Currently they are rejected, not successful no-ops.

## Dependencies and reproducibility

Milestones 1–2: Python >=3.11, Pydantic 2, PyYAML 6, matplotlib, setuptools; development uses
pytest and build. The lock records the tested Python 3.12 environment; its
NumPy/contourpy pins require >=3.12. It is version-pinned, not a platform-independent
or artifact-hashed lock. Models are
the schema source of truth; `Sample.model_json_schema()`,
`Target.model_json_schema()` and `Config.model_json_schema()` expose JSON Schema
for the **normalized records**, not CSV parsing or cross-row uniqueness rules.

Milestone 3: independently pin CRISPResso2 **2.3.4**, Bowtie2, samtools and fastp
in an isolated environment or container with a recorded image digest. Pooled
2.3.4 uses **fastp** for paired merging; do not copy older FLASH/Trimmomatic setup
instructions. CRISPResso's Python dependencies include NumPy, pandas, scipy,
matplotlib, seaborn and Jinja2, with Cython/C build requirements. Only the plotting
dependencies are package dependencies; the CRISPResso toolchain runs externally.
M3 actually executed the official v2.3.4 image by digest, with Bowtie2 2.5.5,
samtools 1.23.1 and fastp 1.3.3; see the M3 evidence for exact probes.
Verify upstream license terms before
redistributing a backend image. No external service or credentials are required
for local analysis; installing packages requires access to their registries.

Later reporting may add pandas/Jinja2; statistics may use an isolated,
versioned R + glmmTMB backend for beta-binomial mixed models. These are decisions
to validate in their milestones, not installed dependencies now.

## Input schemas (version 1)

CSV files are UTF-8 (BOM accepted), comma-delimited, with exact case-sensitive
headers. Header order is arbitrary. Reject duplicate/unknown/missing columns,
ragged rows, empty datasets and malformed quoting. Full metadata validation
requires the biological columns below, with barcode sequences or IDs per end;
demux additionally accepts the minimal sample schema described below. All base
target headers are required; explicitly nullable cells may be blank. Optional
override columns may be absent or blank. Strip surrounding cell whitespace;
preserve identifiers such as replicate `01` as strings. `NA` is not a null token.

Identifiers match `[A-Za-z0-9][A-Za-z0-9_.-]*`. Identifiers are never lossily sanitized. This prevents path traversal;
actual sample output filenames are additionally checked with `casefold()` to
reject collisions on case-insensitive filesystems after cell normalization. DNA is nonempty A/C/G/T; normalize case, reject
N, gaps, ambiguity codes, U and internal whitespace. RNA fields additionally
accept U and explicitly normalize it to T for the backend. Reference ambiguities
need an explicit schema/backend extension, not silent normalization.

### samples.csv

One row is one sample in **one sequencing run**, including controls. Reused
individual forward or reverse barcodes are valid; the pair must be unique.
Milestone 2 adds `forward_barcode_id` and `reverse_barcode_id` references to a
catalog. Each end requires a sequence or an ID; if both are supplied they must
agree. `demux` accepts a minimal routing sheet containing `sample_name`,
`barcode_id` and the two end definitions, as shown in
`examples/ev_only_1005_samples.csv`. It also accepts full Milestone 1 sheets.
`validate` still requires full biological metadata and targets; provide
`--barcodes <catalog.csv>` when those full sheets use catalog IDs. No editor,
treatment, dpi, replicate or pairing values are fabricated for the minimal sheet.

| Column | Type and meaning |
| --- | --- |
| `sample_name` | Unique identifier, biological sample identity |
| `barcode_id` | Unique identifier, stable output stem; not an inferred biological replicate |
| `forward_barcode`, `forward_barcode_id` | DNA barcode expected on R1, or a forward catalog ID; either or both |
| `reverse_barcode`, `reverse_barcode_id` | DNA barcode expected on R2 using configured orientation, or a reverse catalog ID; either or both |
| `editor`, `treatment` | Nonempty categorical strings; no hard-coded level names |
| `dpi` | Nonnegative integer days post intervention; fractional days need a schema change |
| `biological_replicate` | Nonempty identifier, preserved as string; may repeat across treatment groups |
| `block_id` | Nullable identifier; required when `paired=true` |
| `paired` | Explicit `true`/`false` (case-insensitive in CSV); rejects 0/1, yes/no and blanks |

Barcode lengths are configurable. The default `qi_hitom_v1` profile specifies
9 nt at offset 0 on each end, matching the user-verified Qi-Lab/Azenta layout:

```text
R1: [GCTT + 4 variable bases + T] [GGAGTGAGTACGGTGTGC] [amplicon...]
R2: [CTGT + 4 variable bases + T] [GAGTTGGATGCTGGATGG] [amplicon...]
```

The canonical 20 motifs and bridge/layout settings live in package CSV/YAML
resources, not Python constants. Custom catalogs and a `custom` profile support
other offsets/lengths, but demux requires equal lengths within each direction.
Mixed-length/prefix catalogs are rejected before FASTQ processing. Catalog-free
explicit sequences require the custom profile and no supplied catalog; bundled
and supplied catalogs are authoritative and cannot be extended by sample rows.
Matching is exact by default, optionally substitution-only Hamming with a maximum
per end. It does not support barcode indels or scanning arbitrary positions. Demux rejects
k >= minimum same-side distance (and k >= motif length), and warns when
2*k >= minimum distance. Qi supports k=0 or k=1 only. Actual ties
will be quarantined, never resolved by row order. A valid sample pair requires
both barcode ends to be uniquely identified; resolving an ambiguous end solely
using the expected pair list could conceal recombination and is disallowed.

Implemented exclusive categories are `assigned_expected_pair`,
`unexpected_valid_barcode_pair`, `ambiguous_barcode_match`, `forward_only`,
`reverse_only`, `no_barcode_match`. Their sum must equal input **read pairs**.
Only assigned expected pairs enter sample FASTQs. The complete F × R matrix
retains both expected and unexpected recognized pairs, including zero cells;
other categories appear separately in the summary. No expected pair can resolve
a tied barcode. Preserve header, sequence, plus and quality bytes by default;
trimming requires explicit configuration. Bridge validation is diagnostic only.
See [demultiplexing.md](demultiplexing.md) for precise rules, output schemas,
synthetic evidence and the real-data regression targets.

M2.1 publishes only a fully staged, reconciled, hashed run. Future M3 must enforce
the [completion contract](m2-hardening.md#downstream-completion-contract), including
summary status, reconciliation and output hashes, before consuming sample FASTQs.
A convenience heatmap may fail with a warning; authoritative tables may not.

### targets.csv

One row per `(target_name, copy_name)`; no fixed number of copies or targets.
All listed targets are assayed in all listed samples in version 1. Treatment
labels do not filter targets. Selective sample-target applicability requires a
future explicit design table.

| Column | Type and meaning |
| --- | --- |
| `target_name`, `copy_name` | Identifiers; pair unique; `__` reserved |
| `wt_sequence` | Complete WT amplicon DNA, without inline barcodes/adapters |
| `prime_edited_sequence` | Complete intended PE amplicon in the same strand orientation; must differ from WT; intended indels allowed |
| `pegRNA_spacer` | Actual experimental RNA guide 5′→3′ without PAM; shared guides remain identical on copy rows; never an implicit analysis override |
| `pegRNA_extension` | Required RNA extension 5′→3′: RT template then PBS |
| `nicking_guide` | Nullable RNA 5′→3′ without PAM (e.g. absent for PE2) |
| `pegRNA_scaffold` | Nullable RNA scaffold preceding the extension, 5′→3′ |

Generate backend name `target_name__copy_name` and save the mapping; no lossy
sanitization. WT amplicons must be distinct **across the whole file**, including
reverse complements. The pinned Pooled implementation even rejects a
self-reverse-complementing WT; validator reports that backend limitation.
Cross-copy WT/PE or PE/PE collisions are warnings requiring biological review.

Optional flat columns, repeated per copy when shared by a target:

| Column | Constraint / backend mapping |
| --- | --- |
| `quantification_window_coordinates` | String `0` (backend's disable-filter sentinel) or ordered, disjoint `start-end[_start-end]` ranges; zero-based inclusive WT coordinates, in bounds; maps identically |
| `quantification_window_size` | Integer >=0; maps identically |
| `quantification_window_center` | Signed integer; maps identically |
| `prime_editing_pegRNA_scaffold_min_match_length` | Integer >0, requires scaffold and cannot exceed its length; maps identically |

Coordinates take precedence over size/center in CRISPResso. Do not overload
coordinate `0` to mean just base zero; use `0-0`. Backend behavior for window
transfer to PE indels needs integration fixtures. These windows affect backend
metrics, not the proposed full-amplicon exact-match metric. Free-form shell
arguments and arbitrary CRISPResso options are deliberately absent. Add future
options through a reviewed typed allowlist.

Milestone 1 checks syntax, uniqueness, collisions and exact substring warnings.
It does **not** validate pegRNA design or calculate a SNP/indel alignment report.
The original roadmap proposed a generalized reference report: lengths; pairwise WT and PE
alignments; SNP counts, indel events and affected bases; diagnostic positions;
distance/overlap with intended edits; and whether read coverage observes those
positions. Use a tested alignment library, flag non-unique alignments in repeats,
and report reference-relative coordinates. A difference in equal-length strings
is not automatically a SNP: compensating indels can occur. The current M3 task
validates a controlled, documented synthetic design; a generalized reference-QC
aligner remains deferred after the failed routing gate.

### config.yaml

Safe YAML mapping, no duplicate or unknown keys; strict native YAML numeric and
boolean types. Required `schema_version: 1`. Defaults are listed below;
`examples/config.yaml` explicitly selects the custom profile, while
`examples/qi_hitom_config.yaml` records the verified protocol. Empty configuration
files fail. CLI metadata
paths are supplied explicitly and resolved relative to the invoking working
directory; FASTQ paths and output directory are CLI inputs, never inferred
from fixed filenames. Relative executable paths also use the invocation directory.

| Section / field | Accepted values and defaults |
| --- | --- |
| `n_processes` | Positive integer, 1; future total worker budget, not workers per sample |
| `demux.profile` | `qi_hitom_v1` (default) or `custom`; bundled profile data, with explicit field overrides |
| `demux.forward_offset`, `reverse_offset` | Nonnegative integer, 0; zero-based positions in the respective raw read |
| `demux.forward_length`, `reverse_length` | Optional positive integers; profile uses 9, custom defaults to catalog motif lengths |
| `demux.forward_bridge`, `reverse_bridge` | Optional DNA overrides; explicit null disables the respective bridge |
| `demux.reverse_barcode_orientation` | `as_read` (default) or `reverse_complement`; forward barcode always as read |
| `demux.max_mismatches` | Nonnegative integer, 0 per end; catalog-aware bounds enforced by demux |
| `demux.trim_barcodes`, `trim_bridges` | Booleans, false; bridge trimming requires barcode trimming and configured bridges |
| `demux.bridge_qc` | Boolean true; bridge matches never control assignment |
| `demux.max_open_sample_pairs` | Positive integer, 32; bounded LRU of gzip output pairs |
| `demux.ambiguous_policy` | Only `unassigned`; no sample-expectation rescue |
| `crispresso.pooled_executable`, `core_executable` | Nonempty executable names/paths, `CRISPRessoPooled` and `CRISPResso` |
| `crispresso.version` | Only quoted string `"2.3.4"`; compatibility target, not proof of an installation |
| `crispresso.min_reads_to_use_region` | Nonnegative integer, 100; explicit pipeline choice, upstream default is 1000 |
| `crispresso.copy_assignment_policy` | Only `require_validated`; no unsafe permissive fallback |
| `quantification.primary_metric` | `precise_full_amplicon` (default) or explicitly selected `pe_reference_assigned` |
| `quantification.denominator` | Only `nonambiguous_nondiscarded_aligned` |
| `qc.min_analyzable_reads` | Positive integer, 100; low coverage flagged, not called zero editing |
| `qc.min_copy_fraction`, `max_ambiguous_fraction` | Finite fractions in [0,1], 0.1 each; provisional research thresholds |
| `qc.discriminating_variant_edit_distance` | Nonnegative bases, 5; provisional proximity warning radius |
| `statistics.mode` | `none` (default), `simple`, `factorial`; analysis not implemented |
| `statistics.factors` | Unique list from `editor`, `treatment`, `dpi`; default []; active mode requires nonempty list |
| `statistics.block_column` | `null`, `block_id`, `biological_replicate`; all selected values must be present; paired rows require `block_id` in active mode |
| `statistics.include_interaction` | Boolean false; true requires factorial mode and >=2 factors |
| `statistics.min_biological_replicates` | Integer >=2, default 3; warning threshold, not a power guarantee |

`mode: none` cannot silently carry factors/block settings. Version 1 factors are
metadata field names, not formulas or executable R. Explicit contrasts, continuous
dpi coding, multiplicity families and random-effect structure will be finalized
in Milestone 6. An accepted factorial configuration does not certify complete
blocks, model identifiability or adequate biological replication. Synthetic
examples are short metadata fixtures, not validated pegRNA designs or usable
sequencing references.

## CRISPRessoPooled integration investigation

Source inspected on 2026-10-20: upstream tag **v2.3.4**, commit
`1fc4b629e5400a48d6569b0ab4b8d1766f33636f`. These findings come from the actual
parser, routing and output-writing source, not an executed CRISPResso run:

- [Pooled TSV parsing, supported headers and duplicate checks, lines 615–775](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoPooledCORE.py#L615)
- [Bowtie2 routing and per-row Core commands, lines 777–942](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoPooledCORE.py#L777)
- [PE reference/orientation checks, Core lines 3083–3156](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoCORE.py#L3083)
- [Core ambiguity and scaffold handling, lines 855–875](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoCORE.py#L855)
- [Allele row fields and count semantics, Core lines 4014–4118](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoCORE.py#L4014)
- [Allele ZIP and quantification/mapping tables, Core lines 4610–4708](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoCORE.py#L4610)
- [Core JSON counters, lines 6499–6519](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoCORE.py#L6499)
- [Pooled summaries, lines 1492–1602](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoPooledCORE.py#L1492)
- [Authoritative option declarations](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/args.json)
- [JSON encoding conventions, Shared lines 797–887](https://github.com/pinellolab/CRISPResso2/blob/1fc4b629e5400a48d6569b0ab4b8d1766f33636f/CRISPResso2/CRISPRessoShared.py#L797)

### Exact invocation and reference mapping

Use **amplicon-only mode**, `-f` with no genome `-x`, once per biological sample
after inline demultiplexing and routing qualification. Generate a **tab-delimited,
headered** amplicon file (not targets.csv passed directly), one WT row per copy:

| Metadata | Exact Pooled TSV header |
| --- | --- |
| Generated `target__copy` | `amplicon_name` |
| `wt_sequence` | `amplicon_seq` |
| `prime_edited_sequence` | `prime_editing_override_prime_edited_ref_seq` |
| `pegRNA_spacer` | `prime_editing_pegRNA_spacer_seq` |
| `pegRNA_extension` | `prime_editing_pegRNA_extension_seq` |
| `nicking_guide` | `prime_editing_nicking_guide_seq` |
| `pegRNA_scaffold` | `prime_editing_pegRNA_scaffold_seq` |
| Four optional override columns above | Same names |

Use explicit `NA` for absent optional backend cells (Pooled skips this sentinel),
not missing trailing TSV cells; its parser strips lines. Our CSV blank-null
convention and generated backend TSV sentinel convention are intentionally distinct.
Do not put PE sequences in `expected_hdr_amplicon_seq`: HDR is a different mode.
Do not create PE as a second independent Pooled row: it competes in copy routing
and does not configure the intended WT/PE classification relationship.

Illustrative exact argv for the example settings, **not a validated production
command for similar homeologs yet**:

```sh
CRISPRessoPooled \
  -r1 results/02_demultiplexed_fastq/4A_R1.fastq.gz \
  -r2 results/02_demultiplexed_fastq/4A_R2.fastq.gz \
  -f results/03_CRISPResso/4A/amplicons.tsv \
  -o results/03_CRISPResso/4A --name 4A \
  --crispresso_command CRISPResso \
  --n_processes 1 --min_reads_to_use_region 100 \
  --write_detailed_allele_table --keep_intermediate
```

The resulting parent directory is `.../4A/CRISPRessoPooled_on_4A/`, with
`CRISPResso_on_<amplicon_name>/` children. Discover child paths through the
manifest, rather than assume cleaning never changes a name. In the amplicon-only
branch 2.3.4 tests `n_reads > min_reads_to_use_region`, not `>=`; exactly 100
reads at the example cutoff are **skipped**, not a failed run or zero edits.

Per-row options override shared Core options. PE mode requires an extension
**and** spacer even with an explicit edited reference. Orient WT/PE so the spacer
is on the forward reference strand and the extension's reverse complement is
contained in the PE sequence. The backend still performs orientation, extension
and reference consistency checks. Do not enable
`--prime_editing_override_sequence_checks` to conceal a design mismatch.

Leave `--assign_ambiguous_alignments_to_first_reference` and
`--expand_ambiguous_alignments` **unset**. Do not discard indel reads or ignore
substitutions/insertions/deletions. Preserve the detailed allele table and
intermediates for auditing. The runner will use argv lists, capture exit status,
and stage inputs under safe generated names: Pooled itself constructs shell
commands, so merely passing a Python argv list does not solve arbitrary-path
quoting in its internal commands.

### Why default multi-copy routing is insufficient

Pooled builds a Bowtie2 index from **WT amplicons only**, merges paired reads with
fastp and routes alignments into per-amplicon FASTQs. Its default Bowtie2 options
do not enumerate and quarantine tied homeolog hits; the default SAM filter is
only unmapped flag `4`, and the routing code does not apply a MAPQ/score-gap gate.
The Core ambiguity flags operate **after** this step, among WT and PE references
inside one copy. They cannot recover cross-copy ties that Bowtie2 already routed.
An intended edit may erase a diagnostic SNP or make a read closer to another
copy's WT. Merely adding `-k 2`/`-a` also risks duplicated FASTQ records and counts;
filtering secondary alignments does not prove the primary assignment unique.

Milestone 3 must investigate a wrapper-owned routing audit using standard Bowtie2
alignments against **all WT and intended PE haplotypes**, collapsed to copy IDs,
with read-ID accounting and conservative tie/insufficient-evidence exclusion.
This reuses an aligner; it is not a replacement edit classifier. Include both
WT and PE references to evaluate editing-dependent assignment bias. A numeric
MAPQ threshold alone is not proof that all competing copies were considered.

Candidate accepted-read cohorts can then enter Pooled, but the retained
`CRISPResso_AMPLICONS_ALIGNED.bam` routing must agree with the audit per read ID.
If WT-only Pooled routing disagrees, fail and withhold copy-specific estimates.
A fallback of preassigned per-copy cohorts with one-row Pooled calls would change
the requested one-Pooled-run-per-sample architecture; document and review that
choice before adopting it. Neither approach is implemented or claimed validated.
Keep `require_validated` as a gate until synthetic experiments establish safe
behavior. This limitation does not block metadata validation or demux development.

## Machine-readable output and metric contract

Use `json.load`, tabular readers and ZIP member streams; no HTML and no pickle.
CRISPResso JSON contains `_type`/`value` wrappers for arrays, namespaces,
dataframes and other objects. Decode only known needed structures without eval
or importing the backend's custom decoder. Validate the version and required
fields, bounded counts, reference identities, completion marker and filenames.
Do not treat an early-written info JSON as proof of successful completion.

| File / exact field | Intended use |
| --- | --- |
| Parent `CRISPResso2Pooled_info.json` | `running_info.version`, `args`, `command_used`, `end_time_string`; `results.good_region_names`, `good_region_folders`, `failed_batch_arr`, `failed_batch_arr_desc`; distinguish successful, failed and skipped copies |
| Parent `REPORT_READS_ALIGNED_TO_AMPLICONS.txt` | `amplicon_name`, `run_name`, `n_reads`, `n_reads_aligned_%`, `crispresso_command`, `crispresso_output_folder`; route counts and subcommand provenance |
| Parent `MAPPING_STATISTICS.txt` | Colon-delimited `READS IN INPUTS`, `READS AFTER PREPROCESSING`, `READS ALIGNED`; sample-level attrition, not PE counts |
| Parent `SAMPLES_QUANTIFICATION_SUMMARY.txt` | `Name`, `Reads_total`, `Reads_aligned`, `Unmodified`, `Modified`, `Discarded`; sanity-check only, since WT/PE/scaffold reference strata are aggregated |
| Child `CRISPResso2_info.json` | `results.ref_names`, `results.refs[ref].sequence` and `include_idxs`; verify WT/PE reference/window identity; `results.alignment_stats` counters below |
| Child `CRISPResso_quantification_of_editing_frequency.txt` | Per `Amplicon`: `Reads_aligned`, `Unmodified`, `Modified`, `Discarded`, `Insertions`, `Deletions`, and combination columns; cross-check JSON totals; window-relative modifications |
| Child `CRISPResso_mapping_statistics.txt` | Tab-delimited `READS IN INPUTS`, `READS AFTER PREPROCESSING`, `READS ALIGNED`, `N_COMPUTED_ALN`, `N_CACHED_ALN`, `N_COMPUTED_NOTALN`, `N_CACHED_NOTALN`; attrition and reconciliation |
| Child `Alleles_frequency_table.zip` → `Alleles_frequency_table.txt` | Integer `#Reads`, `Aligned_Sequence`, `Reference_Sequence`, `Reference_Name`, `Read_Status`, `n_deleted`, `n_inserted`, `n_mutated`; with detailed flag also `Aligned_Reference_Names`, `Aligned_Reference_Scores`, `ref_positions`, `all_insertion_positions`, `all_deletion_positions`, `all_substitution_positions` |

Discover child filenames from `running_info.quant_of_editing_freq_filename`,
`mapping_stats_filename`, `allele_frequency_table_zip_filename` and
`allele_frequency_table_filename`. The last names the member **inside the ZIP**;
the plain file is normally removed. Stream the specified member; reject unsafe
paths. Percentages are display values; sum integer counts, not rounded `%Reads`.

For JSON counters below, `A = results.alignment_stats`. The default WT reference
name is typically `Reference`; verify its sequence rather than relying on that
label. PE is `Prime-edited`, scaffold is `Scaffold-incorporated` when configured.

| Pipeline metric | Source and definition |
| --- | --- |
| `analyzable_reads` | Sum `A.counts_total[ref]` over actual references once; excludes Core ambiguous and discarded reads; only meaningful after copy-routing qualification |
| `wt_reference_reads` | `A.counts_total[WT]`; includes reads with mutations closer to WT; **not exact WT** |
| `exact_wt_reads` | Allele counts exactly matching full WT sequence with complete coverage and no unresolved bases |
| `pe_reference_reads` | `A.counts_total['Prime-edited']`; every accepted PE-assigned read, with or without additional changes |
| `precise_pe_reads` | PE-assigned allele counts whose full ungapped sequence equals the verified intended PE, with full reference coverage and no extra sequence, gaps relative to PE, or ambiguous bases |
| `pe_with_additional_mutations_reads` | PE-assigned, fully assessable alleles demonstrably differing from PE; retain incomplete/unassessable alleles separately, not as proven extra mutations |
| `pe_window_unmodified_reads` | `A.counts_unmodified['Prime-edited']` or PE row `Unmodified`; optional secondary metric, can include mutations outside the window |
| `indel_containing_reads` | Count each assessable allele once if detailed `all_insertion_positions` or `all_deletion_positions` is nonempty relative to its assigned reference; document that intended PE indels are represented in PE and are not extra indels |
| `scaffold_reads` | `A.counts_total['Scaffold-incorporated']`; backend motif-classification count; null/not-assayed when no scaffold configured, not zero |
| `within_copy_ambiguous_reads` | `A.class_counts.get('AMBIGUOUS', 0)` only after validating the complete file/schema; allele `Reference_Name` starts `AMBIGUOUS_`, even if its `Read_Status` says `UNMODIFIED`/`MODIFIED` |
| `discarded_reads` | Sum `A.counts_discarded`; detailed table uses `DISCARDED_` prefix; default pipeline does not request indel discarding |
| `ambiguous_copy_reads` | Separate routing audit ledger, **not** Core `AMBIGUOUS`; default Pooled does not expose a trustworthy count; null + `not_measured` until qualified |
| `other_or_unassessable_reads` | Explicit residual categories in the validated allele partition; never silently subtract unrelated overlapping metrics |

`Read_Status`, `n_deleted`, `n_inserted`, `n_mutated` are quantification-window
relative. None alone proves full-amplicon precision. Extra-mutation counts must
inspect complete allele alignment/coverage. Avoid a simplistic equality on a
cropped plot table. An intended deletion must not count as an unintended deletion
just because it differs from WT. If a WT-relative indel metric is later needed,
give it a separate name and test against intended insertion/deletion fixtures.

Treat reference assignment as a partition (WT / PE / scaffold / ambiguous /
discarded); exactness and indel flags further describe that partition and can
overlap. Scaffold is not added to PE-assigned counts in the primary metric.
Within-copy ambiguity is excluded from the denominator by explicit design;
report its count/fraction because this exclusion can bias efficiency estimates.

With ambiguity expansion/first-reference assignment disabled, verify:

```text
Core READS ALIGNED = sum(counts_total) + sum(counts_discarded) + class_counts[AMBIGUOUS]
Core READS ALIGNED = sum(allele #Reads, including ambiguous/discarded, each once)
For each reference: counts_total = counts_unmodified + counts_modified
```

Reconcile input pairs, preprocessing/merge losses, routed reads, low-depth skips,
failed subruns, Core unaligned reads and accepted counts separately. Do not equate
raw mate count with merged sequence count. No missing run, missing reference,
unmeasured ambiguity or zero denominator becomes a numerical zero by default.

## Aggregation, design and provenance (future)

Store long-form counts, status, denominators and metric-definition version per
sample × target × copy; a wide sample table is only a derived presentation.
Use percentages in [0,100] for fields ending `_percent`; underlying fractions are
in [0,1]:

```text
copy_PE_percent = 100 * precise_pe_reads / analyzable_reads
target_read_weighted_percent = 100 * sum(precise_pe_reads) / sum(analyzable_reads)
target_equal_copy_mean_percent = mean(copy_PE_percent)
copy_read_fraction = analyzable_reads_copy / sum(analyzable_reads_for_target)
```

Zero coverage produces null. Missing/failed/low-depth copies must not disappear
silently from equal-copy means: return incomplete status and expected/observed
copy counts, and withhold the primary complete-target summary. Any partial
summary must be labeled separately. Copy fractions, between-replicate balance
changes, routing ambiguity and weak diagnostic variants produce QC warnings.

Reads are observations for count likelihoods, **never biological replicates**.
Biological n comes from samples/blocks and independent units confirmed by the
experimenter. Simple mode will require explicit contrasts and paired/unpaired
design. Factorial mode will consider counts such as
`cbind(precise_pe_reads, analyzable_reads - precise_pe_reads)` with beta-binomial
overdispersion and confirmed block effects, e.g. editor × treatment plus a block
random intercept. Do not infer a causal model from labels alone. Incomplete
blocks, technical replication, pseudoreplication, few blocks and zero coverage
require checks before fitting. Report model, biological n, estimates, confidence
intervals, raw p-values and defined multiplicity adjustments.

Planned deterministic outputs:

```text
results/
  manifest.json, resolved_config.yaml, inputs/       metadata snapshots and hashes
  01_demux_QC/                                     counts, matrix, heatmap, JSON
  02_demultiplexed_fastq/<barcode_id>_{R1,R2}.fastq.gz
  analysis/03_analysis_fastq/                      separate trimmed copies, manifest
  backend/                                        TSV, argv, logs, external diagnostic output
  05_routing_QC/                                  synthetic truth/routing comparison
  future_quantification/                          not implemented
  future_statistics/                              not implemented
  future_report/                                  not implemented
```

Each stage manifest will contain input content hashes, normalized configuration,
metadata snapshots, schema/metric versions, pipeline version and exact Git commit
(plus dirty state), backend/tool versions or container digest, exact argv and
working directory, UTC timestamps, exit status, expected outputs and counts.
Use atomic completion markers after output validation. Resume only when hashes,
versions and validated outputs agree; `--force` invalidates dependent stages.
The presence of a directory or CRISPResso's own no-rerun option is insufficient.

## Assumptions requiring biological confirmation

1. The Qi-Lab/Azenta layout above is user-verified for the inspected run; confirm
   layout for other protocols and whether explicitly requested trimming removes
   only library sequence. Exact matching is the verified default. Unexpected
   combinations suggest possible recombination but do not prove its mechanism.
2. Amplicon boundaries/strand, genotype-specific WT references and copy number;
   primer specificity, off-target amplification and paralogs outside the reference
   panel. Shared references cannot support copy-level estimates.
3. Complete intended PE haplotypes (including silent changes), spacer/PAM omission,
   extension order/PBS, nicking guide and actual scaffold sequence per construct.
4. Whether diagnostic variants survive editing and lie inside reliably sequenced
   regions; PCR chimeras, alignment bias and sequencing errors can mimic copies.
5. Whether the primary metric should require identity over the full amplicon or
   a biologically defined edit window. This design proposes full-amplicon identity;
   it will penalize sequencing errors and unrelated polymorphisms. The denominator
   exclusion of ambiguous/discarded reads also needs confirmation.
6. Read-weighted editing reflects sequencing abundance, not necessarily cellular
   editing or genomic dosage. Equal-copy means and read-weighted estimates answer
   different questions. No automatic ploidy/dosage correction is assumed.
7. Biological independence, pairing/block IDs, technical replicate structure,
   factor contrasts, interpretation of dpi, minimal biological n and low-depth/
   copy-balance thresholds. No statistical inference is available in this milestone.

Known limitations: metadata/demux success is not backend readiness. The synthetic
routing audit demonstrates forced ambiguous assignments and the guide mismatch
limitation in 2.3.4. No generalized copy-variant report, production PE parser,
statistical model or final report exists. Partial read coverage may prevent full-amplicon precision.
Scaffold detection is motif-based and depends on backend orientation/search rules;
absence of a count is not proof of absence. Default Pooled cannot supply the
required reliable cross-copy ambiguous count. Backend contracts are pinned and
must be retested before upgrading.

## Tests and next milestones

The pytest suite exercises malformed CSV/YAML, normalization, identifiers,
variable barcodes, duplicate pairs/references, backend-specific reference limits,
typed optional parameters, reference collisions, paired/block requirements,
configuration errors, installed CLI success/failure and example metadata.
Milestone 2 additionally tests streaming FASTQ structure/pair errors, all six
terminal categories, exact and Hamming ties, raw output preservation, gzip/LRU
handling, bridge diagnostics, custom extraction, matrix/heatmap contents and
mandatory reconciliation/failure cleanup. Normal unit tests require no
CRISPResso or network. M3 real-backend tests use `crispresso_integration` and
explicit `M3_INTEGRATION=1` opt-in; see the M3 document for runtime requirements.

M3 is implemented as a validation gate, with distinct immutable demux and trimmed
analysis inputs. Actual execution confirms 310/310 informative routes, zero
cross-routes and 40/40 forced non-informative assignments. Its scientific gate
failed; diagnostic regression tests passing do not authorize production routing.
The faithful shared-guide mismatch test also fails in the backend and is now
represented in preflight. M2 remains independently usable without CRISPResso.

**Next: routing follow-up before M4**, including an explicit ambiguous-read
quarantine strategy and reviewed guide-mismatch handling. Further fixtures for
edited-away diagnostic SNPs, repeats, scaffold, threshold boundaries and amplicon
order should qualify the eventual routing design, not broaden this failed gate
into downstream implementation. After qualification, M4 parses outputs and
validates metrics; 5 aggregates copies;
6 implements biological statistics; 7 reports; 8 provides a complete synthetic
end-to-end reproducibility test. Keep unit and `integration` tests separate.
