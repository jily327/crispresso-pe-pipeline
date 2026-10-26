# Technology recommendation

## Recommendation

Use a **local React + TypeScript frontend, a small FastAPI Python adapter, and one supervised Python worker process**. Serve bundled frontend assets from the local service; open the user's ordinary browser. Bind to loopback by default. Reuse current Python workflow/validation/statistics/reporting APIs. No cloud service, scheduler, Redis, distributed queue, database server, desktop wrapper or independent scientific implementation is needed for the first release.

This is a proposed architecture, not code added to the repository. New web dependencies, endpoint schemas and release packaging require review in the eventual implementation milestone after M8.1 merges.

## Realistic options compared

| Criterion | Python-hosted UI (e.g. NiceGUI) | React/TypeScript + Python API — recommended | Desktop wrapper (e.g. Tauri + web frontend + Python sidecar) |
|---|---|---|---|
| Initial packaging | Few UI languages; browser server still needed | JS build at release time; ship static assets and Python service together | Additional native toolchain, signing and sidecar packaging |
| Rich sequence/table interaction | Possible, but server/widget coupling and custom JS grow | Explicit component/state model; strong grid/sequence control | Same frontend strengths as web, plus bridge complexity |
| Local FASTQs | Server can see allowed local paths; browser still hides arbitrary client paths | Explicit local-file capability flow avoids large unnecessary copies | Native file dialog easier; path permissions still need enforcement |
| Long-running execution | Must isolate worker from UI callbacks | API + separate supervised Python worker is a clear boundary | Same worker isolation required, plus app lifecycle coupling |
| Progress/reconnect | Supported with extra job/session design | SSE or polling contract; independent worker and replayable events | IPC/sidecar reconnect and browser events both need design |
| Plotting/report browsing | Python figures easy; native HTML isolation still required | Reuse M6 SVG; use returned data only for extra interaction | Embedded webview must isolate native reports from privileged bridge |
| Testing | Python tests plus end-to-end UI; custom widgets can obscure contracts | Typed adapter tests, component tests, Playwright and visual/accessibility checks | Adds OS installer, native dialog and webview matrix |
| Reproducibility | Backend package/runtime still pinned separately | One versioned UI/API build + exact scientific backend identity | Native release identity adds another moving component |
| Windows/macOS/Linux | UI broadly portable; backend qualification unchanged | UI broadly portable; backend qualification unchanged | Packaging and signing required per OS; does not solve backend portability |
| Maintenance | Attractive for a small internal prototype | More upfront setup, clearer long-term scientific/UI ownership | Highest burden; defer until native dialogs/offline installation justify it |

Streamlit-like whole-script rerun patterns are less suitable for a stateful, long-running workflow with safe force actions and dense sequence interaction. A Python-hosted UI remains a viable alternative if a lab prioritizes Python-only maintenance over richer interaction, but this study recommends one architecture rather than maintaining two implementations.

## Deployment contract

First qualify Linux local execution against the existing pinned CRISPResso 2.3.4 runtime. Package the browser assets and adapter with a declared compatible PEAnalyzer version. The UI must display the actual software/runtime identities. A verified executable version is not proof of a particular container digest; deployment supplies and verifies the real runtime binding.

Windows deployment should initially be documented through a separately tested WSL2/container environment; macOS may require Docker or another explicitly qualified setup, including architecture/emulation considerations. Do not advertise native Windows/macOS scientific execution until the full relevant backend and GUI suites pass there. Browser availability alone is not scientific runtime qualification.

No remote LAN binding or multi-user authentication in v1. If later required, that is a distinct access-control/deployment scope. After installation the GUI assets work offline; the backend image/dependencies must already be provisioned. Native imported reports with CDN dependencies are separately unavailable/degraded offline unless a qualified derivative supplies local assets.

## Process and storage boundaries

