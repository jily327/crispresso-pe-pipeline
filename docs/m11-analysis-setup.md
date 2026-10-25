# M11A — Analysis Setup and Review

M11A validates and previews analyses but does not execute them.

The application now offers **New Analysis** and **Open Existing Analysis**.
The latter retains the M10/M10.1 verified snapshot viewer. New Analysis has five
steps: Samples & Sequencing, Analysis Mode, Target, Configuration, and Review.

## Launch and input capabilities

Install the GUI extra and launch locally:

```sh
peanalyzer-viewer \
  --workspace /data/completed-study \
  --setup-fastq /data/pool_R1.fastq.gz \
  --setup-fastq /data/pool_R2.fastq.gz \
  --setup-output-root /data/proposed-analyses
```

All registrations are optional and repeatable. `--setup-demux PATH` registers an
existing M2 archive instead of a raw pool. Open the printed loopback URL with its
session fragment. Node and CRISPResso are not required at viewer/setup runtime.
No arbitrary browser-supplied filesystem path is accepted. The browser receives
opaque IDs and short display labels. Registration and use reject symlinks,
traversal and incorrect file types. Existing Host, Origin and token checks apply
to every new API route. Files remain on the local machine.

The backend currently consumes **one raw paired-end pool plus a barcode sample
sheet**, or a verified M2 archive. Sample rows do not select independent FASTQ
pairs. Single-end, interleaved and multi-lane inputs are not exposed. The launcher
must register all desired inputs before opening the wizard; browser upload and a
native filesystem chooser are outside this milestone.

Sample metadata uses the existing schema: sample name, stable barcode/sample ID,
forward/reverse barcode sequences, editor, treatment, dpi, biological replicate,
and paired/block metadata. Rows can be added, edited, removed, filtered and sorted
for presentation. No biological metadata is inferred. For QI-HITOM, barcode
sequences must match the bundled authoritative catalog. Custom barcodes are at
the read start, with no bridge. Other custom layouts need a future bounded UI.

## Draft lifecycle and integrity

Drafts exist only in the local adapter's memory, separately from scientific
workspaces. Restarting the server loses drafts. Switching to the existing viewer
and back preserves the active browser draft. Reloading the browser creates a new
draft; there is no draft library/persistence UI. Discard removes the server draft.

Each full-content PATCH requires the current revision and increments it. A patch
immediately clears stored validation and preview. Validation carries a revision
and canonical draft digest. Frontend edits immediately clear downstream display;
generation guards reject stale save, validation and preview responses. The client
retains the accepted server revision when local edits supersede a pending save.
Only one save/validate transaction is in flight per wizard.

Before and after validation, raw file bytes or the complete archive inventory
are hashed. Preview access rechecks input identity and destination conflicts;
changed inputs clear validation. A cached validation is a snapshot, not a promise
that external files cannot change. Future execution must independently revalidate
all inputs and resolved runtime arguments.

## Scientific ownership

Python reuses `Sample`, `Target`, `NucleaseTarget`, the actual CSV loaders and
cross-row checks, catalog/extraction validation, paired FASTQ parsing, demux
verification, preparation configuration, reference geometry and the existing
workflow DAG. In-memory CSV adapters do not create metadata files.

PE supports one target with one or more copy definitions: WT and intended edited
amplicons, spacer, extension, optional nicking guide and scaffold. The existing
shared experimental guide/extension constraint is enforced. Backend-returned
annotations include differences, edit regions, spacer locations and reference
window estimates. Routing-blocked geometry is displayed as a warning when target
metrics may still be possible; invalid reference/guide definitions block Review.
Reference-only geometry explicitly defers empirical routing qualification. The
new `geometry(..., reference_only=True)` path returns before synthetic read
routing; the default scientific preflight behavior remains unchanged.

Nuclease remains single-copy. Generic targets use explicit zero-based inclusive
qwc ranges: sentinel `0` is invalid, while `0-0` denotes a real coordinate. TIGR–Tas
uses `tigr_tas_v1`, an 18-nt target and W1/W2/W3/W4, with W2 initially selected.
Python returns orientation, target interval, physical nick boundaries,
target-oriented labels and selected coordinates. React renders these values; it
does not derive geometry or call variants. Mode/profile changes warn before
clearing incompatible target inputs.

The nuclease panel obtains all 58 expected scientific settings from Python.
They are read-only: Core 2.3.4, substitutions retained, current insertion semantics
requiring both anchors, end exclusions 0/0, one reference, and zero ambiguous or
discarded aligned populations. These are **requirements for future execution**;
setup does not claim to have qualified a locally installed executable or outputs.

Configuration deliberately exposes only library profile, paired analysis trims
and optional output proposal. Automatic trims require the existing qualified
untrimmed QI-HITOM layout; otherwise both explicit sizes are required. Statistics
are descriptive summaries; contrast creation is deferred.

## Versioned API and plan preview

All endpoints require the same local session token:

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/setup/capabilities` | Registered input/output capabilities and setup boundary |
| POST | `/api/v1/drafts` | Create a blank draft with no mode selected |
| GET | `/api/v1/drafts/{id}` | Read the current draft snapshot |
| PATCH | `/api/v1/drafts/{id}` | Replace content with an expected revision |
| POST | `/api/v1/drafts/{id}/validate` | Validate the specified revision |
| GET | `/api/v1/drafts/{id}/preview?revision=N` | Recheck inputs and return current validated preview |
| DELETE | `/api/v1/drafts/{id}?revision=N` | Discard the draft |

`DraftValidation` contains typed severity, code, step, field, message and optional
technical detail. Invalid drafts cannot obtain a valid preview. Field issues are
associated with controls and validation failure focuses the first relevant field.

`PlanPreview` uses `analysis-plan-preview-v1` and `executable: false`. It contains
sample and target identities, literal metadata, input hashes, reference
annotations, configuration, the existing stage graph, output proposal, backend
requirements and deferred capabilities. It is not the executable workflow `Plan`.
The existing `build_workflow_plan` probes Core and therefore is not called.

Canonical scientific identity includes normalized sample/target definitions,
input byte identities, demux/preparation settings, routing policy, statistics and
backend contract/version. Samples and copies are sorted by backend identity for
determinism. Analysis name and output proposal affect plan identity but not
scientific identity. Preview hashes are scoped to this preview contract; M11B
must build a fresh executable plan and full software/runtime/stage identities.

An output parent and safe leaf name may be proposed, but no directory, metadata,
FASTQ, scientific output or report is written there. Existing destinations and
protected input/workspace overlaps are rejected.

## Execution boundary and verification

Tests instrument workflow, demux, preparation, routing (including `route_pair`),
PE/nuclease metrics, aggregation, statistics, reporting, Core resolution and plan
execution/resume entry points. Real schema-based PE/nuclease browser flows run
with these guards active. Browser evidence records zero guarded calls and unchanged
workspace/input bytes and modification times, including the proposed output.

The disabled **Run Analysis** control has no executor endpoint. M11B will address
execution, resolved runtime qualification, progress, cancel, recovery, retry,
resume and force. M11A does not implement any of them.

Production frontend assets remain committed and checked by the M10.1 build gate.
Regenerate transport contracts with `python scripts/generate_viewer_types.py`,
then run `npm ci && npm run build` in `frontend/` before packaging. A stale or
missing asset inventory prevents wheel/sdist builds. Runtime serves bundled
assets without Node.
