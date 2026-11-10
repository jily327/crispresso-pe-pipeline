# PEAnalyzer v1.0.0 — Final Independent Audit: Executive Summary

**Candidate:** `jily327/crispresso-pe-pipeline`, `main` @ `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`, package version `1.0.0` (verified before work began).
**Auditor role:** independent, read-only. No production file, test, algorithm or branch other than this artifact branch was changed.
**Verdict:** `PEANALYZER V1.0.0 FINAL AUDIT: PASS WITH CONDITIONS` — see `V1_FINAL_RELEASE_DECISION.md`.

## The short version

**The numbers are right.** I built synthetic sequencing experiments in which I knew exactly how many molecules of each kind were in each sample, ran them through the real application with a real CRISPResso2 2.3.4, and compared what came out with what went in. Both primary prime-editing fractions, the nuclease indel fractions, the statistics, the on-screen values and the Excel summary agreed with the independent expectation in every case. Unavailable values were never shown as zero, ambiguous reads were never forced into a homeolog, and I could not get the application to mark anything "verified" that was not, delete anything it did not own, or report a cancelled or broken run as complete.

**Two things do not hold up, and neither is about a number.**

1. **Recovery does not work where it is most needed (F-01, MAJOR).** If a run is cancelled or fails *while CRISPResso is running* — the long stage — it cannot be resumed by any option, in the GUI or CLI. The GUI first says "resumable with force" and then, whichever force you choose, says "TAMPERED". The data were not tampered with; the application simply refuses to remove its own half-written output. You must start again in a new folder. A harmless cousin (F-04): after a reboot clears `/tmp`, an untouched interrupted workspace can also be labelled "TAMPERED".
2. **Nobody has run the Windows desktop (F-02, MAJOR).** The release is presented as a desktop release started from a `.bat` file. The project's own records say Windows, WSL, Explorer and Microsoft Excel were never available for testing, and the launcher script was changed again after the last qualification with no test. I had no Windows either. Every such check is recorded as **NOT VERIFIED — REAL WINDOWS DESKTOP REQUIRED**.

**One practical trap (F-03, MINOR):** a single sample with no reads (a failed PCR well) stops the whole plate's analysis, and because of item 1 the folder cannot then be resumed.

## Findings at a glance

| Severity | Count | IDs |
|---|---|---|
| BLOCKING | 0 | — |
| MAJOR | 2 | F-01 recovery dead end; F-02 Windows desktop gate unverified |
| MINOR | 4 | F-03 one bad sample aborts the plate; F-04 false "TAMPERED" after key regeneration; F-05 runtime digest declared not checked; F-06 whitespace-padded barcode ID breaks the optional export |
| INFO | 9 | F-07 … F-15 (see `V1_RELEASE_RISK_REGISTER.md`) |

The most consequential *scientific* observation is informational (F-07): CRISPResso itself reports a compact equal-length deletion+insertion as substitutions, so such events are missing from `indel_fraction`. PEAnalyzer reproduces the backend faithfully, as its contract says; users should read `any_modification_fraction` too.

## What was actually done

| Area | Work | Result |
|---|---|---|
| Identity | SHA and version check | Matches the requested candidate |
| Code reading | Scientific core, workflow, recovery, GUI server, v0.9/v1.0 additions, React Results page | Data-flow map in `V1_CROSS_LAYER_AUDIT.md` |
| PE science | 4-sample single-copy and three 2-copy experiments, real backend, independent oracle | All counts match (E03, E07, E08) |
| Nuclease science | TIGR-Tas W2 and W4, real backend, independent parser | All ten fractions match; window geometry confirmed (E06) |
| Cross-layer | Excel import → Review → Run → verified view → workbook over real HTTP | 98/98 checks (E04–E05) |
| Lifecycle | Mutation before/after acceptance, concurrent runs, cancel during Core, cancel at completion, killed supervisor, export collision | All controlled except recovery after cancel-during-Core |
| Recovery security | Forged manifest/plan/receipt, deleted receipt, planted file, stale preview, key loss | All refused; no deletion; one false label |
| Library | Genuine 0.8.0 / 0.9.0 / 1.0.0 workspaces plus forged, incomplete, relocated and symlinked decoys | 9/9 controlled; old workspaces byte- and metadata-identical afterwards |
| Excel in / out | 57 adversarial import workbooks; workbook cells recomputed independently | 57/57; null ≠ zero; target-wide; exact big integers; never overwritten |
| Packaging | Wheel from clean export; frontend rebuilt from source | 93/93 files identical; bundle byte-identical |
| Regression | Full source suite once; frontend unit tests; product real-backend integration tests on the wheel | See below |

