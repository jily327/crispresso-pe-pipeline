# M11A validation report

Status: **PASS**. M11A validates and previews analyses but does not execute them.

- Branch: `feat/m11-analysis-setup`
- Exact base: `40bd8ad8844fd07ce8a138b5520f7f0ec948030f`
- Implementation HEAD: `86c5bbf93fa5246bd5fbfbb4633d8623471e01de`; the following evidence commit contains this report.
- Package version: `0.8.0` (unchanged)
- Design authority: `05cfc68b62215a4c52862e09f081eab1c75ba39f`, all six final M9.1 documents.

## Delivered behavior

New Analysis provides Samples & Sequencing → Mode → Target → Configuration → Review.
Open Existing Analysis preserves the M10/M10.1 verified snapshot viewer and its
cached-verification behavior. Switching between flows preserves the active draft.

PE fields: target/copy name, WT and intended edited amplicons, pegRNA spacer and
extension, optional nicking guide and scaffold. One target may have multiple
copies sharing the experimental guide/extension. Python validates schema and
reference geometry, returning difference and guide annotations.

Nuclease fields: one target/copy, WT amplicon, explicit inclusive qwc or TIGR–Tas
profile, 18-nt target and W1–W4. W2 is initially selected. Both orientations use
backend geometry, including physical nick boundaries, selected coordinates and
target-oriented labels. Sentinel `0` fails; `0-0` is a valid real coordinate.
The 58 expected scientific fields are backend-returned and locked.

Inputs use explicit launcher registrations and opaque references: one paired pool
plus barcode-defined samples, or a verified M2 archive. Sample metadata is never
inferred. Optional output destinations are proposals only and are never created.

## API and identity

Added GET `/api/v1/setup/capabilities`; POST `/api/v1/drafts`;
GET/PATCH/DELETE `/api/v1/drafts/{id}`; POST `/api/v1/drafts/{id}/validate`;
GET `/api/v1/drafts/{id}/preview?revision=N`.

Drafts are typed, in-memory, opaque-ID objects. Full-content patches require an
expected revision and invalidate validation. Responses carry revision/digest
identity. Frontend generation guards reject stale save, validation and preview
responses. Input byte identities are checked before/after validation and again
on preview retrieval. Validation issues include severity, code, step and field.
Hidden sample rows are revealed before focusing validation errors.

`analysis-plan-preview-v1` is explicitly non-executable. It contains biological
metadata, input hashes, normalized targets, annotations/configuration, existing
workflow DAG stages, output proposal, backend requirements and deferred flags.
Scientific edits change scientific identity; presentation names do not. Plan
identity also includes analysis name and destination. M11B must build and verify
a fresh executable plan and actual runtime identity.

## Validation results

| Layer | Existing baseline | New M11A | Final result |
|---|---:|---:|---:|
| Python from source | 1572 | 64 | 1636 passed, zero failures/skips |
| Python from fresh wheel | 1572 | 64 | 1636 passed, zero failures/skips |
| Frontend | 17 | 12 | 29 passed |
| Browser against source | 10 | 4 | 14 passed |
| Browser against installed wheel | 10 | 4 | 14 passed |

Final source setup/package checks also passed all 69 cases. The full suites include
qualified Core integration fixtures; those fixture executions are separate from
setup/viewer actions. Tests were not removed or skipped. Existing warning output
comes from deliberate invalid-glyph cases and an upstream Starlette deprecation.

Executor guards cover workflow execution/resume, executable probing, demux,
preparation, routing including synthetic `route_pair`, PE/nuclease metrics,
aggregation, statistics and reports. Both browser audits recorded **zero** guarded
calls and unchanged workspace/input bytes and mtimes, including output proposals.
The disabled Run control has no execution endpoint. PE reference-only annotation
returns before empirical routing trials; default scientific preflight is unchanged.

Browser coverage includes real PE, explicit nuclease and TIGR validation, W2→W1
updates, invalid sentinel rejection, error focus, existing viewer access, keyboard
navigation, accessibility scans, desktop widths and 200% equivalent reflow.
Frontend tests also cover mode cancellation, all three stale-response phases,
backend-owned Review and locked configuration.

## Packaging

A fresh isolated install was checked against every wheel package member before
running the full wheel suite. Clean checkout wheel, clean checkout sdist→wheel
and working-tree wheel contain the same 82 member names and bytes. Builds and the
installed GUI server work with Node and CRISPResso absent from PATH.

An incremental build experiment exposed obsolete hashed JS in setuptools staging.
The build command now refreshes only its generated static staging directory after
the existing source identity gate passes. A seeded obsolete bundle is excluded;
its wheel equals the clean wheel. Directing staging to source assets is rejected
without modifying source. Missing/stale asset rejection tests remain intact.

An earlier validation harness selected an older same-version virtualenv. The asset
gate correctly rejected that attempt. It is excluded from the final results above,
which use a fresh environment with explicit installed-member verification.

## Limits and handoff

Drafts are ephemeral and have no persistence/library UI. Files must be registered
at launch; there is no unrestricted browser path API, upload or native chooser.
Custom extraction currently means barcodes at the read start, without bridges.
Only one target, paired-end input, single-copy nuclease and descriptive statistics
are exposed. Contrast creation and broader library layouts remain deferred.

Backend runtime qualification is an expected contract in this preview, not a claim
that installed Core or future output populations have been verified. M11B owns
execution, progress, cancellation, recovery, retry, resume and force. M11A stops at
validated Review. No PR or merge is part of this delivery.

No remaining BLOCKING or MAJOR finding was observed. See `validation-summary.json`,
`commands.json`, the individual logs and browser/package identity evidence here.

## Implementation commits

- `de9ceea` Add revisioned analysis drafts and backend-owned setup previews
- `f045d22` Add analysis setup wizard and validated Review without execution
- `314227a` Verify setup boundaries and document the M11A contract
- `3bc57f0` Reveal filtered samples before focusing validation errors
- `86c5bbf` Refresh wheel static staging to exclude obsolete hashed assets

The complete changed-path inventory is in `changed-files.txt`.
