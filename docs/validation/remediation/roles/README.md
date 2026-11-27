# SCI-04 — Biological replicate eligibility

**Audited counterexample reproduced.** Remote PR 17 and the detached candidate both
resolved to `2f567b88628eeb287bacc9febf3b65b3a00bfc7a`. The original GPT
`controls.py` produced the erroneous PE mean, pooled fraction, SD and used IDs
in `frozen-oracle.json`. The audit's separate four-sample `control_workflow.py`
ran genuine CRISPResso2 2.3.4 and completed scientific verification on that
candidate. Both treatment and PCR control entered the biological sample list.

| Check | Audited | Corrected |
| --- | --- | --- |
| Treatment A eligible replicates | 2 | 1 |
| Unweighted mean | 0.50 | 0.10 |
| Sample SD | 0.565685424949238 | Unavailable |
| Pooled integer counts | 91/110 | 1/10 |
| Two-per-arm contrast | Reportable | Not assessable, null effect, p and q |
| Populated PCR sample retained individually | 90/100 | 90/100 |

The known counts and before/after expectation were frozen in `28c574a`.
The role policy and reports landed in `55e79be`; signed plan/observation
design checks and explicit zero-read workbook tests landed in `5308abc`.
Existing saved results retain their historical summary when loaded. New
contrasts on their stored observations use the corrected design. Technical
replicates remain individual QC observations. Biological negative controls can
contribute one observation per independent replicate.

## Independent checks

The final package evidence identifies the source revision, tested wheel SHA-256
and installed package code SHA-256. `collect.py` rejects a different installed
package or wheel. It independently sums the native allele row multiplicities
for single-reference nuclease reads with at least one insertion or deletion
and checks all four integer pairs against the input truth. It then executes the
public statistics entry point on those same genuine measurements. The raw
FASTQs are unchanged. For the public PE fixture, the audit's exact permutation
and BH reference calculations also passed.

The installed role regression suite covers experimental, biological negative,
legacy PCR negative, explicit PCR negative, no-template and technical roles.
It exercises missing or repeated paired blocks, shared technical replicate IDs,
contrasts and site series. The on-disk workbook checks confirm that literal
booleans and integer counts survive export and that a zero-read control has a
blank fraction. A biological negative/control group retains the genuine 0.50
mean and 91/110 pooled counts when both samples are biological.

The installed `81c21c8` wheel completed a fresh four-sample run of the original
synthetic SCI-04 fixture. All four native allele tables gave the expected
indel/aligned counts in barcode order, 1/10, 90/100, 2/10 and 3/10. The
verified treatment A summary used only `bio1`. The signed PCR observation had
fraction 0.90 and was ineligible for biological statistics in the viewer
projection and the saved Excel workbook. The contrast reported
`INSUFFICIENT_BIOLOGICAL_REPLICATES`, with effect, p and q unavailable.
`genuine-native-recount.json` binds the workbook, control TSV, workflow
manifest and native tables to this run. Reproduce the comparison with
the installed candidate Python.

```text
python collect.py ORIGINAL_GENERATED_AUDIT_WORKSPACE output.json --package-root FROZEN_PACKAGE --corrected-workspace FRESH_CORRECTED_WORKSPACE
```

## Failure and interruption history

- On the detached audited SHA the new known-truth PE regression failed as
  expected because the mean included the declared PCR sample. The unmodified
  audit reproduction independently gave the same wrong inventory.
- During integration, competing git index ownership caused one transient
  commit failure. A normal retry succeeded without discarding another
  contributor's work.
- The frozen intermediate `55e79be` statistics, roles, sample/workbook and
  reporting suites passed 602 tests. Its first fresh four-sample native
  attempt timed out during the bc002 backend version probe after 60 seconds.
- Intermediate `5308abc` referenced `measurement_exports` before the GUI
  module landed. Seven of 18 tests failed in this checkout, and its fresh
  native attempt stopped at bc001. An earlier working-tree run for roles and
  metadata passed 68 cases. It is not evidence for the incomplete checkout.
- After `measurement_exports` landed, the installed `81c21c8` role suite
  passed 19 tests with zero skips. The first four-sample native run was paused
  for the shared Docker lock during a bc001 version probe. It timed out.
  The fresh run held the shared lock from launch and passed workflow verification,
  native allele recount, viewer projection and saved workbook checks. Earlier
  failed workspaces were kept separate.
