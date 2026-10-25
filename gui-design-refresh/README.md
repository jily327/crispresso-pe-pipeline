# M9.1 contract refresh handoff

Decision: **VALID WITH NARROW REFRESH**. Main inspected: `9e9a51fb20e56a3421fdfa156375170cd6b257dc`, package 0.8.0. The approved architecture is unchanged. M8/M8.1 were read for interface reconciliation, not re-audited. No GUI/application implementation, commit, push, PR or merge was performed.

## Active deliverables

1. [GUI_DESIGN_REFRESH.md](GUI_DESIGN_REFRESH.md) — authoritative refresh decision, 12 stable contract groups, change classifications, error wording and correction register for historical companions.
2. [FINAL_FIELD_BACKEND_MAPPING.md](FINAL_FIELD_BACKEND_MAPPING.md) — current fields, exact metric names/paths, 58-argument contract, zero-exception requirement, TIGR representation and ownership.
3. [FINAL_CAPABILITY_GAP_MATRIX.md](FINAL_CAPABILITY_GAP_MATRIX.md) — 17 capabilities classified against real Python APIs, with no implied HTTP endpoints.
4. [M10_IMPLEMENTATION_BOUNDARY.md](M10_IMPLEMENTATION_BOUNDARY.md) — exact base/branch proposal, five read-only screens, safe detail panels, adapter work, deferrals, tests and acceptance criteria.
5. [GUI_DESIGN_SPEC_FINAL.md](GUI_DESIGN_SPEC_FINAL.md) — narrow final copy of the approved overall specification.
6. [RESULTS_INFORMATION_ARCHITECTURE_FINAL.md](RESULTS_INFORMATION_ARCHITECTURE_FINAL.md) — narrow final copy of the approved result architecture.

Start M10 from `9e9a51fb20e56a3421fdfa156375170cd6b257dc` on proposed `feat/m10-verified-result-viewer`. Open existing completed M7 workspaces and implement Overview, Samples, QC, Statistics and Provenance. Do not implement setup, scientific execution, cancellation, upload, force actions or native HTML rendering in that first milestone.

## Historical and evidence material

`historical-design/` holds exact reviewed documents from `329a24bdbda61f1a981b9902456c4e13169348f7` for comparison. They are not newly revised specs; active refresh documents take precedence over their old provisional statements. `NARROW_DESIGN_CHANGES.diff` shows only the two necessary revised copies. Visual-design and PE-overview sections were preserved verbatim.

`source-extracts/` contains immutable merged source/document extracts. `SOURCE_INVENTORY.json` records exact source revisions and SHA-256s. `QUALIFIED_ARGUMENT_REFERENCE.json` records a static extraction of 56 fixed plus 2 target-dependent fields, not a new validator. `PE_MAPPING_CONTINUITY.json` records source continuity supporting unchanged GUI contracts, not audit results. `REFRESH_REVIEW_CHECKS.json` records documentation consistency and branch-preservation checks.

The downloadable ZIP includes the six active deliverables, this index, historical comparison documents, narrow diff and small evidence inventories. The inspected source extracts remain available in the external study directory; the package does not include application implementation changes or biological datasets.
