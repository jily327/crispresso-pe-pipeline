# Practical GUI maintenance qualification (0.9.0)

Base: `72e0f86a495e079cab2ae50d2796e7a3423c78af`.
Candidate: `feat/practical-ux-inputs`. No PR or merge.

See [the engineering report](ENGINEERING_REPORT.md) for implementation, scope,
version/dependency changes, identity rules, findings and limitations. The exact
candidate SHA is the Git commit containing the final report; production bytes
remain those of the first implementation checkpoint.

| Gate | Measured result |
|---|---|
| Source Python | 1,972 passed; 0 failures/errors/skips |
| Fresh installed wheel Python | 1,972 passed; 0 failures/errors/skips |
| Retained/new Python inventory | 1,910 retained + 62 new; none removed |
| Integration inventory | 88 retained + 2 new = 90 |
| Frontend | 56 passed |
| Source browser | 35 passed; 0 failures/skips/flaky |
| Installed-wheel browser | 35 passed; 0 failures/skips/flaky |
| Package | source and wheel report 0.9.0; 89 package files byte-identical |
| Frozen boundaries | 64 files byte-identical to base; complete production diff recorded |
| Scientific parity | legacy/manual vs upload/XLSX, PE + nuclease; source vs wheel |
| Prior 0.8.0 outputs | scientific values unchanged; SVG creator credit changes to 0.9.0 |

Browser inventory is 18 viewer/Setup, 6 Run, 8 Recovery and 3 practical-input
scenarios. Actual browser File inputs and native Core execute in Linux Chromium.
Windows OS/browser testing was not available. Both viewer audits record zero
scientific calls and unchanged input/workspace bytes and mtimes.

`qualification.json` records counts/timing; `case-retention.json` records exact
node-ID retention; `scope.json` and `frozen-core.json` record production boundaries.
Transport, baseline and source/wheel parity JSON records accompany the report.
The source/wheel suite logs and environment-specific runners are included. These
runners identify the qualified local native backend; adapt their executable paths
to the audit environment. They do not replace the production launcher.

## Durable checkpoints and harness corrections

- `2cb293d240c78d197d5fd89a14f3ea8bb0c07363`: implementation and focused tests.
- `858a4817a8e3e4339dd9bc3e32af43d6a348afee`: real browser/transport parity tests.
- `b1c52d2cbc42b015e6cc06b58727af6bc945e5b5`: complete passing source suite.
- `ee2214973bad6642950d8453731b94e023336afa`: complete passing source browsers.
- `d3d9f27`: interruption diagnosis; production unchanged.
- This evidence commit: final wheel/browser/package qualification and handoff.

Development harness corrections are documented in the engineering report. The
initial external wheel-test workspace lacked a historical audit fixture and a
developer generator script, causing four FileNotFoundError failures. Exact
committed test inputs were restored; the four passed, and the entire wheel suite
was restarted with fresh outputs and unchanged production/wheel bytes. The table
reports the complete successful run, not a combination of partial runs.

No new scientific or lifecycle behavior was introduced. Known M11C minor/info
findings and optional extra UX items remain deferred. This evidence supports an
independent focused audit; it is not a merge approval.

The tool-session interruption after 1,757 reported passes is recorded separately.
Two isolated installed-wheel transport tests passed; the detached full runner then
completed all 1,972 cases with exit 0. No partial-run totals are combined. A temporary
GitHub HTTP 401 resolved after the managed authorization refreshed; no credentials
are stored in these artifacts.
