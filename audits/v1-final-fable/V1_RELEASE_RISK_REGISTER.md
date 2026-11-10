# PEAnalyzer v1.0.0 — Release Risk Register

Candidate: `main` @ `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`, package version `1.0.0` (identity verified before work started; `origin/main` and local `HEAD` both resolved to this SHA).

Findings are ranked by the consequence a laboratory would actually experience. "Confirmed" means reproduced here against the real application; "source-level" means proven by reading code but not executed. Nothing speculative is classified as a confirmed defect.

| ID | Severity | One-line statement | Status |
|---|---|---|---|
| F-01 | **MAJOR** | A run interrupted or failed inside the scientific backend (metrics) stage can never be resumed in place, and the GUI then labels PEAnalyzer's own partial output `TAMPERED` | Confirmed (GUI + CLI) |
| F-02 | **MAJOR** | The Windows/WSL/Microsoft Excel desktop gate is still unverified, and the WSL launcher was changed after the last recorded qualification with no automated test | Confirmed by evidence review; NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED |
| F-03 | MINOR | One unusable sample (zero-read well, or reads the backend cannot merge) aborts the whole plate's workflow | Confirmed |
| F-04 | MINOR | After the per-account recovery key is regenerated, an untouched workspace is reported `TAMPERED` instead of "unanchored"; the key lives in `/tmp` | Confirmed |
| F-05 | MINOR | The "qualified runtime digest" is asserted for any executable that prints `2.3.4`; the GUI hard-codes it and displays it as provenance | Confirmed |
| F-06 | MINOR | A barcode ID typed with surrounding whitespace makes the optional Excel export fail | Unit-reproduced + source-level |
| F-07 | INFO | Compact equal-length deletion+insertion events are called substitution-only by CRISPResso and so are absent from `indel_fraction` | Confirmed (backend behaviour) |
| F-08 | INFO | "Verified" means internally hash-consistent with present source files, not authenticated | Documented; partial forgeries tested |
| F-09 | INFO | The CRISPResso Prime-edited-reference numerator legitimately includes imperfect edits | Confirmed; documented |
| F-10 | INFO | Demultiplexing reads forward barcodes only on R1 and reverse only on R2 | Source-level |
| F-11 | INFO | If the supervisor is SIGKILLed, science continues unsupervised to completion and the server must be restarted | Confirmed; documented |
| F-12 | INFO | Any unrelated new file closes the verified view; an interrupted no-op CLI resume can delete a valid completion marker | Confirmed / source-level |
| F-13 | INFO | The product's own test suite takes the production host lease and key directory | Confirmed |
| F-14 | INFO | The 4-nt alternative-overlap rule makes a small fraction of designs unassessable | Source-level |
| F-15 | INFO | GUI statistics are descriptive only; version labels come from distribution metadata | Source-level / observed |

No BLOCKING finding was identified: across every experiment I could not make PEAnalyzer report a wrong number, mark unverified data verified, delete a file it did not provably own, or publish a cancelled/corrupted run as complete.

---

## F-01 — MAJOR — Recovery dead end after interruption in the backend stage

