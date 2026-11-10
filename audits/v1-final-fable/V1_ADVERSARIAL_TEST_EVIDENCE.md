# PEAnalyzer v1.0.0 — Adversarial Integration Experiments and Evidence

Candidate `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`. All inputs are synthetic (seeded PRNG); no real or sensitive data. Scripts are in `scripts/`, machine-readable results in `evidence/`.

## Environment actually used

| Item | Value |
|---|---|
| Python | 3.12, dependencies from `requirements-dev.lock` + `requirements-gui.lock` |
| Product under test | editable install of the audited commit (GUI experiments); wheel built from a clean `git archive` (packaging and backend integration) |
| Backend | CRISPResso2 **2.3.4** from bioconda, **fastp 1.4.0** — a real 2.3.4, but **not** the pinned image `pinellolab/crispresso2@sha256:b7e7…` (no Docker daemon). The qualified digest was *declared* so that the reportable code path executed; see F-05 |
| Platform | Linux container; no Windows, no WSL, no Microsoft Excel |
| GUI driving | Real `python -m peanalyzer.gui` server, real supervised worker, loopback HTTP with token/Origin exactly as the browser sends. No Playwright/Chromium run |

## Classification of evidence

* **Independently executed** — every experiment in the table below; the full source test suite once (1934 passed, 92 skipped because they are gated on a backend environment variable, 0 failed); frontend type-check + 62 unit tests; frontend rebuild; wheel build/install comparison; the product's own real-backend integration tests against the installed wheel (status at the end of this file).
* **Previously reported, not re-executed** — Playwright browser suites; containment fault injection (census/reap failure, unkillable children); the M3.1/M4.2 routing and repeat-period qualification grids; ALSW real-data Excel parity; pinned-image qualification.
* **Structurally reviewed only** — read-through reconstruction, tolerance-policy families, paired statistics, W1/W3 nuclease windows, theme behaviour, library discovery limits, upload size bounds.
* **Not tested** — anything requiring Windows/WSL/Excel; hostile same-account writer; full coordinated rewrite of all provenance; multi-gigabyte inputs.

## Experiments

For every experiment the expected outcome was fixed before the product was called — in the design truth file, in the script's assertions, or in the scenario record — and the table restates it. "Distinguisher" is what separates a product defect from a harness error. For E40 my own prior expectation was that the workflow would abort; the "expected" column states the behaviour a laboratory would want, which is why it is a finding rather than a surprise.

