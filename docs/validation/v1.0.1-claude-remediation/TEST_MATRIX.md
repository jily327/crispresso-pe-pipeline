# Executed validation

All tests use synthetic data on native Linux (Docker 28.4.0). No Windows, WSL, Docker Desktop, Explorer or Microsoft Excel execution occurred. Python workbook reading is not Microsoft Excel testing.

| Check | Result |
|---|---|
| V-01 before fix: fresh audited wheel + actual installer/launcher/GUI | Expected regression failure: nonempty Core cancellation → daemon absent → `TAMPERED / UNSAFE_PATH` |
| V-02 before fix: daemon inspection from home | Expected regression failure: home mounted read-write |
| Targeted alias/runtime/launcher/recovery/security suite | **129 passed** |
| Fixed fresh-wheel installer/launcher/GUI | **1 passed**; two nonempty cancellations → two `RESUMABLE` previews → verified completion, Exact PE 2/400, two foreign files preserved |
| Full source Python suite | **2,003 passed, 110 skipped, 0 failed** (21 warnings) |
| Full installed-wheel Python suite | **2,003 passed, 110 skipped, 0 failed** (21 warnings) |
| Source genuine probe/generic-parent tests | **5 passed** |
| Installed-wheel genuine probe and CLI ownership | **7 passed** |
| Installed-wheel genuine containment and GUI recovery | **6 passed, 2 parity cases explicitly deselected** in the storage-safe rerun |
| Original multi-container parity | **Not completed**: Docker VFS storage exhaustion; not counted as passed |
| Separate sequential genuine scientific parity | **PE 39/39; nuclease 35/35**; integer truth, statistics, HTTP and PE Excel agree; historical bytes/mtimes and three existing container states unchanged |
| Frontend unit tests | **62 passed**, 9 files |
| Frontend type checking and production build | **Passed** (`tsc --noEmit`; clean build; packaged assets unchanged) |
| Chromium Run/Recovery integration | **6 Run + 8 Recovery passed**; zero failures, skips or flaky retries |
| Packaging | Clean 1.0.1 wheel/sdist; 96 application members match source; repeat under controlled conditions identical; different-umask build differs in ZIP metadata with all member contents equal |
| Windows/WSL/Docker Desktop/Explorer/Microsoft Excel | **NOT VERIFIED IN THIS ENVIRONMENT** |

The 110 default skips are 94 existing backend-gated tests, eight retained genuine Docker cases, seven new runtime cases, and one installed-layout case. The new/retained Docker and installed-layout suites are executed separately as recorded above. The older 94 gated tests were not enabled in this follow-up. The independent audit's 65 enabled backend cases and 318 oracle checks remain historical evidence at its exact candidate; they are not included in these counts.

Genuine backend: CRISPResso2 **2.3.4**, image `pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`; observed local image ID `sha256:518eb6dd6672f4edee8ec464b75d7555cf04ca185ce1ca676d7b930bde24655d`. No version-matching substitute was used. Native Linux bind/lock behavior does not prove cross-WSL Docker Desktop release behavior. The `/mnt/c` stand-in test is only an ordinary Linux directory.

## Intermediate attempts retained

- The original two regressions deliberately failed before production edits; their observations are retained.
- The first new alias unit-test attempt used a filename already created by the existing fixture: **2 failed, 31 passed**. The test alias was renamed; no product assertion was weakened. The corrected targeted suite passed 129.
- A restricted-sandbox targeted invocation stalled at TestClient and was terminated; it is not counted as a completed run. The serial rerun with local-service access passed.
- There is no `npm run typecheck` script. That command failed; the actual `tsc --noEmit` command and the production build's type-check both passed.
- The first wheel-mode experiment changed a file mode alone and got identical bytes under the original umask; its assertion expecting a different archive failed. A fresh build with umask 0002 produced the expected different archive with identical member contents. This supports the limited reproducibility claim rather than a universal one.

Verbose test output, temporary wheel installations, generated reads/workspaces and token-bearing server logs remain outside Git. Committed JSON records outcomes, skip details, daemon observations, image identity and payload hashes. No laboratory data is used.

The first combined genuine run recorded six cases and then ended without a summary during multi-container parity. Subsequent retries exited 120 with empty output logs; retained probe diagnostics identified `Docker create ... no space left on device` in `/var/lib/docker/vfs`. Moving generated build/dependency storage alone was insufficient. Exact record-backed cleanup of two nonrunning test containers restored space. Runtime, containment and browser checks were then run serially; science parity uses the separately documented one-invocation experiment. The original multi-container test remains uncompleted in this environment, rather than being marked green by that substitute.