* **Location:** `src/peanalyzer/workflow_recovery.py::check_removal_contents` (line 40, raises at 54); `src/peanalyzer/metrics/production.py::run_metrics` (line 387, `output.mkdir(parents=True)` writes directly into the final path, unlike demux/analysis/routing which stage into `.incomplete-*` and rename); `src/peanalyzer/workflow.py::execute_workflow` (line 640, `ORPHANED_STAGE_OUTPUT`); `src/peanalyzer/gui/recovery.py::RecoveryStore._view` (lines 147–149 map `ORPHANED_STAGE_OUTPUT → RESUMABLE_WITH_FORCE` and `FOREIGN_CONTENT_PRESENT → TAMPERED`).
* **Invariant affected:** `docs/m11c-recovery.md` — "Cancellation leaves a partial workspace for a new inspection"; `RESUMABLE_WITH_FORCE` — "An explicit closure is required"; `docs/m7-workflow.md` line 183 — "A partial M4 output directory remains an orphan **until explicitly forced**."
* **Reproduction (GUI, real CRISPResso 2.3.4):** `scripts/exp_gui_lifecycle.py` scenario L3. Submit a run, wait until a real backend process exists, cancel. Result: job `CANCELLED` correctly, zero backend processes, no completion marker (all good). Then **Inspect Recovery** → `RESUMABLE_WITH_FORCE`, `executable=false`, reason `ORPHANED_STAGE_OUTPUT [metrics::1A::T1]`. Preview with force `metrics`, `routing` or `all` → each returns `TAMPERED`, `executable=false`, reason `FOREIGN_CONTENT_PRESENT … metrics/1A/T1/comparator/copy1/execution.json, input_R1.fastq.gz …`. Evidence: `evidence/E10_E16_gui_lifecycle.json` → `L3b_recover_after_cancel_during_core`.
* **Reproduction (CLI):** two independent failed workspaces (backend exit on unmergeable reads; zero-read sample). `--resume` → `ORPHANED_STAGE_OUTPUT`; `--resume --force metrics|routing|all` → `FOREIGN_CONTENT_PRESENT`. Evidence: `evidence/E07_E08_E11_E13_E37_E38_supplementary.json` → `E11…`, `E12…resume_attempts`.
* **Actual vs expected:** Expected: some inspected path makes the workspace executable again (reusing demux/analysis/routing). Actual: no product path exists; the only remedies are a brand-new workspace (repeat demultiplexing of the raw pool) or manual deletion of `metrics/<sample>/<target>` outside the product.
* **Why earlier audits missed it:** this is a boundary effect between two individually correct fixes. M11C.1 (BLOCKING W2) correctly forbade deleting content without an ownership record. The force fixtures were then changed to *empty* orphans (`docs/validation/m11c1/README.md` lines 38–39: "Existing orphan-force fixtures use empty orphans rather than authorizing deletion of files without ownership records"). Real M4 output is never empty, so the realistic case stopped being exercised. A cancel sent *before* the backend creates its directory does resume cleanly (I observed that too), which is why a fast test passes.
* **Impact:** Operational, not scientific — it fails closed and nothing false is published. But the metrics stage is the long-running one and the only stage that calls an external program, so it is where interruptions and failures realistically occur. The headline M11C feature does not work for its primary scenario, the classification shown ("TAMPERED") wrongly tells a user their data were interfered with, and one active document states the opposite of actual behaviour.
* **Confidence:** High (reproduced through HTTP API and CLI, three workspaces).
* **Minimal remediation:** make M4 publication atomic like the other stages (build in a sibling `.incomplete-*` directory, rename on success, remove on unwind) so an interrupted stage leaves nothing at the owned path; or write an authenticated in-progress inventory. Independently: map "unmanifested content inside this workflow's own unfinished stage path" to a distinct, non-accusatory classification; correct `docs/m7-workflow.md` line 183; restore a regression test with a **non-empty** orphan.

## F-02 — MAJOR — Windows/WSL/Excel desktop gate unverified

* **Location:** `desktop/PEAnalyzer.bat`, `desktop/run-oneclick.sh`, `src/peanalyzer/gui/desktop.py::reveal_output`, `src/peanalyzer/gui/summary_workbook.py`.
* **Evidence reviewed:** `docs/validation/desktop-1.0/README.md` lines 107–111 ("Actual Windows/WSL Explorer and BAT operation was **not manually tested**"); `docs/validation/desktop-1.0-remediation/README.md` lines 65–67 ("Actual Windows, WSL and Microsoft Excel were unavailable"). The two commits after the last qualification record (`383369a`, `bb15e65`) add 46 lines to `run-oneclick.sh` and a doc paragraph; they contain no evidence. `grep` finds no test in `tests/` that references `run-oneclick.sh` or `PEAnalyzer.bat`. **Subsequent evidence does not close the gap.**
* **What I could and could not do:** A Linux simulation with mocked `docker` and `powershell.exe` ran the shipped script against the installed wheel: it created `~/PEAnalyzer-analyses/v1.0.0`, started the server, extracted the URL and passed exactly `-NoProfile -NonInteractive -Command Start-Process -FilePath '<url>'`; SIGTERM to the launcher stopped the server. `bash -n` passes. `reveal_output` returned the documented non-fatal "available on Windows / WSL" message. The workbook was parsed by an independent ZIP/XML reader. **None of this is Windows verification.**
  * `PEAnalyzer.bat` execution, Docker Desktop start-up wait, `wsl.exe -d Ubuntu-24.04`: **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED**
  * `wslpath -w` + `explorer.exe /select,` and actual Explorer visibility: **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED**
  * Windows default-browser launch through PowerShell interop: **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED**
  * Microsoft Excel opening `PEAnalyzer_Summary.xlsx` (inline-string cells, `0.00%` format, freeze panes, auto-filter), editing it, and the `~$` lock-file lifecycle as Excel really produces it: **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED**
  * Behaviour of `/tmp` (lease, recovery key, launch logs) across WSL shutdown: **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED**
