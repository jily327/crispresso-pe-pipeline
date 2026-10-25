# M10: read-only verified result viewer

M10 is **READ-ONLY**. It opens existing completed M7 workspaces and displays
verified stored PE/nuclease results. It does not execute or alter scientific
analyses. Original source input paths and bytes required by the authoritative
verifier must still be available. A moved folder, standalone metric JSON, report
ZIP or incomplete workflow is not a supported substitute.

## Install and launch

Use Python 3.11+. Node.js 24 is needed only for frontend development or bundle
regeneration; ordinary Python package builds use committed assets, and installed
viewer runtime does not require Node. For frontend development, from the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock -r requirements-gui.lock
python -m pip install -e '.[gui,dev]'
cd frontend
npm ci
npm run build
cd ..
peanalyzer-viewer --workspace /absolute/path/to/completed-workflow
```

Open the exact local URL printed by the launcher, including its session fragment.
The fragment is removed from the address bar after loading and retained only in
that browser tab's session storage. Register multiple explicit workspaces by
repeating `--workspace`. The browser receives opaque registration IDs and labels;
it cannot submit arbitrary filesystem paths or browse the filesystem. A missing
registered folder is shown as a typed open error. Restart with another explicit
registration to add a workspace. There is no persistent catalog. Verified snapshots
are held in process memory outside the scientific workspace. Default labels use
the shortest distinguishing parent suffix when basenames collide; explicit labels
are preserved. Access always uses opaque IDs, never display labels.

The listener binds **127.0.0.1 only**; `--port` changes the port (default 8765).
There is no LAN host option. API requests require the launch token, a loopback
Host and a matching Origin when supplied. No CORS access is enabled. The app's
CSP forbids frames, objects and remote resources. Do not expose this local reader
through a public reverse proxy.

Development can use `npm run dev` in `frontend` with the adapter on port 8765;
Vite proxies `/api`. Open the Vite URL with the adapter's token fragment. The
production build bundles all JavaScript/CSS locally and requires no CDN requests.

## Architecture and ownership

- `frontend`: React/TypeScript, Vite, five result views, semantic tables, keyboard
  tabs, sample details, pure display sorting/filtering and exact-value alternatives.
- `peanalyzer.gui.app`: versioned FastAPI transport, loopback/session boundary,
  typed errors, capabilities and static assets.
- `workspace`: explicit in-memory registration; existing `verify_workflow_output`;
  strict stored models; before/after file identities; invalidation on change.
- `projection` / `models`: typed presentation values and stable sample/series joins.
- `artifacts`: manifest-bound opaque IDs, exact-byte downloads and containment.

Existing Python models own qualification, reportability, geometry, fractions,
populations, source identity and statistics. Their consistency checks are allowed
and remain active. The adapter does not execute scientific stages, resolve or probe
Core, rebuild a plan, call resume, recompute M5 or regenerate reports. The eventual
supervised scientific worker and setup/execution application are deferred.

The frontend renders the adapter's formatted stored fractions. It never divides
counts, computes means/p/q, reconstructs alleles, derives TIGR geometry, changes
windows or repairs missing scientific values. All scientific integer counts are
transported as decimal strings, including counts larger than JavaScript's safe
integer range. Source percentages and full fractions remain available. Condition
means have biological n, not invented pooled numerators/denominators.

## Views and supported contracts

Overview, Samples, QC, Statistics and Provenance support `m7-v1` completed
workspaces, PE `m4-v1` / `m5-v1` / `m6-v1`, and final post-M8.1
`indel-nuclease-v1` / `indel-nuclease-stats-v1` / `indel-nuclease-report-v1`.
Unknown contracts, unknown states and failed qualification are rejected.
Capabilities include the exact backend base and installed viewer software identity.

PE exact/native remain separate, with their stored populations, denominator
labels, assessment stage, backend-count role, copy/policy identity, exclusion
and QC evidence. The selected metric series controls sample/statistical tables;
Overview retains the approved target-primary hierarchy. Changing a display filter
does not change any stored group summary.

Nuclease uses the authoritative indel fraction, four ordinary exclusive classes,
and a separate **Overlapping metrics — do not sum** table. Stored net-size bins
preserve zero-size indels. A sample detail provides paged typed allele rows and
literal aligned/reference strings. The selected window/profile/orientation/cuts
come from stored resolved geometry; explicit/palindromic nulls are not filled in.
The full expected scientific configuration and actual resolved arguments are
read-only provenance. Python's existing 58-field and zero-exception gates remain
the authority; no frontend qualification policy is copied.

Statistics shows stored sample points, condition means/minimum/maximum/median,
expected/reportable biological n, explicit effects/p/q and paired-block evidence.
No requested tests is distinct from an unavailable contrast. Provenance includes
source contracts/hashes, runtime/software identity, stage execution/reuse and
verified artifact inventory. Local input paths are omitted from routine views;
original diagnostics/downloaded source files may contain their recorded paths.

## Verification, immutability and artifacts

Open verifies the complete workflow at its recorded location, then strict-loads
and projects the inventoried M5/metric sources. Files used for projection must
match the verified hashes. Snapshot identity covers workspace regular-file bytes,
directory inventory, original input hashes and analyze-mode external demux
archive inventory. Symlinks, traversal and special
files are rejected. Full authoritative verification runs **once per successful open**. Workspace and
original-input identities are captured before verification and checked after
projection before the immutable in-memory snapshot is published.

Every API read/download compares current file hashes and directory inventory
with that snapshot, without rerunning the scientific verifier; scientific results are hidden
when a request fails. The UI also checks the current snapshot every 15 seconds
while idle, scheduling the next check only after the prior check completes.
The badge describes the verified snapshot, not an assertion of continuous
filesystem locking. Full verification can still be expensive at open; later reads
perform streaming SHA-256/inventory checks and return cached typed projections.
A mismatch invalidates the handle and requires reopening. Downloads check exact
artifact bytes against their recorded hash and recheck the snapshot before returning
those bytes. The local API runs blocking readers outside the event loop. The cache
never grants permanent trust to mutable disk files. Tabs remain keyboard-focusable
while the content region reports `aria-busy`; successful open focuses the analysis
heading intentionally.

The viewer creates no locks, sessions, indexes, manifests, outputs or caches in
scientific workspaces. Registration and projected data live in process memory.
Browser session state belongs to the browser. Existing validator imports may use
normal system caches (for example Matplotlib), outside scientific workspaces.

Artifacts must occur in verified workflow/stage inventories, remain contained
under the registered root, and still have their recorded size/hash. The browser
uses opaque IDs, never paths. Text/JSON/table/YAML/log/SVG/HTML/ZIP files can be
downloaded as attachments; other inventoried files are listed without download.
HTML/SVG are never embedded in the privileged app. Native CRISPResso report
availability is based on its recorded `report_filename` and inventoried file,
not a fastp HTML report. Absent native HTML is **Not produced** and never triggers
execution. No bundle generation or portable report rewriting is performed.

## Build and release

Release policy: committed, reproducible prebuilt frontend assets (Option A).
A clean checkout can build wheel and sdist without Node. Node is needed only
when changing the frontend and regenerating its production bundle:

```bash
(cd frontend && npm ci && npm run build)
```

The build records hashes of production sources, build configuration, lockfile and
output assets in `gui/static/build-identity.json`. Both wheel and sdist commands
validate this identity and fail with `VIEWER_ASSET_IDENTITY_MISMATCH` for missing,
modified or stale assets. They cannot silently produce a viewer-less wheel.
From a clean checkout (including building a wheel from the sdist):

```bash
python -m build
python -m venv /tmp/peanalyzer-viewer-install
/tmp/peanalyzer-viewer-install/bin/pip install 'dist/crispresso_pe_pipeline-0.8.0-py3-none-any.whl[gui]'
/tmp/peanalyzer-viewer-install/bin/peanalyzer-viewer --workspace /absolute/path/to/completed-workflow
```

Generated assets live in `src/peanalyzer/gui/static` and are committed and
included in wheel/sdist package data, alongside the source/build identity.
Rebuild with the pinned Node/npm environment and compare asset hashes to check
reproducibility; the Python build gate binds the committed inputs and outputs. Runtime needs Python and the `gui` extra, not Node.
A source installation without built assets fails launch with an explicit build
instruction. `requirements-gui.lock` pins the adapter/test dependency closure
alongside the unchanged scientific/development lock. `frontend/package-lock.json`
pins frontend/build/browser-test dependencies. Regenerate transport types after
presentation-model changes with `python scripts/generate_viewer_types.py`.

## Validation

```bash
python -m pytest -q tests/test_gui.py
(cd frontend && npm test && npm run build)
```

Real fixture preparation is a separate test action, before viewer guards:

```bash
M10_INTEGRATION=1 M10_RESULTS_DIR=/tmp/m10-real \
M3_CORE_EXECUTABLE=/path/to/qualified/CRISPResso \
python -m pytest -q tests/test_gui_integration.py
M10_E2E_ROOT=/tmp/m10-real python tests/gui_e2e_server.py
# In another terminal:
(cd frontend && npx playwright install chromium && npm run test:e2e)
```

A preinstalled Chromium can be selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.
The browser test server guards all scientific executors and backend probes, then
checks original input/workspace bytes and modification times during shutdown.
It is test-only and uses a fixed test token; the production launcher always
creates a random token. Integration preparation makes real four-sample PE and
nuclease workflows using qualified Core 2.3.4. Those exact roots cross verifier →
projection → API → browser, with no caller execution during viewing.

Source and fresh-wheel validation retain every prior test, enable all existing
real integration flags, and add failure, paging, precision, source-mutation,
qualification, frontend ownership, keyboard, AA and reflow tests. See
[M10 validation evidence](validation/m10/README.md) and
[M10.1 focused remediation evidence](validation/m101/README.md) for exact results
and identities.

## Deferred capabilities

New Analysis, uploads, metadata/target editors, workflow execution/progress,
resume/force/cancel, scientific configuration controls, rich sequence annotation,
PE native allele parsing, new statistics/position plots, native HTML viewing or
generation, persistent catalogs and portable workspace relocation remain deferred.
M10 is a completed reader slice, not a runner.