## Regression and packaging evidence

* **Independently executed:** full source test suite — **1934 passed, 92 skipped, 0 failed** (skips are tests gated on a backend environment variable); frontend type-check clean and **62/62** unit tests; wheel build and file-level comparison; frontend rebuild.
* **Product real-backend integration tests on the installed wheel (M4, M4.1, M4.2, M4.2.1, M4.2.2, M7, M8, M8.1):** **65 passed, 0 failed** in 10 min 44 s against the bioconda 2.3.4 backend (`evidence/logs/wheel_real_backend_integration.log`). These are the project's own tests, so they corroborate rather than independently validate; they do show the installed wheel drives a real backend correctly.
* **Test retention:** between 0.9.0 and 1.0.0 `git diff` on `tests/` shows 493 added lines and 4 deleted lines, the deletions being version-string updates (`0.9.0` → `1.0.0`); no unconditional skip/xfail markers exist. The one place where tests were bent to behaviour is historical and is the root of F-01: after M11C.1 the orphan-force fixtures were changed to *empty* directories.
* **Previously reported, not re-executed:** Playwright browser suites, containment fault-injection, routing/repeat qualification grids, pinned-image qualification, real-data Excel parity.

## Limits of this audit — read before relying on it

* Backend was a genuine CRISPResso2 2.3.4 but a bioconda build with fastp 1.4.0, **not** the pinned Docker image. (The one runtime-sensitive constant I could test — the 11-nt merge boundary — reproduced.)
* All reads were error-free synthetic reads. No real dataset was analysed.
* Only substitution-type prime edits were used; insertion/deletion edit designs rest on earlier evidence.
* The GUI was driven through its HTTP API, not through a browser.
* No Windows, WSL or Microsoft Excel.
* Race conditions were each exercised a few times, not statistically.
* I made and corrected several harness mistakes; they are listed in `V1_ADVERSARIAL_TEST_EVIDENCE.md`.

## Conditions attached to the verdict

* **C1** One recorded smoke test on real Windows + WSL + Excel before the Windows desktop is called approved.
* **C2** Fix or prominently release-note the recovery limitation and correct the misleading "TAMPERED" label and the contradictory sentence in `docs/m7-workflow.md`.
* **C3** Ship three operating instructions: drop empty wells before running; the runtime digest is your declaration, so actually use the pinned image; read `any_modification_fraction` next to `indel_fraction`.

## Documents

| File | Content |
|---|---|
| `V1_FINAL_RELEASE_DECISION.md` | Verdict, confidence by dimension, conditions, counter-arguments |
| `V1_RELEASE_RISK_REGISTER.md` | Every finding with location, proof, impact, confidence, remediation |
| `V1_SCIENTIFIC_INTEGRITY_AUDIT.md` | Metric definitions challenged against designed truth |
| `V1_CROSS_LAYER_AUDIT.md` | Data-flow map, end-to-end trace, lifecycle scenarios |
| `V1_RECOVERY_SECURITY_AUDIT.md` | Trust model, forgery experiments, destructive-operation safety |
| `V1_DESKTOP_EXCEL_AUDIT.md` | Library, Excel import/export, Windows gate |
| `V1_ADVERSARIAL_TEST_EVIDENCE.md` | Experiment table, environment, reproduction, harness corrections |
| `scripts/`, `evidence/` | Runnable harness and machine-readable results |
