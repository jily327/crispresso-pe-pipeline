# Practical GUI inputs / Results / final-verification engineering report

Candidate branch: `feat/practical-ux-inputs`.
Base: `72e0f86a495e079cab2ae50d2796e7a3423c78af`.
The exact final candidate is the Git commit containing this report; the final
handoff records its full SHA. No PR or merge is part of this task.

## Version and dependencies

Authoritative version `pyproject.toml`: **0.8.0 → 0.9.0**. No conflicting project
version policy was found. Production version sources changed: `pyproject.toml`,
`frontend/package.json`, `frontend/package-lock.json`. Generated
`src/peanalyzer/gui/static/build-identity.json` binds those release inputs; the
frontend bundle was rebuilt for the feature changes. Runtime `__version__`
continues reading installed distribution metadata. Historical validation records
were not rewritten. The new package-consistency test runs against both source
installation and fresh installed wheel.

GUI/dev extras intentionally add openpyxl 3.1.5 and defusedxml 0.7.1; the GUI lock
also pins openpyxl's et_xmlfile 2.0.0 dependency. No Office executable is needed.

## Scope and implementation

[scope.json](scope.json) lists every modified production file. New production modules are
`gui/uploads.py`, `gui/sample_workbook.py`, and
`frontend/src/components/InputImports.tsx`. Existing API/launcher, setup references
and DTOs, Results projection/components, Run presentation and generated types/assets
receive only the corresponding additive wiring/presentation changes.

Browser File inputs send actual FASTQ bytes over the existing authenticated local
API. Server-owned UUID paths, bounded streaming, SHA-256/size receipts, existing
FASTQ syntax validation and atomic registration separate accepted uploads from
partials. Handled failures clean owned partials; completed originals are retained
for accepted-workflow verification/recovery, including after draft replacement.
External sources are never cleaned. See the feature contract for limits, private
storage ownership, no-symlink checks and the hard-kill orphan limitation.

Excel's required columns are barcode_id, sample_name, editor, treatment, dpi and
biological_replicate. Optional columns cover block/paired and barcode IDs/sequences.
Whitespace trimming, exact integer cells, explicit booleans and optional blanks
are documented; no dpi is invented. Formula, external-content, malformed numeric,
unknown column/catalog and duplicate-row cases fail closed with row/field errors.
QI shorthand resolves through the existing qualified catalog. Existing Sample and
CSV cross-row validation supply the authority. Successful import replaces only
editable sample rows after confirmation; ordinary Validate & Review and explicit
Run remain mandatory. Manual input and legacy launcher registration remain.

Results → Samples shows Exact intended PE and **CRISPResso Prime-edited reference
fraction** simultaneously with stored integers, percentages, populations,
definitions and evidence links. The comparator is reference-assigned/aligned,
not CRISPResso Modified%. Copy-conditioned diagnostics occupy a separate selector
group. Internal metric IDs, null/blocked semantics and calculations do not change.

Run displays final verification from existing events/counts while authoritative
state remains RUNNING. Existing verification still gates COMPLETED and Open Results.
No worker, cancellation, supervision, recovery or terminal-state rule changes.
Existing software-version/provenance gates remain in force; this is not a new
cross-version recovery compatibility guarantee.

## Identity, parity and frozen boundaries

Current Setup identities contain input basename/hash/size; plan identity additionally
contains analysis name and destination. Generated upload basenames can therefore
change digests. Equivalent same-basename inputs match the exact digests. Both
transport paths match canonical metadata/catalog/target/configuration and all
scientific outputs. PE and nuclease real-backend tests exercise both paths.

`frozen-core.json` and the complete production diff prove unchanged science and
recovery execution bytes. Scientific parity independently compares metrics,
statistics, prepared reads, routing records and report figures. Comparisons to preserved prior 0.8.0 qualification outputs
find that SVG differences are restricted to the package-version creator credit;
source versus wheel at 0.9.0 requires identical compared scientific payloads.
Root-bound paths, population/source hashes, invocation, timestamps and source-vs-
installed software provenance are documented execution differences, not science.

## Qualification

| Gate | Result |
|---|---|
| Complete source suite | 1,972 passed; 0 failures/errors/skips |
| Complete fresh-wheel suite | 1,972 passed; 0 failures/errors/skips; exit 0 |
| Python inventory | 1,910 retained + 60 new non-integration + 2 new integration |
| Integration inventory | 88 retained + 2 new = 90 |
| Frontend unit tests | 56 passed |
| Source / wheel browser suites | 35 / 35 passed; 0 failures/skips/flaky |
| Source / wheel package | 0.9.0; 89 package files byte-identical |
| Frozen core | 64 files byte-identical to base |

See qualification.json for exact measured counts and elapsed times, case-retention.json
for all prior node IDs retained by collection, package-parity.json for wheel bytes,
and the transport/baseline/source-wheel parity records for independent comparisons.
The committed runners show the environment and invocation. All tests use synthetic
data and the existing qualified native CRISPResso2 2.3.4 environment.

The retained suites cover Setup/legacy/manual/QI-HITOM, PE/nuclease/statistics/reports,
verified viewer artifacts, M11B Run/cancel/reconnect and M11C resume/force/recovery.
New browser checks use actual File inputs, downloaded/imported Excel, editable rows,
real PE/nuclease Run, final-verification pause/reload, primary metrics, rejected
replacement, accessibility and viewport reflow. The test-only pause blocks the event
producer, never a production arbitrary-command endpoint.

## Findings and limits

No unresolved new BLOCKING, MAJOR or MINOR product failure was observed in these
gates. The following corrections concerned test harnesses or execution infrastructure.

No new product failure is claimed from corrected harness defects. Development
harness corrections: catalog fixture letters; mocked Promise; updated visible label;
Playwright response lifetime; two expected equal metric counts; producer rather than
reader pause for final verification; missing historical fixture/generator files in
the initial external wheel-test workspace. The four missing-file failures passed
after copying those exact committed audit inputs, then the entire wheel suite was
restarted. A later tool-session runner disappeared after 1,757 passing cases without a
final result; both transport tests then passed independently. A detached full
runner completed all 1,972 cases with exit 0. No incomplete run is counted as a
pass. These did not require scientific/lifecycle or wheel changes.

INFO: browser qualification is Linux Chromium exercising the platform-native File
input; an actual Windows OS/browser was not available. The memory test streams a
synthetic file over 10 MiB with a less-than-6-MiB traced allocation bound; multi-GiB
throughput was not benchmarked. Completed uploads need operator storage management;
hard-kill partial cleanup is not an automatic scavenger.

Known M11C MINOR/INFO findings remain intentionally deferred. Optional full-path /
copy-path, extra runtime wording and sample/editor-name warnings were not added.
This is a candidate for an independent focused audit, not approval to merge.

READY FOR INDEPENDENT FOCUSED AUDIT