* **Impact:** the release is described as a desktop release whose user entry point is a Windows batch file. That entry point has never been executed by anyone on record. Failure there is not a scientific risk (science runs in WSL exactly as tested), but it is a first-five-minutes failure for the intended user.
* **Should it block?** It should block *Windows desktop release approval*. It should not block the scientific engine, CLI or Linux/WSL-shell use of the GUI.
* **Remediation:** one scripted manual smoke test on a real Windows 11 + WSL2 Ubuntu-24.04 + Docker Desktop + Excel machine, recorded with screenshots: BAT cold start; browser auto-open; upload → Review → Run on a small pool; Explorer reveal; open/edit/close the workbook in Excel while Results is open; close and relaunch; Windows restart then attempt recovery.

## F-03 — MINOR — One unusable sample aborts the whole workflow

* **Location:** `src/peanalyzer/workflow.py::validate_stage` lines 296–297 (`execution_failures.json` non-empty → `BACKEND_EXECUTION_FAILED`).
* **Reproduction:** two-sample sheet where `2A` has no reads in the pool. `1A` computes correctly (80/200 exact and native). For `2A` the M4 record is scientifically right (`BLOCKED`/`NOT_ASSESSABLE`, null counts), but the workflow exits 2, publishes no statistics/report/completion, and (F-01) cannot be resumed. Same outcome when every pair has <11 nt mate overlap. Evidence: supplementary `E12`, `E13`.
* **Actual vs expected:** By documented design ("Backend execution failures … stop construction; none become biological zeros"), so this is not a correctness defect. Operationally, a 96-well plate with one failed PCR well yields no result at all until the well is removed from the sheet and everything is rerun.
* **Remediation:** treat "backend refused an empty/unalignable population" as a publishable non-reportable sample state, distinct from an infrastructure failure; at minimum state the workaround in the user documentation and surface the offending sample ID prominently in the GUI.

## F-04 — MINOR — False `TAMPERED` after key regeneration

* **Location:** `src/peanalyzer/workflow_integrity.py::key_path` (line 20, `/tmp/peanalyzer-<uid>-recovery/key`), `authenticate` (line 87).
* **Reproduction:** `scripts/exp_recovery.py` E21. Remove the key → `UNSUPPORTED / UNANCHORED_RECOVERY_OWNERSHIP` (correct, fail-closed). Let any new run mint a key (`signing_key(create=True)`) → the same byte-identical workspace is now `TAMPERED / TAMPERED_RECOVERY_INTEGRITY`. Restore the original key → `RESUMABLE`.
* **Impact:** never unsafe; misleading. `/tmp` is routinely cleared at boot on systemd distributions, so the typical sequence "machine restarts mid-run → user starts another analysis → later inspects the interrupted one" will accuse the user of tampering. Whether WSL clears `/tmp` on the target machines is unverified here.
* **Remediation:** store a key identifier in the receipt and report a key mismatch as unanchored; keep the key under `~/.local/share/peanalyzer/` (mode 0700/0600) rather than `/tmp`.

## F-05 — MINOR — Runtime digest is declared, never checked, and shown as fact

* **Location:** `src/peanalyzer/gui/execution.py::RuntimeSettings.qualified_digest` (lines 16–22); `src/peanalyzer/backend/pooled.py::resolve_executable` (version-string probe only).
* **Proof:** every result in this audit was produced by a bioconda CRISPResso2 2.3.4 with **fastp 1.4.0** (the pinned image carries fastp 1.3.3), yet all are `REPORTABLE` and carry `pinellolab/crispresso2@sha256:b7e7971a…` in provenance and in the Results screen. `executable_sha256` is the hash of the wrapper script, not of the image.
* **Mitigating evidence:** the one runtime-sensitive constant I could test, the mate-merge boundary, reproduced exactly on this different build (overlap 10 → no reads; 11 → all merged; `MIN_PINNED_BACKEND_OVERLAP = 11`). `docs/m4-metrics.md` states the digest is "declared execution provenance, not remote attestation".
* **Impact:** a mis-deployed backend is recorded as the qualified one. Bounded, because version 2.3.4 is enforced and artifacts are reconciled.
* **Remediation:** label the value "declared runtime" in UI/workbook, and record observed `fastp --version` plus, for a Docker wrapper, the image digest reported by the daemon.

## F-06 — MINOR — Whitespace-padded barcode ID breaks the optional export