```text
Browser: React controls, navigation, accessible drawing, display state
    │ typed requests / events / verified artifact downloads
Loopback Python API: capabilities, draft validation, presentation projection,
                    safe file/artifact access, job supervision
    │ structured job request (no shell command assembly)
Single Python worker: existing execute_workflow / resume_workflow APIs
    │
M2 → preparation → PE routing OR nuclease identity → authoritative backend metrics
   → M5 → M6 → verified M7 completion
```

Use a GUI-owned local directory for draft JSON, input-import snapshots, an analysis catalog and job event records. Keep it outside scientific workspaces. Small atomic JSON records are sufficient for v1; no scientific data is stored only in a UI database. M7 owns scientific workspace files and locks. Browser data/cache is never completion authority.

One active workflow job in the first GUI deployment; no automatic sample parallelism. A worker remains independent of a browser connection. Resuming requires M7 validation, not an API process's memory. A restart can reconstruct catalog entries from user-selected verified workspaces and known session records. Jobs cannot be started twice by double-click or request retry.

## Proposed adapter surface — not existing endpoints

Names are a design contract to implement and test, not claims of current repository functionality. Schema identifiers are future GUI contracts, independent of M4/M5/M6/M7 scientific schemas.

| Operation | Request | Response / authority | Existing building block or gap |
|---|---|---|---|
| Get capabilities | Installed backend identity | Supported modes/profiles/windows, entry paths, schemas, limits, locked settings, unavailable features | A; resolve from explicit compatible backend capability map; fail closed for unknown versions |
| Select/register local source | Allowed-root selection or explicit local upload | Opaque source ID, display path/name, size, verification state | A; server file access, no path inferred from browser File.name |
| Validate draft/import | Draft revision, exact imported bytes or generated typed rows, source IDs | Structured field/row errors, normalized values, input identity, can-run blockers | `load_samples`, `load_targets`, `validate_metadata`, existing verifiers; A error envelope |
| Preview target | Mode-specific target rows and draft revision | Validated annotation tracks, coordinate system/reference hash, orientation/labels, resolved configuration, unavailable reasons | PE projection A; nuclease `window`/scientific identity P; never expose direct JS geometry |
| Preview run | Fully validated draft, output source capability, runtime selection | Plan hash, DAG, resolved stage parameters, expected inventory, warnings/blockers | `build_workflow_plan`; A review envelope; no backend science execution |
| Submit job | Validated revision/plan identity, idempotency key, explicit output intent | Job ID; accepted current identity or rejection | A supervisor calls `execute_workflow`; revalidate before use |
| Read job / events | Job ID, last event cursor | Sequenced status, actual stage IDs, timestamps, diagnostic references | A minimal events; existing plan/stage/failure/session records remain authority |
| Cancel | Owned job ID | Cancellation accepted then cleanup/terminal state | A supervision; preserve existing SIGTERM unwind philosophy and test child-process behavior |
| Preview resume/force | Workspace ID, selected families, current inputs | Reused/invalid/stale stages, descendant impact, input protection, confirmation identity | Existing validation and force closure; A stable preview API, no deletion |
| Execute resume/force | Confirmed impact identity | Job ID | `resume_workflow`; verify preview still current; M7 owns invalidation |
| Open verified results | Workspace ID | Contract-versioned projection referencing source hashes | `verify_workflow_output`, strict metric/M5/report models; A presentation adapter |
| Read sample/alleles/annotations | Verified result identity + stable keys + display paging | Stored fields or qualified artifact projection, source identity, nullable capability reasons | A; no variant caller, no silently recomputed fractions |
| Artifact/bundle access | Opaque inventoried artifact IDs | Download or isolated native view, actual media type/hash | A safe server; don't accept arbitrary browser filesystem paths |

A target preview envelope should include: draft revision, backend software identity, source reference hash, coordinate convention, exact normalized target/configuration, annotation track coordinates/labels, capability flags and errors. A result projection should include original contract IDs/hashes, stable sample/series/population keys, stored values/counts/status, backend-described denominators and availability of optional plots/artifacts. Do not silently coerce unsupported data into a familiar family.

