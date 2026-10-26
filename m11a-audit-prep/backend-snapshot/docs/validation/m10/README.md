# M10 verified-result viewer validation

Backend base: `9e9a51fb20e56a3421fdfa156375170cd6b257dc`.
Final design authority: `05cfc68b62215a4c52862e09f081eab1c75ba39f`.
Implementation branch: `feat/m10-verified-result-viewer`. Version remains 0.8.0.
See [handoff checkpoint](HANDOFF.md) and [viewer documentation](../../m10-viewer.md).

## Results

| Check | Result |
| --- | --- |
| Complete source Python suite | 1,556 passed; 0 failures/errors/skips |
| Complete fresh-wheel Python suite | 1,556 passed; 0 failures/errors/skips |
| Original scientific/framework regression cases | All 1,524 passed in each suite |
| M10 adapter cases | 30 unit + 2 real-workflow integrations in each suite |
| Total real CRISPResso integrations | 81 passed in each suite (79 retained + 2 M10 fixture preparations) |
| Frontend unit/component guardrails | 15 passed |
| Source browser/E2E | 6 passed |
| Installed-wheel browser/E2E | 6 passed; server PATH contains neither Node nor CRISPResso |
| Automated accessibility | No WCAG A/AA violations in tested Overview |
| Layout | 1366×768, 1920×1080 and 200% zoom-equivalent CSS viewport checked |
| Original source/tests/validation evidence | 1,462 files byte-identical to base |
| Packaged source/assets | All 73 files match source, wheel and fresh installation |
| Clean frontend rebuild | `npm ci` + build reproduces identical static bytes |
| Source distribution rebuild | sdist-derived wheel contains the same 73-file payload |
| Actual installed launcher | Serves static assets and opens verified PE workspace without Node |

`validation-summary.json` contains exact versions, per-module test counts, JUnit/log
hashes and wheel SHA-256. `tested-package-payload.json` identifies all tested Python,
resource and bundled frontend files. The tests ran on the pre-commit implementation
payload based on the exact backend SHA; these hashes identify the bytes subsequently
committed/built, rather than claiming execution under a future commit SHA.

## Real scientific sources and execution isolation

Each integration run prepares real four-sample PE and post-M8.1 nuclease workflows
with pinned CRISPResso2 2.3.4. This preparation occurs before opening the viewer.
Nuclease preparation includes a genuine net-zero indel cohort. The viewer then
passes the completed roots through the actual authoritative verifier, strict
models, projection, HTTP API and browser. No mocked verifier substitutes success.

`real-workspace-evidence.json` records focused/source/wheel fixture checks.
`browser-immutability.json` and `wheel-browser-immutability.json` record the entire
browser sessions. All report **zero scientific executor/probe calls** and unchanged
workspace/input bytes and file modification times. Guards cover execute/resume,
plan building, backend resolution, demux, preparation, routing, PE/nuclease metric
execution, summarization/statistics and report generation. Validator/model
consistency checks remain active.

The installed browser server runs with an empty executable search path. The actual
installed `peanalyzer-viewer` entry point is also tested separately; see
`installed-launch.json`. Browser automation itself runs in the test harness and
is not a viewer runtime dependency.

## Failure and presentation coverage

Adapter tests reject missing completion, corrupt metric/M5/report/SVG/manifest,
missing/modified original input, unknown schema/status, actual stale stage identity,
symlink/traversal/special-file access and uninventoried artifact handles. A change
after opening invalidates both scientific reads and downloads. A change during
projection refuses publication. Missing/wrong-type/wrong-value nuclease qualification
and pre-M8.1 evidence are rejected by the existing scientific model.

Frontend tests intentionally vary fixture counts independently of stored fractions
and means to prove that rendering does not recompute science. Other checks preserve
null versus zero, separate PE exact/native denominators, overlapping nuclease
memberships, zero-size indels, stored window choices and unchanged p/q/biological n.
All scientific counts use lossless decimal-string transport. Sample and allele
paging preserve stable source identities. Native HTML is never embedded; fastp
HTML does not falsely imply a native CRISPResso report exists.

Browser flows cover every primary tab, both modes, sample detail, literal alleles,
qualification provenance, artifact download, close/reopen, invalid workspace,
revalidation failure hiding previous results, keyboard navigation and local API
session/origin rejection. Screenshots were visually inspected; raw screenshots,
logs and traces are retained outside Git under `/workspace/m10-implementation`.

## Remaining findings and boundaries

- **BLOCKING:** none.
- **MAJOR:** none.
- **MINOR:** none.
- **INFO:** each full Python suite emits 20 existing Matplotlib missing-glyph
  warnings from invalid-label tests and one Starlette/AnyIO deprecation warning.
- **INFO:** original input lineage and supported workspace locations remain
  mandatory. Full verification can be I/O intensive; large-workspace performance
  has no claimed benchmark or validation bypass.
- **INFO:** setup, execution, recovery, native HTML embedding/generation, rich
  sequence interpretation and portable relocation remain intentionally deferred.

The environment's browser-download CDN was unavailable; tests used installed
Chromium 154.0.8037.57. An initial installed-browser test attempt was invalidated
by concurrent dependency replacement; installation/build was completed first and
all six installed-browser cases were rerun successfully. Final evidence above
records the complete passing runs.
