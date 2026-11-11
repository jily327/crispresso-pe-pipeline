# Executed validation matrix

Qualification is Linux-only. All backend runs use synthetic inputs. No Windows, WSL or Microsoft Excel execution is claimed. Logs reside under `/tmp/pe-logs` in the qualification workspace; focused portable evidence is in `evidence/`.

| Check | Executed result |
|---|---|
| Production/audit identities | Exact expected SHAs, fetched before branch creation |
| Baseline nonempty backend failure, key regeneration, padded export | Independently reproduced; repeated with correct v1.0.0 distribution metadata in evidence/baseline-reproductions-corrected-version.json |
| Final full source suite (`.venv/bin/python -m pytest -q`) | **1,977 passed, 93 skipped, 0 failed**, 21 warnings, 730.49s |
| Final focused recovery/credential/publication regressions | **55 passed** in 73.29s; final full source/wheel runs also include these tests |
| Genuine interrupted CRISPResso regression (`V101_DOCKER_INTEGRATION=1`) | **1 passed** in 21.81s; nonempty backend output, two failed attempts, actual recovery inspection, verified successful retry |
| Final installed-wheel v1.0.1 genuine-backend regressions | **2 passed**, 1 warning, 209.06s; partial-write/nonzero retry and actual GUI cancellation/recovery using an owner-death-aware container guard |
| Real PE/nuclease HTTP integration (`M10_INTEGRATION=1`, `test_gui_integration.py`) | **2 passed** in 93.69s |
| Independent PE oracle, v1.0.0 and v1.0.1 | **76 passed / 0 failed each** |
| Independent HTTP/Excel/baseline comparison | **59 passed / 0 failed** |
| Independent nuclease W2 and W4 oracle | **36 passed / 0 failed per version per window**; direct science equality in evidence/nuclease-parity.json |
| Historical completed v1.0.0 open using v1.0.1 | Verified; all stored bytes and mtimes unchanged |
| Frontend unit tests (`npm test`) | **62 passed**, 9 files |
| Type-check and asset build (`npm run build`) | Passed (`tsc --noEmit`, Vite, build identity record) |
| Version-matching unqualified executable provenance | Passed in the default suite using a version-printing test executable; this is a presentation/security regression, not a genuine bioconda backend run |
| Viewer/Setup/desktop Playwright | **20 passed** (Chromium on Linux) |
| Run Playwright | **6 passed**, including real PE/nuclease run, stale Review, live reload, cancellation, worker-busy and failure presentation |
| Recovery Playwright | **8 passed**; initial 7 passed / 1 harness failure because restart environment variables were omitted |
| Practical Playwright | **3 passed**, real uploads, workbook validation and verified analysis |
| Final full installed-wheel suite | **1,977 passed, 94 skipped, 0 failed**, 21 warnings, 655.61s |
| Existing real-backend matrix on installed wheel | Initial complete command: **87 passed, 1 failed, 4 setup errors**, 1,977 deselected, 1 warning, 1,042.52s. All five affected cases passed on the corrected child-command rerun (**5 passed**, 45.74s). All **92 distinct existing backend tests** ultimately passed. |
| Clean wheel + sdist | Version **1.0.1**; all **94 package files** match the fully tested wheel/source; final clean-wheel CLI/version smoke **5 passed**. Both launcher files and all regression tests are included in the source archive. Wheel hashes and dependency checks are in evidence/packaging.json and evidence/dependency-lock-check.json. |
| Actual Windows BAT / default browser / Explorer / Excel / WSL shutdown | **NOT VERIFIED IN THIS ENVIRONMENT**; separate user-reported success and final-byte checklist in WINDOWS_SMOKE_TEST.md |

## Skips and failed intermediate attempts

The 93 default-suite skips are the existing opt-in backend tests plus the new Docker interruption test. They are not counted as executed backend passes. The exact skip inventory is retained in the source/wheel logs and the portable summary. Explicit backend commands are listed separately; a default-suite skip remains a skip in that run even when exercised later.

The initial full source run had 1,957 passed, 93 skipped and 8 failed in 763.33s. All eight failures were obsolete TAMPERED expectations for foreign files; refusal and no-deletion assertions remained intact. Those expectations were corrected to UNSUPPORTED, and the final complete run above passed.

