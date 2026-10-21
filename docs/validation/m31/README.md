# M3.1 evidence index

The source branch starts at M3 commit
`e7e67ccef5792682fcf61344e3423f1a2f80d3e3`. These are actual synthetic outputs,
not mocked backend results. See [interpretation and limitations](../../m31-routing.md).

- `m3_baseline/`: original child mapping and quantification statistics, parsed
  integer metrics and independently attributed synthetic exclusions. Original
  M3 JSON/allele evidence remains under `../m3/baseline/` unchanged.
- `qualification/`: new 125-pair fixture, truth, per-read evidence ledger,
  geometry, confusion matrix, quality/retention/quarantine tables, and selected
  actual Core outputs for each confident copy. All 75 confident pairs enter
  Core; all 50 quarantine pairs remain outside copy denominators.
- `edited_diagnostic/`: matched full-coverage and restricted-coverage WT/PE
  experiment with an intended edit affecting diagnostic 40; 40 assigned and
  10 symmetrically quarantined. This is a focused bias experiment, not a claim
  that arbitrary edited-diagnostic mosaics are qualified.
- `orientation/`: actual faithful reverse-only spacer rejection, exact TSV,
  command manifest and stderr; no sequence-check override or guide rescue.
- `historical_bowtie2_distributions.json`: M3 AS−XS and MAPQ counts for comparison.
  New Biopython routing has no MAPQ/AS/XS, and retains its own alignment scores.
- `runtime_versions.json`, `image_inspection.json`: observed external runtime.
- `validation_results.json`, `source_hashes.json`: checks and evidence-derivation
  source identity. Execution manifests record the parent Git commit plus dirty
  state honestly; tests preceded the M3.1 commit. Window/metric evidence was
  also independently re-parsed from actual child artifacts after implementation.

Actual Core/Pooled runtime:

```text
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
CRISPResso 2.3.4; CRISPRessoPooled 2.3.4
Bowtie2 2.5.5; samtools 1.23.1; fastp 1.3.3
```

Exact argv/cwd/input hashes and timestamps are retained in each execution JSON.
The environment-local Docker launcher is documented in `../m3/runtime_launcher.txt`.
Full outputs remain outside the repository at `/workspace/validation/m31/`.
No FASTQs, BAMs, large output trees or unpublished biological sequences are
included. Raw backend text preserves its original whitespace.

The actual complete integration command was:

```sh
M3_INTEGRATION=1 M31_INTEGRATION=1 \
M3_RESULTS_DIR='/workspace/validation/m31/m3 regression' \
M31_RESULTS_DIR='/workspace/validation/m31/final qualification' \
M3_CORE_EXECUTABLE=/workspace/validation/m3/bin/CRISPResso \
M3_POOLED_EXECUTABLE=/workspace/validation/m3/bin/CRISPRessoPooled \
M3_SAMTOOLS_EXECUTABLE=/workspace/validation/m3/bin/samtools \
M3_CHILD_CORE_COMMAND=CRISPResso \
M31_RUNTIME_IMAGE='pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c' \
/workspace/peanalyzer-venv/bin/python -m pytest -q -m crispresso_integration
```

Result: **8 passed**. Historical unsafe Pooled routing and guide rejection are
expected regression outcomes, not scientific passes. The new explicit router's
qualification is PASS only for its tested geometry and recorded policy.

After final preflight changes the four M3.1 tests were executed again, and the
`qualification/` and `orientation/` evidence here comes from that final run:

```sh
M31_INTEGRATION=1 \
M31_RESULTS_DIR='/workspace/validation/m31/release qualification' \
M3_CORE_EXECUTABLE=/workspace/validation/m3/bin/CRISPResso \
M3_POOLED_EXECUTABLE=/workspace/validation/m3/bin/CRISPRessoPooled \
M3_CHILD_CORE_COMMAND=CRISPResso \
M31_RUNTIME_IMAGE='pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c' \
/workspace/peanalyzer-venv/bin/python -m pytest -q tests/test_m31_integration.py
```

Result: **4 passed in 49.78 s**. Final ordinary and installed-wheel suites each
passed **325 tests**; the wheel's eight external-runtime tests were explicitly
skipped in its ordinary unit run and executed separately above.

Every fraction retains its numerator and denominator. Native and exact-haplotype
fractions are distinct; neither their difference nor its direction establishes
editing quality. Backend unaligned failure reasons remain unknown unless proven.
