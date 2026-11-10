# PEAnalyzer v1.0.0 — Desktop, Library and Excel Audit

Candidate `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`. This audit ran in a Linux container. Anything that needs a real Windows desktop is marked exactly **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED** and is not inferred from Linux behaviour.

## 1. Historical analysis library

To avoid testing against imitations, I produced **genuine** workspaces: the source trees at `72e0f86` (0.8.0) and `432b7cc` (0.9.0) were exported read-only, installed into isolated environments, and each release's own CLI analysed the same synthetic pool with the real backend; 1.0.0 did the same. A 0.8.0 nuclease workspace was added. Then the 1.0.0 viewer was pointed at the common parent (`--view-only`). `scripts/exp_library.py`, `evidence/E25_E32_historical_library.json` — 9/9 controlled.

| Requirement | Observed |
|---|---|
| Discovery performs no science | Server started `--view-only`; a job submission returned `409 RUN_UNAVAILABLE`; discovery reads only two marker files per candidate |
| Old workspaces are not modified | Full fingerprint (bytes, size, mtime, inode, inventory) of all three workspaces identical before and after discovery + Open + Refresh |
| "Detected" is not "verified" | All entries read "Detected — verification required" until opened; a forged marker claiming `COMPLETED`/9.9.9 was listed as detected, failed Open (`409`), and was relabelled "incompatible" |
| Duplicate names distinguishable | Three folders all named `exp1` appeared as `v0.8.0 / exp1`, `v0.9.0 / exp1`, `v1.0.0 / exp1` |
| Incomplete not shown as completed | Workspace without completion marker: "Incomplete — use Recovery"; Open → `409 INCOMPLETE_WORKSPACE` |
| Symlinks cannot bypass containment | Symlinked workspace directory and symlinked completion marker: not catalogued |
| Version labels from provenance | A 0.8.0 workspace inside a folder named `v9.9.9-looks-new` was labelled "PEAnalyzer 0.8.0" (and failed Open, because relocation is unsupported) |
| Verification failures stay visible | Error code and detail returned to the client; label downgraded, never upgraded |
| Cross-version consistency | 0.8.0, 0.9.0 and 1.0.0 workspaces all opened verified; exact PE equals the designed truth in each; both primary metrics identical across the three releases; no workbook created by viewing (export `MISSING`); nuclease → `NOT_APPLICABLE` |

Caveat: the "version from provenance" is the unverified stored value at discovery time and distribution metadata at creation time (F-15). Discovery limits (depth 4, 5,000 directories, 500 candidates) were reviewed in `gui/library.py` but not stress-tested.

## 2. Excel input (official sample template)

`scripts/exp_excel_import.py` drives `gui/sample_workbook.py::parse` with 57 fabricated workbooks; each expectation was fixed before the call. `evidence/E09_excel_import.json` — **57/57 as expected.** The happy-path experiment additionally imported through the real HTTP endpoint.

| Area | Cases (all behaved as expected) |
|---|---|
| Formulas / active content | formula in name, in dpi, DDE-style text, hyperlink cell, macro part, external-link part → rejected |
| Leading zeros | text `007` preserved; numeric `7` becomes `"7"`; `04A` shorthand rejected; numeric barcode ID rejected |
| Barcode combinations | unknown forward (`13A`), unknown reverse (`4Z`), lowercase, conflicting explicit catalog ID, conflicting explicit sequence → rejected; redundant matching sequence accepted |
| Malformed container | not a ZIP, empty body, truncated XML, entity-expansion DOCTYPE, oversized archive → rejected as import diagnostics, no exception escaped |
| Headers / structure | duplicate, unknown and missing headers; hidden row/column; merged cells; extra sheet; hidden look-alike sheet; named range; altered Instructions version; 1,001 rows → rejected |
| Biological metadata | missing dpi / replicate / treatment, fractional or negative or textual dpi, date in replicate, boolean in text field, `paired` without block, `yes`/`1` as paired → rejected; no value is invented |
| Rows | duplicate barcode, duplicate sample name, blank row inside table → rejected; trailing blanks ignored; edge whitespace trimmed |
| Custom profile | IDs without sequences rejected; non-ACGT rejected |
| No execution before Review | import returns rows only; no workspace or upload directory appears; rows still require Validate & Review, which is where duplicate replicates within a condition are rejected |

Assumption worth knowing: a blank `paired` cell means unpaired (documented). Import does not and cannot check that the sheet matches the physical plate.