| ID | Claimed invariant | Failure hypothesis | Independent expected outcome | Minimal reproduction | Distinguisher | Outcome |
|---|---|---|---|---|---|---|
| E03 | Exact PE = exact PE/(exact WT+exact PE); native = Prime-edited/aligned; statistics on samples | Wrong denominator, Modified% conflation, reads as replicates | Counts equal designed molecules; native equals my parse of CRISPResso files; n = samples | `make_pe_experiment.py` → `peanalyzer run` → `verify_pe_workspace.py` | Designed counts are fixed in `truth.json` before the run | 76/76 |
| E04–E05 | The same fact survives Import → Review → Run → view → Excel | A layer recomputes, reorders or reformats a value | Disk = API = workbook = truth; order as accepted | `exp_gui_happy.py` | Workbook read by an independent ZIP/XML parser | 98/98 |
| E06 | Nuclease classes are exclusive; ins+del counted once; window geometry W2/W4 | Double counting; wrong window; wrong denominator | Ten fractions equal my recomputation; `include_idxs` equals s+4…s+13 / s−10…s+27 | `make_nuclease_experiment.py`, `verify_nuclease_workspace.py` | Same molecules must change class between W2 and W4 as geometry dictates | 36/36 each; **F-07** observed |
| E07 | Ambiguous reads are never forced into a copy; target metric independent of routing | Low-quality or mosaic reads assigned; target numerator loses quarantined reads | 65 quarantined with the two designed reasons; target exact 150/360 | `make_multicopy_experiment.py routable` | Per-reason quarantine counts were designed in advance | As expected |
| E08 | Blocked/unobservable copy never contaminates the target metric | Copy status leaks; partial denominator reported | Copy metrics BLOCKED/null; target REPORTABLE (blocked) or NOT_ASSESSABLE/null (length-divergent) | `… blocked`, `… lengthdiff` | Null vs number is unambiguous in JSON | As expected; **F-03** observed |
| E09 | Excel import is strict transport; nothing invented; nothing executed | Formula/odd cell accepted, leading zero lost silently, malformed file crashes | 57 predetermined accept/reject outcomes | `exp_excel_import.py` | Expectation coded before call | 57/57 |
| E10 (L1) | Run executes reviewed bytes | Post-Review mutation accepted | 409, no job, no workspace | `exp_gui_lifecycle.py L1…` | Workspace directory absence | Controlled |
| E11 (L2) | Post-acceptance mutation cannot yield a published result | Later mutation unnoticed | FAILED, no marker, no registration | `… L2…` | Completion marker absence | Controlled |
| E12 (L3a) | Cancel during Core contains every backend process | Children survive; marker remains | CANCELLED after CONTAINMENT_CONFIRMED; zero backend processes | `… L3…` | `/proc` scan for argv with the staged input name | Controlled |
| E13 (L3b) | A run cancelled during the backend stage is recoverable after inspection | Own partial output treated as foreign; no executable path | An executable preview exists | same | Three force families tried; two CLI workspaces reproduce | **DEFECT — F-01** |
| E14 (L5) | Export failure cannot falsify or block science; nothing overwritten | Foreign workbook overwritten or reported verified | COMPLETED + warning; state not UNCHANGED; bytes intact | `… L5…` | Byte comparison of the planted file | Controlled |
| E15 (L6/E17) | Cancel/complete race gives one terminal state | Double terminal state or hidden success | One terminal event; marker and registration consistent | `exp_recovery.py` E17 | Event list filtered to job-terminal events | Controlled |
| E16 (L4) | Dead supervisor never becomes COMPLETED | Exit treated as success | FAILED, final | `… L4…` | Job state polled again after orphans exit | Controlled; **F-11** |
| E18a–d | Forged metadata cannot authorise recovery | Agreeing JSON accepted as ownership | TAMPERED/UNSUPPORTED, not executable | `exp_recovery.py` | Files restored byte-for-byte after each case; clean baseline is RESUMABLE | Controlled |
| E19 | Force never deletes unowned content | Planted file deleted | Refused; file intact | same | File content read back | Controlled |
| E20 | A stale preview cannot be executed | Confirmation uses old hash | 409 RECOVERY_PLAN_CHANGED | same | Job count unchanged | Controlled |
| E21 | Key loss fails closed and is reported truthfully | Falls back to unsigned JSON, or misreports | UNSUPPORTED in both states | same | Original key restored → RESUMABLE again (workspace was never modified) | Fail-closed ✔; **F-04** (false TAMPERED) |
| E22 | Resume reuses verified stages and publishes verified results | Re-executes or publishes unverified | 14 REUSED, COMPLETED, workbook = disk | same | Event statuses | Controlled |
| E23–E24 | Workbook integrity is never over-claimed | Edited workbook shown as matching | CONTENTS_MATCH after restart; CHANGED/UNVERIFIED after edit | same | Two server sessions | Controlled |
| E25–E32 | Library: no science, no writes, detected ≠ verified, versions from provenance | Old workspace modified; forged/incomplete/symlinked entry trusted | See desktop report | `exp_library.py` | Genuine 0.8.0/0.9.0 workspaces built by those releases; full before/after fingerprint | 9/9 controlled |
| E33–E36 | Workbook: null ≠ zero, target-wide, exact integers, no overwrite | Zero-fill, copy metric used, float precision loss | See desktop report | `exp_excel_edges.py` | Independent reader; designed truth | 4/4 controlled |
| E37 | Wheel equals source; assets intact | Stale or missing files; bundle not from source | 93/93 files identical; rebuilt bundle byte-identical | commands in supplementary evidence | SHA-256 comparison | As expected |
| E38 | WSL launcher logic | Script error; server orphaned | Starts, hands URL to PowerShell, stops on signal | supplementary evidence | Mock call log | Linux simulation only — **not** Windows verification |
| E39 | Backend merge boundary constant holds on this build | Boundary differs → state-dependent survival unguarded | Overlap 10 rejected, 11 accepted | supplementary `E13_backend_merge_boundary` | Seven overlaps, 100 pairs each | 11 nt, as coded |
| E40 | One bad sample does not prevent results for the others | Whole workflow aborts | Completed with that sample non-reportable | supplementary `E12_plate…` | Good sample computed correctly before the abort | **Aborts — F-03** |

## Harness errors I made and corrected

Stating these because they bear on how much to trust the rest:

1. First GUI draft omitted barcode sequences → server correctly returned `INVALID`. Fixed by importing samples through the Excel endpoint.
2. A GUI submission was refused `WORKER_BUSY` because the repository test suite was running on the same account and holds the same host lease (became F-13).
3. Backend-process detection matched my own shell command line, producing a false "processes survived" and a cancel sent too early. Fixed to match real backend argv; scenario re-run.
4. A predicate counted stage-level `COMPLETED` events as job-terminal. Re-evaluated from raw data and re-run as E17; the evidence file keeps the original verdict alongside the correction.
5. My XLSX reader initially did not recognise inline strings or built-in format id 10 (`0.00%`). Both were reader gaps, not product defects.
6. Installing 0.8.0 with a shared `PYTHONPATH` made old code report version 1.0.0. Rebuilt as fully isolated environments before any historical workspace was generated.
7. I briefly suspected the launcher left an orphaned server; a timed re-test showed shutdown completes within a second. Not reported as a finding.

## Reproducing

```bash
# backend: any CRISPResso2 2.3.4 on PATH (the audit used bioconda crispresso2=2.3.4)
python scripts/make_pe_experiment.py IN
peanalyzer run --r1 IN/pool_R1.fastq.gz --r2 IN/pool_R2.fastq.gz --samples IN/samples.csv \
  --targets IN/targets.csv --config IN/config.yaml --output WS --crispresso CRISPResso \
  --runtime-digest <digest> --contrasts IN/contrasts.yaml
python scripts/verify_pe_workspace.py WS IN/truth.json out.json
python scripts/exp_gui_lifecycle.py "$(which python)" "$(which CRISPResso)" IN WORK out.json
```

The GUI scripts start and stop their own servers on ports 8811–8871 and must not run concurrently with the repository test suite (shared lease).

## Product real-backend integration tests against the installed wheel

`tests/test_m4_integration.py`, `m41`, `m42`, `m421`, `m422`, `m7`, `m8`, `m81` were run against the installed wheel with the bioconda backend: **65 passed, 0 failed** (10 min 44 s). Log: `evidence/logs/wheel_real_backend_integration.log`. These are the project's own assertions executed by me; they are corroboration, not an independent oracle.
