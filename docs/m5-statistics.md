# M5 biological aggregation and exact statistical contrasts

M5.1 (package 0.5.1, `statistics_contract_version: m5-v1`, schema version 1)
consumes completed M4 JSON measurements offline. The inferential unit is the
biological **sample**, identified by `sample_name`. Reads are measurements
within that sample; reads are never independent biological replicates.

## Inputs and exact identities

Supply a UTF-8 CSV manifest with exactly one column:

```csv
result_json
measurements/sample-a-target1/result.json
measurements/sample-b-target1/result.json
```

Paths resolve relative to the manifest directory (absolute paths also work).
Resolved duplicate paths, including aliases, are errors. There is no directory
scan. Two documents claiming the same biological sample and target are an error,
even with identical counts or different analysis IDs. No newest/largest analysis
is chosen. Resolve duplicates upstream.

Supply the full biological `samples.csv` accepted by the existing `Sample`
model: `sample_name`, `barcode_id`, barcode sequences or catalog IDs, `editor`,
`treatment`, integer `dpi`, `biological_replicate`, nullable `block_id`, and
`paired` (`true`/`false`). M4's prepared-sample `sample_id` is joined **exactly to
`barcode_id`**. There is no sample-name fallback, barcode guessing or case
folding. Sample names and barcode IDs must each be unique. M5 validates the full
typed metadata but does not resolve barcode catalogs or rerun demultiplexing;
barcode sequence/pair qualification remains upstream. A metadata sample with
zero M4 result documents across all targets is listed in
`unused_metadata_sample_ids` and never creates an observation. Within each
condition and target, duplicate biological-replicate identifiers are rejected.
Technical replicates are not automatically merged.

Every JSON document passes the authoritative M4 `MetricResult` model and its
arithmetic validators. M5 accepts schema 1 / `m4-v1`, rejects absent/unknown
versions, duplicate JSON keys and nonfinite JSON values, and checks the stored
sample/target/copy population hashes against M4 provenance. Product-evidence and
family-population links must match; stored target definitions, when present,
must agree with their hash and target/copy inventory. A target name cannot refer
to conflicting definitions across samples. These are identity checks, not new
sequence interpretation. No M4 result, count, eligibility, evidence or reason is
rewritten. Trusted, immutable M4 archives are required; coordinated forgery of
all provenance is outside the contract.

## Complete sample × target coverage

A participating sample is a metadata sample whose authoritative `barcode_id`
appears as `sample_id` in at least one validated M4 result in the manifest.
The observed target universe is the union of target IDs in all validated results.
Every participating sample must have **exactly one M4 result for every observed
target**. Duplicates remain errors; missing whole sample × target documents
raise `AggregationError` with `PARTIAL_SAMPLE_TARGET_COVERAGE`, the barcode ID
and deterministically ordered missing targets, before summaries, contrasts or
completed outputs are produced. No sample or first manifest row defines the
reference target set. A target found in only one sample still belongs to the
run-wide target universe.

Metadata samples with zero results remain unused and do not trigger this check.
An existing result with a BLOCKED/NOT_ASSESSABLE metric still covers its sample
and target. A missing optional metric within that result remains `MISSING_METRIC`
with `METRIC_NOT_PRESENT`. Selective sample-target applicability needs a future
explicit design contract and is not inferred here. M5.1 adds no status or schema
version and does not change statistical calculations on complete inputs.

## Observations and summaries

`result.json` is authoritative. `observations.tsv`, `group_summaries.tsv` and
`contrasts.tsv` are derived conveniences; nested values are JSON cells, null
scalar values are empty cells. All four files are published through a private
sibling staging directory followed by rename. Existing outputs are rejected.
Failures clean this invocation's stage; a hard kill can leave a visibly
incomplete stage/lock requiring operator cleanup.

Each observation retains the full biological identity, structured condition
fields (`editor`, `treatment`, `dpi`), target, metric name, population scope and
ID, nullable copy, routing flag, original status, numerator, denominator, reasons,
analysis ID, M4 contract and source result. Source-result paths are normalized
relative to the manifest directory. The floating `fraction` is derived from
integer counts at full precision; it never replaces those counts.

Target native, target precise, confident-copy native, confident-copy precise,
and each target/copy family policy form separate analytical series. Copy metrics
remain routing-conditioned populations. Policy IDs have one exact normalized
definition throughout an M5 invocation. Different definitions under one ID or
duplicate series in a document are errors. Valid policy position lists are
normalized by M4's `FamilyPolicy`; invalid nonreportable policy requests retain
their diagnostic definition and status. No family measurements are recalculated.

Conditions are structured objects, never concatenated strings. Replicate and
block IDs do not belong to condition identity. For every condition, target and
metric/copy/policy series, summaries contain:

- Expected sample IDs/count, reportable/blocked/not-assessable/missing-metric
  counts and a per-sample status/reason inventory.
- Reportable sample IDs, source integer numerators/denominators and fractions.
- Unweighted biological-sample mean, median, minimum and maximum.
- `pooled_read_fraction = sum(numerator) / sum(denominator)`, labelled
  **POOLED READ-WEIGHTED DESCRIPTIVE FRACTION**.

For `1/10` and `90/100`, the biological mean and median are `0.5`; the pooled
fraction is `91/110`. The pooled fraction is descriptive only and never enters
hypothesis testing. Blocked/not-assessable values remain null, never zero.
If a sample has a target result but lacks an optional policy metric, its summary
assessment is `MISSING_METRIC` with `METRIC_NOT_PRESENT`; no observation is
fabricated. Expected counts concern participating samples in the relevant
condition, each of which must have a result for every target represented in the
run. Metadata samples with zero results remain outside those inventories.

