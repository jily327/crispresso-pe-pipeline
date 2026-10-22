# M4 production PE measurements

M4 adds a Python API and schema for measurements of one target in one verified
prepared sample. It adds no statistical tests, biological interpretation,
aggregation, plots, GUI or report generation. The audited base is
`550df70f9f9627c7218b9f047d0b6bf3023b8d25`. M2 behavior and M3.1.2 routing,
geometry, observed-flank rules and comparator primitives are unchanged.

## Population and denominator contracts

**Target metrics use all eligible prepared target pairs, including quarantine.**
**Copy metrics use only the verified confidently routed copy cohort.** These are
different populations, encoded in each record's `population_scope`,
`population_id`, `population_input_reads`, `copy_id` and `routing_conditioned`.
Population IDs hash prepared identity, sample and target definitions; copy IDs
add routing manifest identity and copy name. They are not based on equal counts.

| Metric name | Population | Numerator | Denominator / assessment |
|---|---|---|---|
| `target_crispresso_native_pe` | All prepared target pairs | Authoritative Core `counts_total['Prime-edited']` | Mapping `READS ALIGNED`, reconciled with quantification and JSON counters; every copy anchor must agree |
| `total_precise_pe` | All prepared target pairs | Exact full intended PE of any valid copy | Exact full WT + exact full PE from the original synchronized mates; copy identity is unnecessary |
| `<copy>_crispresso_native_pe` | Confident cohort for that copy | Same authoritative Core numerator | Authoritative aligned reads for that cohort |
| `<copy>_precise_pe` | Same confident cohort | Full intended PE haplotype in accepted backend alleles | Full exact WT + full exact PE in that aligned cohort |

Every denominator depends on its applicable stages: routing qualification and
quarantine for copy admission, backend preprocessing/alignment for backend-based
metrics, and the metric's own product/assessability definition. **No single stage
defines the final denominator for all metrics.** The target precise metric uses
original prepared mates directly. Its backend counters describe the parallel
all-read native analysis and do not filter its denominator. This distinction is
explicit in `assessment_stage` and `backend_counts_role`.

Native and precise PE differ in both numerator and denominator. Exact PE is not
a conservative lower bound: either fraction can be larger. The difference alone
does not indicate better or worse editing quality. Likewise target native 30/105
and combined confident native 30/70 are population differences, not simply two
metric definitions. M4 does not emit an aggregate copy fraction as a target metric.

## Entry points

```python
from pathlib import Path
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.metrics import run_metrics, collect_metrics, MetricResult
from peanalyzer.metrics.production import RUNTIME_DIGEST

# targets: complete list[Target] for exactly one biological target, preserving
# the actual shared experimental spacer, extension, nick and scaffold.
result = run_metrics(
    analysis_root=Path("prepared"), sample_id="1B", targets=targets,
    analysis_id="run1-sample1-target1", output=Path("m4-run1"),
    routing_root=Path("qualified-routing"),
    core=resolve_executable("CRISPResso"), runtime_digest=RUNTIME_DIGEST,
)
print(result.model_dump_json(indent=2))
```

The caller must identify the complete eligible prepared population for this
target. The API does not select one target from a mixed-target FASTQ or infer
sample/target applicability. Input archives must stay immutable while verified.
`routing_root=None` is permitted: target metrics remain independently eligible,
but copy metrics are explicitly BLOCKED. Routing is not rerun or guessed by M4.

`run_metrics` executes the existing conventional unrouted Core comparator for
every required anchor, preserving the actual guide/configuration, and invokes
the existing verified confident-Core handoff for eligible copies. It keeps
backend artifacts and failures, then publishes `result.json` only after model
validation. Output must be new; overwrite/resume are not implemented.

`collect_metrics` accepts the same input identities plus `comparator_root` and
`copy_roots={copy_name: execution_root}` for existing executions. It re-verifies
prepared inputs and routing (policy, geometry, ledger semantics, cohort
inventory, hashes, synchronized byte preservation, original input lineage).
It checks execution completion, runtime identity, exact argv, submitted FASTQ
hashes, target reference sequences and execution-to-input manifest identity.
It re-parses named child artifacts, **not cached `metrics.json` or a caller's
count dictionary**. Missing evidence blocks the relevant result.

Runtime digest is declared execution provenance, not remote attestation of a
container or executable. Deployment must actually use the pinned image. The
qualification evidence records local image inspection and actual version probes.
An arbitrary external executable is not certified by supplying a digest string.

## Backend acceptance and reportability

The five authoritative `running_info.alignment_stats` counters reconcile:

```text
aligned = N_CACHED_ALN + N_COMPUTED_ALN
unaligned = N_CACHED_NOTALN + N_COMPUTED_NOTALN
N_TOT_READS = aligned + unaligned = mapping READS AFTER PREPROCESSING
mapping READS ALIGNED = aligned = native denominator
mapping READS IN INPUTS = verified submitted pairs
```

