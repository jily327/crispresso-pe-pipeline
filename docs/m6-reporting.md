# M6 deterministic reporting

M6 (package 0.6.0, report contract `m6-v1`) renders a completed M5
`StatisticsResult` (`schema_version=1`, `statistics_contract_version=m5-v1`).
The exact copied M5 JSON remains the scientific authority. M6 sorts, formats,
labels and renders existing values; it performs no biological inference.

```sh
peanalyzer report --result completed-m5/result.json --output new-report \
  --title "Synthetic study"
```

The optional title defaults to `Prime-editing amplicon analysis report`.
The reusable Python API is
`peanalyzer.reporting.generate_report(result_path=..., output=..., title=...)`;
it returns a strict `ReportManifest`. `build_report_spec(result, title)` is a
pure presentation specification, shared by HTML, SVG and table renderers.
Neither function calls aggregation, permutation enumeration or BH correction.
Summarize-only M5 inputs with empty contrasts/families are supported.

## Output contract

```text
new-report/
  report.html
  report_manifest.json
  source/result.json
  tables/observations.tsv
  tables/group_summaries.tsv
  tables/contrasts.tsv
  figures/series-<sha256>-samples.svg
  figures/family-<sha256>-contrasts.svg
```

The manifest contains version, title, package version, raw source SHA-256 and a
sorted inventory of every non-manifest file, with path, hash, media type and
artifact kind. Figure entries identify their full series, including the exact normalized policy
definition, or their explicit BH family.
Opaque IDs hash canonical structured identity, using the full SHA-256 digest.
No lossy filename sanitization is used. The packaged
`reporting_resources/report_manifest.schema.json` describes the strict model;
Pydantic/runtime checks additionally enforce artifact inventory and hash links.

The source is read once for strict parsing, hashing and exact byte copying.
Duplicate JSON keys, nonfinite numbers, malformed JSON, unknown model fields
and unsupported contracts fail. The source is checked again before publication;
a changed source aborts. Publication uses a new output only, exclusive sibling
`.NAME.m6-lock`, sibling temporary directory and final rename. Exceptions clean
staging/lock state. A hard process kill can leave visibly incomplete sibling
state; it does not create a completed report. Existing directories and symlinks
are rejected. The lock coordinates cooperating publishers.

## Figure semantics

Each analytical series preserves target, exact metric name, population scope,
routing condition, copy, policy ID and normalized policy definition. Conditions
are ordered by structured `(editor, treatment, dpi)`, and all three appear in
labels. Display labels never serve as scientific identity.

One sample figure is exported for each series containing a reportable
observation. Each equally sized point represents one biological sample and uses
`Observation.fraction` directly. Samples are sorted deterministically and spread
symmetrically over a fixed width of 0.36 condition units; a singleton is centered.
The black summary marker reads
`GroupSummary.mean_biological_sample_fraction` directly. No mean is recomputed.
The y-axis always spans 0–1. Color uses a fixed accessible palette assigned by
sorted structured condition identity, with position and labels providing
additional identification. Colors repeat for more than seven conditions.

Copy measurements are explicitly routing-conditioned and are not whole-target
fractions. Native, precise, target, copy and family-policy series are kept
separate. `POOLED READ-WEIGHTED DESCRIPTIVE FRACTION` appears only as a descriptive
table field, never as an inferential estimate or sample mean.

`BLOCKED`, `NOT_ASSESSABLE` and `MISSING_METRIC` are nonnumerical. They have no
zero placeholder. Every group retains expected/reportable/blocked/not-assessable/
missing counts and sample assessments with reasons. A series with no reportable
observations retains its section and tables, with explicit omission text.

Contrast figures are grouped by the explicit M5 `family_id`. Each reportable
contrast uses the stored `difference_in_biological_sample_fraction`, with x-axis
−1 to +1 and a zero reference line. Direction is **B − A**: positive values mean
larger fractions in B. Captions include both condition definitions and stored
p/q. These are the exact M5 p-values and family-scoped Benjamini-Hochberg q-values;
M6 does not recompute, threshold or interpret them. No confidence intervals or
significance calls are added. Nonreportable contrasts stay in tables with their
reasons and expected/used sample inventories. Paired contrasts retain pairing
mode, complete block IDs/count-by-inventory and excluded blocks/reasons. A family
with no reportable effects has no numeric figure; unused declared families are
retained without reinterpretation.

## Tables, HTML and safety

All fields of M5 `Observation`, `GroupSummary` and `ContrastResult` are exported
in stable model column order. Nested structures use sorted deterministic JSON,
null scalar cells are empty, and raw numerator/denominator/fraction/effect/p/q
values retain their source numeric precision. Presentation percentages use two
decimal places; rounding never feeds back into scientific values or plots.
Inventory lists are sorted for presentation without modifying the copied source.
Policy-definition arrays retain their exact order as part of series identity.

HTML has inline CSS and the complete exported SVG contents. It needs no
JavaScript, CDN, external fonts, stylesheet, image host or network. Semantic
headings, tables with captions/header/body, figures/captions and SVG accessible
labels support navigation. Wide detailed tables scroll horizontally.

All HTML input text is escaped. Matplotlib renders literal XML text, with TeX
and mathematical parsing disabled. Default packaged DejaVu Sans is used, and
figures are closed after rendering, including failures. Missing glyph support
for some Unicode scripts remains a default-font limitation; original labels
remain available in HTML/tables/source.

Absolute source paths are excluded from HTML, manifest and figures. The
observations TSV preserves the required original `source_result` value; the
exact source JSON also preserves its original provenance. Those downloadable
files can therefore contain source machine paths. HTML displays a neutral
reference to the copied source instead of original paths, and creates only
relative links to its own source/tables. No CRISPResso report link is guessed:
`m5-v1` supplies no portable verified backend report artifact contract.

## Determinism and limits

Rendering resets Matplotlib defaults, uses a headless Agg backend, fixed SVG
hash salt per figure, literal SVG text and no date metadata. Identical input
bytes, title, version and rendering environment produce byte-identical reports,
including manifests. The qualification compares the same committed fixture
path/bytes between source and fresh installed wheel. Cross-platform font or
Matplotlib changes are not claimed to be byte-identical.

Reordering valid input arrays preserves the presentation spec, tables and SVGs.
The exact source copy and raw source hash necessarily differ; HTML changes only
its visible source hash. Manifest source/HTML hashes change accordingly. The
original source bytes are intentionally never normalized for copying.

M6 adds no automatic biological interpretation, confidence intervals, GLMMs,
workflow DAG, resume or force behavior. Small-n exact p-values may be coarse.
M4 observability and read-geometry limits remain upstream. M5 invalid-policy
identity collisions, supplied q-value validation and unused family declarations
remain M5 behavior. M4.2.3 and M7 are outside this milestone.

See [qualification evidence and reproduction](validation/m6/README.md).