## Explicit contrast specification

`stats` requires YAML (JSON is also valid YAML) matching the bundled contrast
schema. Duplicate YAML keys, contrast IDs and family declarations are rejected.
Unknown fields, conditions, populations, policies or design values are errors.
Both conditions must have a nonempty observed target group. An example:

```yaml
schema_version: 1
families: [primary]
contrasts:
  - contrast_id: target-precise
    family_id: primary
    target_name: T1
    metric_name: total_precise_pe
    copy_name: null
    policy_id: null
    group_a: {editor: synthetic-editor, treatment: A, dpi: 6}
    group_b: {editor: synthetic-editor, treatment: B, dpi: 6}
    pairing_mode: unpaired
    alternative: two-sided
```

For a copy specify both its metric name (for example `copy1_precise_pe`) and
`copy_name: copy1`. For a target family specify `total_pe_family` and its exact
`policy_id`; for a copy family specify `copy1_pe_family`, copy and policy.
There are no implicit design or multiple-testing defaults.

## Exact tests and missing observations

Unpaired tests require at least **two reportable biological samples per group**.
The effect is mean(B fractions) minus mean(A fractions), without read weighting.
Every allocation of sample labels preserving the two group sizes is enumerated:
`choose(nA + nB, nA)` assignments. The two-sided tail includes assignments with
`abs(T_permuted) >= abs(T_observed)`, including the observed assignment. Tail
comparisons use exact integer ratios via `fractions.Fraction`. No zero-p
correction, t-test substitution or stochastic approximation is used.

Unpaired contrasts are blocked if any expected row is marked paired, or if
non-null block IDs repeat among participating samples. M5 does not silently
ignore a supplied paired/repeated-block design.

Block contrasts require `paired=true` and an explicit non-null `block_id` on
all expected rows. Each block/group may have at most one observation, including
nonreportable observations. A duplicate in either group blocks the contrast.
A usable block contains exactly one reportable A and one reportable B.
Pairing never comes from replicate number, barcode, sample naming or ordering.
At least **two complete blocks** are required. The effect is the mean within-
block B-minus-A fraction. Every one of `2^blocks` sign patterns is enumerated
with the same exact two-sided tail rule.

Expected and selected sample inventories/counts, complete blocks and excluded
blocks/reasons are explicit. A missing partner, nonreportable observation or
missing metric excludes that block. Inference can proceed on the remaining
complete blocks if the minimum is met. A design error produces `BLOCKED`;
insufficient units or an oversized enumeration produces `NOT_ASSESSABLE`.
Nonreportable contrasts have null effect, p, q, executed permutation count and
extreme count. Their selected sample inventories can still describe eligible
candidates, even when a minimum/cap prevents execution; expected inventories
always include exclusions.

The hard limit is **100,000 assignments per contrast**, computed before
iteration. `--max-permutations` may lower it (integer 1–100000), never raise it.
An excess yields `PERMUTATION_SPACE_TOO_LARGE`; no Monte Carlo fallback exists.
For three paired blocks, 8 configurations give a minimum nonzero two-sided p of
`2/8 = 0.25`. Three versus three unpaired samples give 20 assignments and a
minimum `2/20 = 0.1`. Coarse resolution is retained. The sole effect field is
`difference_in_biological_sample_fraction`; no causal/efficacy label or invented
confidence interval is provided.

## Multiple testing, provenance and reproducibility

BH correction uses only reportable p-values inside each explicitly declared
`family_id`. Invalid contrasts have no artificial p-value and do not enter `m`.
Declared families with no valid tests retain `m=0`. The implementation orders
p-values deterministically, applies the reverse cumulative minimum of `m*p/rank`,
and retains raw p, adjusted q and valid-test count. Choosing a family is the
analyst's responsibility; M5 never guesses it from targets, files or experiments.

Provenance includes package/contract, input result hashes, manifest/metadata/spec
hashes, source M4 contracts, paths, invocation parameters and Python/platform.
The file API hashes exact specification bytes. The typed `calculate_contrasts`
API hashes its normalized specification and clears any previous specification
path/hash; the hash basis is explicit in invocation parameters.
Raw file hashes deliberately change when row/JSON-key order changes. Scientific
observations, summaries and contrasts use canonical ordering and remain equal
under such reorderings; byte identity is claimed only for the same inputs and
provenance. Source/wheel qualification compares scientific content separately
from environment/path provenance.

```bash
peanalyzer summarize --manifest metrics_manifest.csv --samples samples.csv --output summary
peanalyzer stats --manifest metrics_manifest.csv --samples samples.csv \
  --contrasts contrasts.yaml --output statistics
```

Python APIs are `peanalyzer.aggregation.summarize` and
`peanalyzer.statistics.stats`, with keyword paths corresponding to the commands
and optional `output`. `collect_observations`, `calculate_contrasts`,
`exact_unpaired`, `exact_paired`, and `benjamini_hochberg` are reusable functions.
Low-level enumerators reject insufficient/oversized calls; `stats` converts those
scientific cases to typed statuses. The strict models are in
`peanalyzer.statistical_models`; packaged schemas are
`statistics_resources/result.schema.json` and `contrasts.schema.json`.

M5 adds no statistical dependency. It does not need FASTQ, Core or Pooled.
It does not implement reports, plots, confidence intervals, model-based count
inference, arbitrary formulas or automatic biological interpretation. Label
exchangeability for unpaired inference and sign symmetry for paired inference
remain scientific design assumptions. M4's existing observability/read-geometry
limitations remain upstream and unchanged; M4.2.3 is not implemented here.
See [M5 qualification](validation/m5/README.md) and
[M5.1 coverage validation](validation/m51/README.md).
