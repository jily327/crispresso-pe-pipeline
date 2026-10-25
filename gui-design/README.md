# M9 GUI/UX design handoff

Design-only study for `jily327/crispresso-pe-pipeline`. No repository code changes, commits, pushes, PRs, merges or GUI implementation. All files live outside the repository.

Read in this order:

1. [GUI_DESIGN_SPEC.md](GUI_DESIGN_SPEC.md) — product contract, 14 screens, scientific boundaries, visual/accessibility rules, implementation gates and final decisions.
2. [SCREEN_FLOW.md](SCREEN_FLOW.md) — step flow, validation timing, mode variants and run/recovery transitions.
3. [FIELD_BACKEND_MAPPING.md](FIELD_BACKEND_MAPPING.md) — each input/result mapped to stable, provisional or proposed backend ownership.
4. [RESULTS_INFORMATION_ARCHITECTURE.md](RESULTS_INFORMATION_ARCHITECTURE.md) — seven result tabs, denominator/exception rules and native output strategy.
5. [ERROR_AND_STATUS_UX.md](ERROR_AND_STATUS_UX.md) — scientific versus operational states, actionable errors and safe resume/force.
6. [TECHNOLOGY_RECOMMENDATION.md](TECHNOLOGY_RECOMMENDATION.md) — local React/TypeScript + FastAPI + one Python worker; alternatives, proposed adapters and deployment tests.
7. [WIREFRAMES.md](WIREFRAMES.md) — ASCII wireframes for every primary screen and key conditional variants.
8. [REFERENCE_REVIEW.md](REFERENCE_REVIEW.md) — supplied screenshots/PDF/native bundle findings and repository-grounded corrections to superficial UI assumptions.

Recommended first implementation: a read-only verified-result viewer and typed Python presentation adapter, followed by setup and supervised run/recovery. All implementation waits for the focused M8.1 re-audit and merge. The nuclease snapshot inspected here is provisional, not a permanent API contract.

`reference-extracts/` contains read-only study evidence and pinned source snapshots, not implementation code. Attachment/source inventories record SHA-256 identities. The shareable design ZIP contains Markdown specifications and small integrity inventories, not the original uploaded native report bundle or repository source snapshots.

Review decisions: approve screen organization/visual density/file-source UX; lock backend-owned scientific semantics; resolve the post-M8.1 capability and annotation/job/artifact API gates before coding. No preference answer is needed to finish this design study.