Initial targeted development runs are not hidden: one sandbox run rejected key ancestor ownership because the sandbox maps system directories to UID 65534; descriptor-based traversal now checks writability and authenticates the private leaf owner instead. A subsequent targeted run exposed expected-label/schema updates and one SOFTWARE_CHANGED guard while code was still being edited. The final full run used stable production code. A concurrently launched recovery-only run returned ACTIVE during the full process-safety suite (9 failures); its unchanged assertions passed in the serial 55-test run. All subsequent lease-dependent suites run serially.

The first browser recovery run omitted the suite's required M11C_E2E_PYTHON and M11C_E2E_SERVER variables. The final test killed its server, then failed in Node spawn before testing restart. This was a harness configuration error, not a product recovery result. The corrected run uses a fresh fixture directory and both variables; the failed log is preserved.

The first scientific comparison attempted byte equality on root-bound population IDs and failed as expected. The retained comparison excludes only explicitly documented identity fields, and still compares every scientific value. The early baseline distribution metadata issue is documented in README.md; the release oracle uses the corrected isolated v1.0.0 installation.

The installed-wheel environment imports PEAnalyzer exclusively from `/tmp/pe-wheel-env/lib/python3.12/site-packages/peanalyzer`; dependency packages are shared read-only from the source virtualenv via a `.pth` path. It is not an independently resolved dependency environment. The wheel itself is installed with `--no-index --no-deps`, and its package location/version are asserted before execution.

A final lifecycle review added two legacy-resume persistence tests, then three missing-directory/interrupted-force tests and two concurrent/crashed key-creation tests. All **55** final edge/recovery tests passed in 73.29s. A superseded wheel run was intentionally interrupted at 441 passed / 9 skipped; a superseded source run was intentionally interrupted at 509 passed / 12 skipped. Neither is counted as a completed final suite. Final full runs are executed after rebuilding the wheel with these changes.

All ordinary browser suites completed: Viewer/Setup/desktop **20 passed**, Run **6 passed**, Recovery **8 passed** after correcting the restart harness, Practical **3 passed**. These are Linux Chromium results, not Windows tests. The last production changes after these browser runs concern credentials and interrupted force removal; final Python/backend suites exercise those paths.

A second opt-in genuine-backend regression was added for GUI cancellation during nonempty Core execution. It was added after the final source suite's collection, so that source command's default skip count does not include it; the later wheel collection and explicitly enabled backend run do. No backend pass is inferred from either default-suite skip count.

The first three two-test genuine-backend attempts each had **1 passed / 1 failed** (94.60s, 116.51s, 107.06s). The first two asserted disappearance of the container record; the third checked actual process state and confirmed Docker `State.Running == true` after GUI cancellation. Plain CLI signal proxying and a host-side SIGTERM cleanup handler were insufficient: workflow unwind can kill the direct wrapper before its handler runs. Each test finalizer stopped only its recorded container. The final qualification wrapper uses a container-side guard watching a kernel lease held by the local wrapper, so abrupt owner death also terminates the backend. These failed deployment experiments are retained, not counted as product passes. The final rerun is recorded separately above. This does not qualify arbitrary external laboratory wrappers or Windows/WSL lock-sharing behavior.

## Final backend coverage and environment correction

The full legacy backend selection executed 92 cases. Its four M3 setup errors and one M31 failure came from passing the host Docker-wrapper path as CRISPRessoPooled's child command inside the container. The supported environment override `M3_CHILD_CORE_COMMAND=CRISPResso` selects the actual executable inside that same qualified image. The five affected cases passed unchanged after this configuration correction. No production code or scientific expectation was changed for the rerun. The initial failed command remains in the matrix.

Together with the two v1.0.1 genuine-backend regressions, **94 distinct backend-gated cases passed, with zero remaining backend skips or unresolved test failures**. This is an aggregate of the full run and targeted corrected reruns, not a claim that one full backend command was green. `evidence/test-results.json` retains the counts, skip inventory and log hashes for the individual runs. All 16 opt-in flags in `evidence/backend-configuration.json` were enabled. The source and default-wheel skips remain skips in those commands.

All 41 packages in requirements-dev.lock and requirements-gui.lock match the qualification environment. The final clean wheel was installed into another virtualenv and imported from that installation for its five CLI/version smoke checks. Like the full wheel environment, it shares the locked dependency directory read-only; this is not an independent dependency resolution. Final production package bytes are identical across source, the fully tested wheel and the clean wheel. Later changes to the separately gated Docker regression were executed in its explicit two-test run; no production code changed after the full source/wheel suites.