* **Location:** `src/peanalyzer/gui/jobs.py` line 297 (`sample_order` taken from raw draft text); `summary_workbook.py::ordered_samples` lines 26–28. The React form does not trim; Excel import does.
* **Proof:** `DraftSample(barcode_id=' 4A ')` keeps the spaces; authoritative validation strips them, so the run is valid and identified as `4A`; `ordered_samples(plan, [' 4A '])` raises `ValueError`. The export is skipped with the generic warning. Science is unaffected. Not run end-to-end.
* **Remediation:** build the order from the compiled (normalized) sample list.

## F-07 — INFO — Compact delins are not indels to the backend

Synthetic molecule: 3-bp deletion immediately followed by a 3-bp insertion (net 0) inside the TIGR W2 window. CRISPResso aligns it as six mismatches; PEAnalyzer faithfully reports `substitution_only`. Result: designed 165 indel-bearing molecules, reported `indel_fraction` 150/510; the other 15 appear under `substitution_only` and `any_modification`. Well-separated insertion+deletion events are counted once and binned at net 0 as documented (W4 run: 18/18). This is the consequence of the explicit contract "CRISPResso is the authoritative variant caller"; users should read `any_modification_fraction` alongside `indel_fraction`. Evidence: `E06_nuclease_W2.json`, `E06_nuclease_W4.json`.

## F-08 — INFO — Meaning of "Verified"

Viewer verification proves hash-consistency of plan → stage manifests → outputs → final manifest, plus byte identity of recorded source files. It is not authentication; the HMAC receipt is used only for recovery ownership. Every *partial* edit I made was caught (metric JSON byte flip → `CORRUPTED_STAGE_OUTPUT`; unknown file → view closed). I did not build a full coordinated rewrite of all provenance; the product explicitly excludes that threat. Users should not treat "Verified" as tamper-proof against a person with write access.

## F-09 — INFO — Native PE includes imperfect edits

In sample 3A, 20 molecules carrying one intended base and a *wrong* base at the second site were assigned by CRISPResso to the Prime-edited reference, so they are in the native numerator (180/470) and correctly absent from Exact intended PE (100/300). This is the documented definition and exactly why the two metrics are shown side by side.

## F-10 — INFO — Fixed barcode orientation

`demux.py` looks for forward barcodes at R1 offset 0 and reverse barcodes at R2 offset 0 only. If a library is prepared non-directionally, pairs in the opposite orientation fall into `no_barcode_match`. That costs yield, not accuracy (orientation is independent of edit state), and the assignment percentage in the demux summary exposes it. Not tested on real data.

## F-11 — INFO — Supervisor SIGKILL

Killing the supervisor process: job `FAILED / CANCELLATION_INCOMPLETE`, never upgraded; new submissions refused (`WORKER_BUSY`) until server restart; the orphaned scientific child ran to completion and wrote a valid completion marker with no workbook. That workspace later appears in the library as "Detected — verification required". Matches the documentation.

## F-12 — INFO — Fragile view; marker deletion on interrupted no-op resume

(a) Any new unrelated file inside an open workspace closes the verified view until re-open (observed with `stray.txt`); desktop tools that drop files into folders will trigger it. (b) Source-level only: `execute_workflow`'s failure handler unlinks `workflow_manifest.json` once `workspace_owned` is set, which for a no-op `--resume` of a *completed* workspace is before the final check; an interrupt in that window removes a valid marker (recoverable by another resume if the key exists). Not reproduced.

## F-13 — INFO — Tests share production lease

While the repository's test suite ran, a real GUI submission on the same account was refused with `WORKER_BUSY`: tests use `/tmp/peanalyzer-<uid>-science/worker.lease` and the real key directory. Do not run the test suite on a machine with a live analysis.

## F-14 — INFO — Conservative reconstruction

`observability.reconstruct` rejects a pair if any shorter suffix/prefix coincidence of ≥4 nt exists besides the true overlap. For fixed-length reads this is a property of the design, so roughly 0.5 % of amplicon/read-length combinations will be reported `NOT_ASSESSABLE` for Exact PE regardless of data quality. Fail-closed; state-symmetry guards prevent bias.

## F-15 — INFO — Statistics scope and labels

The GUI always runs descriptive `summarize`; exact contrasts exist only through the CLI. With two replicates per group the smallest attainable two-sided p is 1/3 (confirmed), which users should expect. The displayed version comes from installed distribution metadata; mixing environments can mislabel code (I produced a 0.8.0 tree reporting "1.0.0" by an environment mistake of my own, then corrected it). The stage signature's code hash still distinguishes the builds.
