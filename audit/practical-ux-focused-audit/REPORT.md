# Practical-UX focused independent audit — evidence

Audit evidence only. No implementation change, never a merge base for the candidate.

| Identity | SHA |
|---|---|
| Baseline main | `72e0f86a495e079cab2ae50d2796e7a3423c78af` |
| Frozen audit kit (`artifacts/practical-ux-audit-prep`) | `8055d81160e9fa1cc4a5f4da79b3c5e9c97d3a0a` |
| Candidate (`feat/practical-ux-inputs`) | `04b9f8852a7af08ea8e8d216c63c8c55726f92ec` |

Verdict: **PASS WITH MINOR FINDINGS — SAFE TO MERGE**

## Independently measured gates
- Frozen-core tripwire: 0/73 BYTE_IDENTICAL and 0/1,501 HISTORICAL changed; 16 review-category files reviewed hunk by hunk.
- Frozen adapter contract (`audit_candidate.py`, 66 tests) bound by `kit/auditor_candidate_binding.py`:
  - 57 in-process tests passed (FASTQ, ownership, interruption, staging/symlink, Excel matrix, catalog probe, streaming).
  - The 9 presentation/version/execution tests are bound to the browser and execution harnesses instead.
- Extra upload matrix (`results/extra-uploads.json`).
- Two-size streaming: RSS rose 6.7 MB for 49 MiB and 7.0 MB for 133 MiB; maximum read 256 KiB.
- Manual vs Excel parity: compiled science, files, preview and identities equal for all 5 accepted cases.
- Legacy vs upload execution parity (real native Core): PE and nuclease science equal. Every byte difference is a path, timestamp or derived hash.
- Source suite: 1,972 passed. Fresh-wheel suite: 1,972 passed (`site-packages` imports). 0 failures, errors or skips; 90 integrations.
- Frontend: 56 passed. tsc clean. The bundle rebuild is byte-identical.
- Browser (Linux Chromium 1194, actual File inputs):
  - Retained suites 35/35 source and 35/35 wheel.
  - Independent spec 16/16 source and 16/16 wheel.
- Packaging: 94 members identical across direct, sdist→wheel and clean-clone builds; 89 package files identical to source; version 0.9.0 in all authorities.

## Findings
- **MINOR-1:** an official template re-saved by LibreOffice is rejected (`docProps/custom.xml` is not on the ZIP allowlist). The failure is closed and clearly reported.
- **MINOR-2:** copy-cohort metrics reuse the primary labels. In Statistics and in sample detail they lack the copy qualifier.
- INFO items are listed in the final audit report.