## 3. Excel output (`PEAnalyzer_Summary.xlsx`)

Parsed with `scripts/xlsx_reader.py` (stdlib ZIP + XML; no openpyxl, no PEAnalyzer code). Expected cells were computed from the metric JSON on disk and from the designed molecules.

| Check | Evidence | Result |
|---|---|---|
| Six columns, exact header text | E04/E05 | as documented |
| Native vs exact are distinct columns with their own numerator/denominator | E04/E05 | e.g. 3A: `180 / 470` and `100 / 300` |
| Target-wide, never copy-routed | E34 (two-copy verified view) | row shows `150 / 385`, `150 / 360`; copy pairs `80 / 200`, `30 / 120` do not occur |
| Sample identity and ordering | E04/E05, E22 | new run: accepted GUI order; recovered run: canonical barcode order, labelled as such |
| Large integers | E35 | `9223372036854775809 / 18446744073709551619` stored as text, exact |
| Fraction vs percentage | E04/E05 | numeric cell holds the stored fraction (0.3829787234042553), number format `0.00%` |
| Null vs zero | E33 | `NOT_ASSESSABLE` → text "Not available" in both cells; genuine `0 / 50` → numeric 0 |
| Export-source integrity | E04/E05 | Definitions sheet lists SHA-256 of each metric file; equal to disk |
| No formulas, macros or external parts | E04/E05 | none |
| Edited workbook | E04/E05, E24 | same session `CHANGED`; fresh session `UNVERIFIED`; science still served |
| Locked workbook | E04/E05 | `~$PEAnalyzer_Summary.xlsx` does not invalidate science (lock file simulated by creating it, not by Excel) |
| Never overwritten | E36, L5 | second write refused; foreign file placed mid-run preserved byte-for-byte; job still `COMPLETED` with warning |
| Recovery-generated workbook | E22 | created, values equal disk |
| Legacy workspaces | E29 | no workbook created by opening |
| Verified result vs presentation artifact | E23 | after restart the state is `CONTENTS_MATCH` with the message that original bytes are not authenticated |

Defect in this area: F-06 (whitespace-padded barcode ID typed by hand → export skipped with a generic warning).

Text cells are written as inline strings. That is valid OOXML and my reader handles it, but: Microsoft Excel rendering, editing, saving and lock-file behaviour — **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED**. openpyxl or a stdlib parser reading the file is not evidence of Excel compatibility.

## 4. Light / Dark theme

Not independently exercised in a browser. Frontend type-check and 62 unit tests (including `theme.test.tsx`) pass on the audited sources, and the bundle is reproducible. Status: **previously reported + unit tests re-executed; no independent visual check.**

## 5. Windows / WSL launcher and Explorer integration

Did subsequent evidence close the gap noted in PR #15? **No.** See F-02 for the document and commit trail. The launcher gained 46 lines after the last qualification record and has no automated test in `tests/`.

What was done here, and its exact standing:

| Item | Standing |
|---|---|
| `run-oneclick.sh` syntax (`bash -n`) | Executed — OK |
| `run-oneclick.sh` on Linux with mocked `docker` and `powershell.exe`, against the installed 1.0.0 wheel | Executed — starts server, creates `v1.0.0` output root, passes the URL to `Start-Process`, SIGTERM stops the server. **Linux simulation only** |
| `reveal_output` on non-WSL Linux | Executed — returns the non-fatal "available on Windows / WSL" message; job stays `COMPLETED` |
| `PEAnalyzer.bat` (Docker Desktop start, 3-minute wait, `wsl.exe -d Ubuntu-24.04`) | **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED** |
| PowerShell interop actually opening the default Windows browser | **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED** |
| `wslpath -w` conversion and `explorer.exe /select,` showing the folder | **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED** (a zero exit code would not prove visibility either) |
| Workbook opened/edited in Microsoft Excel while Results is open | **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED** |
| `/tmp` lease, recovery key and launch logs across `wsl --shutdown` / Windows restart | **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED** |

Observations from reading the scripts: the distribution name `Ubuntu-24.04` is hard-coded in the BAT; the one-click path passes no `--recover-workspace`, so after closing the app an interrupted analysis can be inspected only by launching from a shell with extra arguments; each launch leaves a private token-bearing log in `/tmp` that is never removed.

**Recommendation:** the unverified manual gate should block *Windows desktop release approval* until one recorded smoke test is done on real hardware. It does not affect the validity of results computed by the engine.