All required anchors must empirically agree on input, aligned, unaligned,
native numerator and native denominator. There is no averaging or best-anchor
selection. Native results also require the normalized authoritative
`Reference.include_idxs`: missing, malformed or **empty** windows BLOCK.
Target comparator diagnostics inside that authoritative window also BLOCK.
Both qualified list and exact ndarray encodings are preserved; the old parser
is unchanged. A copy native empty-window failure does not reinterpret an
otherwise assessable full-product exact sequence as an efficiency of zero.

The existing comparator explicitly contracts record-preserving preprocessing;
copy Core requires exact routed/backend input equality without silently assuming
all future preprocessing preserves that count. Every metric carries integer
`backend_input_reads`, `reads_after_preprocessing`, `aligned_reads`,
`unaligned_reads`, `preprocessing_count_delta` and unaligned reason counts when
that backend population is available. Unavailable backend counts are null, never
invented zeros. Target exact can remain reportable when native is blocked; in
that case backend counters may be unavailable and the role is labelled accordingly.
Unaligned causes default to `unknown_backend_alignment_failure`.

States are `REPORTABLE`, `BLOCKED`, `NOT_ASSESSABLE`. Reportable PE fractions have
integer numerator and positive denominator. Non-reportable fractions have null
numerator/denominator and nonempty machine-readable reasons. Zero exact WT+PE
is `NOT_ASSESSABLE` / `ZERO_EXACT_DENOMINATOR`, not 0%. Zero aligned native reads
similarly cannot yield 0%. Raw QC counts remain available when verified.

The executable strict schema is `MetricResult.model_json_schema()`, also shipped
as `peanalyzer/metrics/result.schema.json`. It forbids unknown fields and float
counts. Pydantic model validators additionally enforce arithmetic and population
relationships that JSON Schema alone cannot express. Top-level fields are:
`schema_version=1`, `metric_contract_version=m4-v1`, target/sample/analysis IDs,
`provenance`, `eligibility`, `target_metrics`, `copies`, `qc`, `anchor_evidence`.
There are no convenience floating-point efficiencies in production metric records.
QC fractions contain integer numerator/denominator; a zero QC denominator means
undefined, never an interpreted zero fraction. Backend diagnostic evidence may
retain the older parser's derived convenience fields.

## Exact products and exclusions

The target exact classifier reuses the qualified inward-facing amplicon-end
primitive. Each mate must match its product end, the mates together must cover
the complete product, and all covered sequence must agree. Internal fragments,
uncovered gaps, disagreements, partial PE, PE with extra mutations and other
non-exact products cannot become exact PE. Same-state identical definitions
collapse safely and every input pair is counted at most once. A WT/PE definition
collision or pair that satisfies contradictory WT/PE states BLOCKS reporting.

Copy exact uses reconciled full backend allele sequences. It exposes
`exact_wt`, `exact_pe`, `pe_plus_extra_change`, `other_nonexact_assessable`,
`unresolved_unassessable`, `contradictory_state`, `classification_input_reads`
and `denominator_exclusions`. PE-plus-extra is called only where a complete
substitution design and observed product establish all intended changed bases
plus an additional change. Indel products without that evidence stay in a
broader observable class. No WT-derived/PE-derived origins are assigned.

Aligned-product exclusions are distinct from
`population_denominator_exclusions`, which also includes backend attrition for
copy exact. Preprocessing count expansion would make a simple input-minus-
denominator exclusion undefined (null), rather than fabricate a negative count.
Target exact classifications use prepared pairs, so all its exclusions are
relative to that complete population. Synthetic origin attribution remains in
historical qualification evidence, not production biological results.

## Scientific limits carried forward

The 36-design indel grid remains **13 allowed, 23 BLOCKED**. Unsupported geometry,
stale policy, unverifiable handoff and missing cohorts cannot produce copy
efficiency. Exactly one actual experimental spacer remains shared across copies;
no guide is invented or rewritten to satisfy the backend.

**Insertion limitation:** an inserted PE segment can extend the edit-coverage
footprint compared with the corresponding positional WT molecule. Observed-flank
requirements can therefore quarantine some PE-bearing fragments without an
equivalent WT quarantine. The confident copy cohort may be PE-depleted. M4
exposes confident size, quarantine counts/reasons and the routing-conditioned
label, and applies no mathematical correction. Eligible target all-read metrics
are the primary population-level view.

Reference completeness, PCR specificity, coincident errors, unobservable template
switches and unseen panels/products remain biological/technical limitations.
The existing verifier's memory use and coordinated rewriting of all trusted
artifacts remain outside qualification. Nothing here establishes experimental
editing quality or statistical significance.

See [M4 validation and reproduction](validation/m4/README.md) for the review,
exact regression counts, negative gates, real-backend artifacts and test results.
