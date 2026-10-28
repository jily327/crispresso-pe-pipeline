# Setup findings and limits

Studied candidate: `232d380c73f456181bade0e5c11138c8c5ec6570`.
This is setup preparation, not the final independent M11C.2 audit. No production
source was edited. No installation BLOCKER or MAJOR product defect was observed
in the tested clean Ubuntu and fresh Linux wheel paths.

| ID | Class | Finding / evidence | Action |
|---|---|---|---|
| S1 | INFO — untested deployment boundary | No Windows host/WSL kernel was available. Ubuntu 24.04 nonroot installation, Linux loopback, native Core and Linux Chromium passed. Docker Desktop setup, actual Windows browser forwarding and `/mnt/c` semantics were not measured. | Verify the printed localhost URL on the target WSL2 PC; use Linux-side data. This is not a Windows acceptance claim. |
| S2 | INFO — known recovery limitation | Current recovery key lives under `/tmp/peanalyzer-UID-recovery/`; loss can remove destructive recovery authorization for incomplete workspaces. | Prominent retention warning; no unsupported manual key backup or migration procedure. |
| S3 | MINOR — historical documentation context | Earlier M10/M11A/M11B milestone documents contain historical deferred lifecycle language. Current M11C docs and launcher implement Run and inspected recovery. | This runbook cites current M11C behavior; historical docs were not rewritten. |
| S4 | INFO — provisioning prerequisite | Existing qualification uses a full native extraction of the pinned image. Docker is needed to obtain files, not to run GUI scientific jobs. | Tested extraction script retains the bundled Pixi environment; no substitute pip/Conda/runtime installation asserted qualified. |
| S5 | INFO — infrastructure event | First extraction hit ENOSPC while Docker vfs storage and the new copy coexisted. After reclaiming unrelated rebuildable test venvs, the same extraction completed and both modes passed. | Budget setup disk space in addition to real data. This was not a product failure and prompted no production fix. |
| S6 | INFO — harness event | Clean Ubuntu base already had UID 1000 (`ubuntu`); a test setup attempt to create another UID 1000 failed. The clean installation was then performed as existing nonroot `ubuntu`. | End-user WSL guide uses the normal Ubuntu account; no application workaround. |
| S7 | INFO — scope | Completed-workspace recovery inspection passed read-only checks. Full cancellation/interrupted force-recovery, all 1,910 prior tests and real-data qualification were not rerun in this setup study. | Rely on the separate independent M11C.2 audit for those gates; this package does not supersede it. |

Severity convention: BLOCKER prevents the prescribed installation/use; MAJOR is
a material supported-path defect; MINOR is a bounded usability/documentation
problem; INFO is a prerequisite, known limit or untested boundary. No visual
polish item is represented as a scientific blocker.

The clean Ubuntu OS had no Node executable. Bundled frontend assets loaded and
real PE/nuclease workflows completed. A separate Linux browser test driver used
Node/Playwright outside the application venv; those are not end-user dependencies.

If the candidate advances, recheck the package against the final approved SHA
before practical use. Nothing here authorizes real-data use before audit/merge.