## What may be computed in the adapter

Presentation-only adapters may format stored fractions, enumerate inventories, select rows and project existing authoritative coordinates to display tracks. Any new ratio required for QC must be explicitly backend-defined with its count basis and tested; the frontend does not divide arbitrary fields into a scientific rate. New position-vector readers need their own reference/denominator reconciliation tests. An adapter must not become a second PE/indel caller or statistical engine.

Prefer existing M6 SVGs for initial replicate and contrast plots; native SVG validity checks remain active. Browser rendering may map supplied values to pixels and handle zoom/filter selection. It must not derive target positions, windows, edit membership, means, p/q, denominator exclusions or cause-of-failure categories.

## Local file handling

For this local deployment, an in-app server folder browser is the primary path: the launcher/operator grants specific read roots and output parents. The API returns opaque file/directory capabilities. It verifies containment/symlinks using existing policies, then passes actual paths to Python. Windows-to-WSL/container mount mapping is displayed and validated, never silently guessed.

Browser Browse/drop offers an explicit alternative: “Copy into local input staging,” showing size, required disk space and progress from actual bytes transferred. Stream uploads; no in-memory FASTQ buffering. Finalize and hash before run; incomplete uploads are not inputs. Imported local files are never moved/deleted by force. A selected raw pair is one pool, not one sample per file. No remote cloud upload is implied.

## Long-running jobs and cancellation

Worker execution calls Python APIs directly, not shell chains. Add the smallest event bridge necessary around orchestration boundaries; do not edit scientific functions to emit UI-specific values. If only completion manifests can currently be observed, display a generic active job plus verified completions until proper stage-start events exist.

Events have a monotonic session sequence, actual stage ID, timestamp, state and diagnostic reference; no invented percent. Reconnect resumes event delivery or reconstructs state from records. A heartbeat loss marks connection/liveness uncertainty, not scientific failure by itself.

Cancellation requires process-ownership tracking and tests for Core/container subprocesses; current CLI SIGTERM handling alone is not a promise that a future supervisor can kill every descendant safely. Never kill a foreign runtime or clear foreign locks. A cancellation request can end in interrupted/incomplete state requiring inspection. Existing completed stages remain eligible for validated resume.

## Native report serving

The supplied report contains external Bootstrap, jQuery, Plotly, fonts and image dependencies. No native HTML is mounted in the application's privileged DOM. Use an isolated restricted origin/viewer without local API credentials, no unrestricted navigation or external fetches, and safe allowlisted relative artifact access; if functionality cannot be preserved safely, offer exact download/static previews instead.

Future offline/native packaging must inventory relative assets, verify source identity and retain original bytes. Label a rewritten portable copy as a derivative; never silently rewrite the authoritative report. Do not toggle Core plotting options or rerun scientific analysis in this design milestone. Qualification of future native-generation behavior must prove unchanged scientific outputs and be separately reviewed.

## Release and test plan

- Contract tests against exact post-M8.1 merged models; reject extra/unknown modes/statuses.
- PE unchanged-output tests; nuclease counts/exception handling; schema and capability matrices.
- Worker failure/cancel/reconnect, zero-execution resume, force closure and wrong-force rejection.
- Component tests for null vs zero, mean vs pooled fraction, B−A, immutable labels and revision-safe previews.
- Sequence accessibility/coordinate fixtures: forward/reverse/palindrome and boundary windows, supplied by backend.
- Playwright flows at 1920×1080, 1366×768 and 200% zoom; keyboard-only and automated/manual accessibility review.
- Offline assets, native-content isolation, traversal/symlink defense, imported HTML and missing plot capabilities.
- Fresh package installation plus pinned runtime on each advertised OS environment; source-versus-installed presentation parity where scientifically deterministic.

Implementation sequencing: (1) qualify adapter and read-only result viewer, (2) build setup/preview controls, (3) add supervised run/resume/cancel, (4) qualify optional native/position visualization. The design is ready for human review; implementation is explicitly gated on backend stabilization.
