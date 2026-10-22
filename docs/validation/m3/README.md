# Recorded M3 synthetic experiment

**ROUTING GATE: FAIL.** These are selected outputs of actual CRISPResso2/Pooled
2.3.4 runs on 2026-10-21 UTC, not mocked outputs. The full interpretation and
API contracts are in [the M3 document](../../m3-backend-validation.md).

`baseline/` contains full synthetic WT/PE/guide sequences, independent truth,
the generated Pooled TSV, execution/preparation manifests, stdout/stderr,
upstream Pooled and child JSON, extracted child allele tables, per-read routing
scores, class counts, confusion matrix and summary. `guide_mismatch/` contains
the faithful altered-copy design, unchanged experimental guide, execution
failure, upstream error log and explicit unsupported result. `runtime_versions.json`
records real probes. `runtime_launcher.txt` is the exact environment-local shim
used to run the external image; it is documentation, not an installed adapter.

No FASTQ, BAM, container, vendored backend source, real read or unpublished target
is included. Full intermediates remain outside the repository under
`/workspace/validation/m3/final tests/`. The BAM and SAM hashes identify the
artifacts used to generate the committed per-read tables. Re-execution regenerates
them. BAM/container logs can contain run paths/timestamps, so their byte hashes
need not match across runs; target design and routing results are deterministic
for this tested runtime. The formal runs reproduced the same 23/17 tie split.

Execution manifests honestly record the base Git commit plus `git_dirty: true`,
because integration validation preceded the M3 commit. `source_hashes.json`
identifies the M3 Python implementation tested. The eventual Git commit contains
that implementation and this evidence; no execution provenance was rewritten to
claim it ran from a later commit.

The exact final real-backend test command was:

```sh
M3_INTEGRATION=1 \
M3_RESULTS_DIR='/workspace/validation/m3/final tests' \
M3_CORE_EXECUTABLE=/workspace/validation/m3/bin/CRISPResso \
M3_POOLED_EXECUTABLE=/workspace/validation/m3/bin/CRISPRessoPooled \
M3_SAMTOOLS_EXECUTABLE=/workspace/validation/m3/bin/samtools \
M3_CHILD_CORE_COMMAND=CRISPResso \
/workspace/peanalyzer-venv/bin/python -m pytest -q -m crispresso_integration
```

The launcher uses this image (the `v2.3.4` tag was pulled, then execution pinned
to the immutable digest):

```text
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
```

Every exact Pooled argv/cwd is in its `execution.json`; version probes are nested
there. `baseline/samtools_execution.json` records the exact extraction command
and SAM hash. Upstream child commands and its actual Bowtie2/fastp invocations
are retained in stderr and/or upstream JSON. Paths in backend logs refer to the
original safe scratch directory; the corresponding relative files were copied
to the external `backend/` directory before scratch removal.

Recorded checks:

- 267 unit tests pass, covering the unchanged M1/M2/M2.1 behaviors and 50 new M3
  cases. Two old literal version expectations were updated to package 0.3.0.
- Four real-backend tests pass by correctly detecting the unsafe routing and
  rejected guide configuration, while validating informative routing and WT/PE
  references. These tests do not certify scientific gate success.
- sdist/wheel build, fresh wheel installation, resource loading and independent
  archive verification are checked separately. See `validation_results.json`.
- No informative read cross-routed; the list of such IDs is empty. Forty
  non-informative reads were assigned once each with tied best/alternate scores.
- Baseline copy1 and copy2 have separate WT and intended PE references; exact
  synthetic precise-PE allele counts are 60 and 40. These are smoke-test counts,
  not final biological efficiency metrics.
- Mismatch child exit 6 and Pooled exit 255 are retained without guide rewriting,
  Flexiguides or sequence-check overrides.

M4 remains blocked until an explicit ambiguity-preserving routing design and
guide-mismatch strategy pass independent scientific review and validation.
