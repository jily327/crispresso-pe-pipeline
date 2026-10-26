# M10.1 — four focused viewer remediations

Base / direct parent: `b410585f92c30f8dbaf96e47bf3963a132ebb75d` on
`feat/m10-verified-result-viewer`. Original M10 base/main remains
`9e9a51fb20e56a3421fdfa156375170cd6b257dc`. Package remains **0.8.0**.
This is focused remediation evidence, not a new scientific or broad GUI audit.

## Changes

1. **Verified in-memory snapshot:** exactly one authoritative
   `verify_workflow_output` per successful open. Workspace and original-source
   hashes bracket verification/projection. Subsequent tabs, polling, paging and
   artifact lookup use a streaming hash/inventory comparison and cached typed
   presentation data, never the full scientific verifier. Analyze-mode external
   demux inventory is included (an extra FASTQ must invalidate the handle).
   Downloads remain manifest-bound opaque IDs: check the snapshot, read/check
   exact bytes, recheck the snapshot, then return those verified bytes. Any
   detected mutation invalidates the handle; reopening is required. Nothing is
   cached or written inside a scientific workspace. Returned projections are
   copied so callers cannot mutate the cached presentation through a response.
2. **Default registration labels:** minimum distinguishing parent suffix, e.g.
   `A / workflow`, `B / workflow`, while `unique` stays short. Explicit labels
   are preserved. Repeated default paths get deterministic numeric suffixes.
   Access is still controlled by opaque registration/workspace IDs. Browser
   tests open same-basename PE/nuclease studies and check their distinct values.
3. **Keyboard focus:** tabs remain enabled while the panel has `aria-busy`;
   Enter/Space/click preserve focus, arrows/Home/End move focus to the intended
   tab, and the most recent navigation request owns the displayed tab. A
   successful initial open intentionally focuses the analysis heading. Tab then
   continues to the biological-sample selector; there is no focus trap.
4. **Packaging Option A:** production frontend assets are committed. The
   `build-identity.json` binds production sources, build settings, lockfile and
   asset hashes. Both setuptools wheel and sdist hooks reject missing/stale
   assets with `VIEWER_ASSET_IDENTITY_MISMATCH`. `npm ci && npm run build`
   regenerates the bundle/identity; Python packaging does not require Node.
   Installed viewer runtime requires neither Node nor CRISPResso. A separate
   rebuild produced byte-identical assets and identity metadata.

## Focused validation

Final source: **1,572 passed**; fresh wheel: **1,572 passed**; each includes
**81 real integrations**, with **0 failures / 0 errors / 0 skips**. All 1,556 prior
cases remain; 16 focused Python cases were added. Frontend: **17 passed** (15
retained + 2); browser: **10 passed source / 10 passed wheel** (6 retained + 4).
All 63 non-GUI package files match the parent byte-for-byte. Existing warnings
(20 Matplotlib label warnings and one Starlette/AnyIO deprecation) remain.
See `qualification.json` for counts and `performance.json` for measured timing.

The 206,038,630-byte real Azenta workspace measured **66.986 s** for the original
full verifier and **67.4102 s** for M10.1 open (one full verification). After open:
Overview 0.3133 s; Samples 0.3129 s; QC 0.3136 s; Statistics 0.3623 s;
Provenance 0.3195 s; poll 0.3096 s; artifact metadata 0.3101 s; complete JSON
download 0.6633 s. Across these requests there was **one total full-verifier call**,
zero scientific execution and unchanged workspace/source bytes and mtimes.

`installed-launch.json` records the actual installed production launcher opening
both PE and nuclease fixtures without Node/Core in PATH and serving assets from
site-packages. Source/wheel browser guard records are cumulative per test-server
lifetime (the source record includes a test retry after a catalog-readiness race).
All final browser cases passed; no product change was needed for that test race.
The final-HEAD clean-checkout build/launch is repeated after the one commit; these
committed suite records describe the tested pre-commit production payload.
The retained inventory contains 1,556 Python cases, 81 real integration scenarios,
15 frontend cases and six browser cases. Added regression coverage includes
cache call counts, same-content projection isolation, workspace/source/external
archive mutation, before/after-read download races, disambiguated registrations,
asset/source identity corruption, Enter/Space loading focus, initial open focus,
and cross-workspace mode separation. No existing cases were removed or skipped.

A sandboxed local TestClient attempt stalled; qualified API/browser/suite runs
use the environment's normal local networking permissions. Early development
runs were stopped when build inputs changed so scientific fixture preparation
could not mix package revisions. The workflow's `SOFTWARE_CHANGED` guard correctly
rejected such a preparation attempt; final qualification uses stable package bytes.

## Real Azenta timing fixture

The available historical Azenta workspace fails the unchanged current verifier
with `STALE_STAGE_IDENTITY` at `routing::1A::ALSW`. It was not modified or accepted
through a bypass. A separate equivalent workspace was prepared from the original
immutable raw input/metadata files using the qualified runtime and the frozen
installed M10.1 wheel. This preparation is separate from viewing. All viewer
probes forbid scientific executors and backend version probes and fingerprint
workspace/source bytes and mtimes before/after. The original M10 verifier code
is measured on the equivalent completed workspace for a comparable baseline;
the audit's 83–90 seconds is also recorded as reported context, not a universal
benchmark. Subsequent latency is hash-I/O-dependent; polling remains 15 seconds
after the previous check completes. Open can still be slow by design.

## Boundaries and limitations

All non-GUI scientific modules remain byte-identical to the parent. No metric,
class, denominator, geometry, qualification, statistics, reportability or
provenance contract was changed. INFO-only presentation findings are deferred.
The snapshot is process-local, not a persistent catalog; reopening and process
restart require full verification. Original source locations remain required.
Hash checks do not lock writers continuously, but changed bytes are never parsed
or downloaded as newly verified content. Filesystem hashing still costs I/O.
No execution, upload, native HTML embedding, cancellation or M11 feature was added.
The next step is one focused re-audit of these four fixes.
