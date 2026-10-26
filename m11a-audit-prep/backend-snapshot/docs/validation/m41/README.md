# M4.1 focused production metric remediation

M4.1 addresses the five merge blockers in the independent audit of
`768d4075c2608f3b72293401bb19dce4309f4967`. Package version is **0.4.1**.
The parent remains the audited M4 commit; historical M4 evidence is unchanged.
Target populations, confident copy populations, M3.1.2 routing/geometry and the
single experimental spacer invariant are preserved. No PR, merge or M5 work is
part of this milestone.

Final validation: **556 source tests and 556 fresh installed-wheel tests passed**,
including **28 actual CRISPResso integration tests per environment**, with zero
failures, errors or skips. Both sdist and wheel build successfully. Installed
API/schema/resources and version checks pass; final wheel payload matches the
tested candidate after evidence-only additions.

## Contract changes

- **HIGH-1:** native denominator remains authoritative READS ALIGNED, including
  ambiguous and discarded aligned products. Ordinary allele counts reconcile
  per reference with JSON `counts_total` and the quantification table. Ambiguous
  allele rows reconcile with JSON `class_counts['AMBIGUOUS']`; discarded rows
  reconcile with JSON `counts_discarded` and quantification `Discarded`. The
  complete allele count equals READS ALIGNED. Unknown categories and unexplained
  residuals fail closed. Copy precise accounts for all aligned products and
  excludes ambiguous/discarded rows as unresolved, without biological origin claims.
- **HIGH-2:** target and copy backend input must equal the verified submitted
  population; after-preprocessing counts may be smaller. Input minus that count
  is explicit QC, and after-preprocessing equals aligned plus unaligned. All
  seven anchor integers must agree: input, after preprocessing, delta, aligned,
  unaligned, native numerator and denominator.
- **MEDIUM-1:** `MIN_EXACT_PAIR_OVERLAP = 10`. Enumerate exact suffix/prefix
  overlaps independently of WT/PE reference length. Require one qualifying
  placement and an exactly matching complete reconstructed product. Zero/tiny
  overlaps and multiple repeat placements are unresolved. This threshold is an
  assessability contract, not a biological error probability.
- **MEDIUM-2:** missing/wrong runtime digest blocks only backend-dependent
  metrics. Verified prepared-pair `total_precise_pe` remains independently
  evaluated. All native-only failure cases preserve its original population.
- **MEDIUM-3:** eligible anchors run independently. Execution manifests retain
  process return codes and specific parsing/reconciliation reasons. Result JSON
  includes per-anchor failure codes and metric reasons; there is no surviving
  anchor fallback. Precondition failures do not fabricate missing-anchor reasons.

Three optional integer fields extend each metric record:
`ordinary_classified_aligned_reads`, `ambiguous_aligned_reads`,
`discarded_aligned_reads`. New backend records always supply all three and the
model validates their partition. Old documents without them load as unavailable
(null). `schema_version=1` and `metric_contract_version=m4-v1` are retained: the
four metric identities, populations and READS ALIGNED denominator are preserved.
Strict older readers need the new schema to accept the added fields.

## Real backend results

Every run uses actual digest-pinned CRISPResso2 2.3.4. The variant generator adds
one pair to the unchanged 125-pair M3.1 fixture before demultiplexing, preparation
and routing. Assertions use authoritative artifacts, not synthetic truth counts.

| Target population | Input | After preprocessing | Delta | Aligned | Unaligned | Ordinary | Ambiguous | Discarded | Native | Prepared precise |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| Third allele at edit position 122 | 126 | 126 | 0 | 106 | 20 | 105 | 1 | 0 | 30/106 | 20/55 |
| Non-overlapping 100-nt mates | 126 | 125 | 1 | 105 | 20 | 105 | 0 | 0 | 30/105 | 20/55 |

Both anchors agree on all seven required integers. In both variants target
precise classifies all 126 original prepared pairs, with 71 exclusions.

For the ambiguous variant, copy1 input is 46, after preprocessing 46, aligned
43 = 42 ordinary + 1 ambiguous, unaligned 3, native 18/43 and precise 12/30.
Its exact classifier covers all 43 aligned products, with 13 exclusions. Copy2
remains 30 input, 28 aligned, 2 unaligned, native 12/28 and precise 8/20.
For the preprocessing variant, copy1 is 46 input, 45 after preprocessing,
42 aligned, 3 unaligned, native 18/42 and precise 12/30.

Separate qualification-only `--discard_indel_reads` runs add a deletion inside
the authoritative quantification window (position 145). They produce one actual
DISCARDED row: ambiguous variant 127 input, 107 aligned = 105 ordinary + 1
ambiguous + 1 discarded, native 30/107; preprocessing variant 127 input,
126 after preprocessing, 106 aligned = 105 ordinary + 1 discarded, native 30/106.
This backend option is not added to production target configuration. An initial
exploration using only the original fixture produced no discarded rows because
its deletion was outside the window; the committed regression explicitly puts
the challenge in the window instead of relaxing the assertion.

A real Core invocation with an invalid option returns nonzero at both anchors.
Both attempts are retained and result reasons say `BACKEND_EXECUTION_FAILED`.
A 40-pair full non-exact population yields native 20/40 REPORTABLE while precise
is NOT_ASSESSABLE, never 0%. A `deletion_30_seed11` target yields target native
and precise 20/40 while copy metrics remain BLOCKED for unsupported routing.

## Focused matrices

`exact-overlap.json` records ten input/output cases. The three audited failure
classes (zero-overlap 5-bp insertion, 3-nt repeat insertion, short-repeat WT
deletion) satisfy the old predicate but are now unresolved. Unique WT/PE and
exactly 10-nt controls pass; 9 nt, mate disagreement, extra substitution and
multiple repeat placements do not become exact products. Shared definitions
count a pair once. Historical exact counts remain unchanged. The prior all-A
repeat test now expects NOT_ASSESSABLE with one unresolved product, a necessary
consequence of the new overlap rule, instead of globally escalating a guessed
WT/PE collision.

| Runtime digest | Target native | Target precise | Copy native | Copy precise |
|---|---|---|---|---|
| Correct | REPORTABLE 30/105 | REPORTABLE 20/55 | REPORTABLE | REPORTABLE |
| Missing | BLOCKED: MISSING_REQUIRED_PROVENANCE | REPORTABLE 20/55 | BLOCKED | BLOCKED |
| Wrong | BLOCKED: UNQUALIFIED_BACKEND_RUNTIME | REPORTABLE 20/55 | BLOCKED | BLOCKED |

`native-family-independence.json` also covers missing anchor, anchor dependence,
empty/malformed windows, diagnostic-window overlap, counter mismatch and missing
Core artifact. Every target precise remains 20/55. Both empty encodings have
explicit test coverage. Changing each of the seven comparison integers blocks
anchor invariance.

`anchor-failure-matrix.json` records eight controlled process/artifact experiments:
first anchor nonzero/second succeeds; first succeeds/second nonzero; nonzero and
malformed output; malformed output and success; counter disagreement and success;
ambiguity reconciliation disagreement and success; launch failure and success;
reference mismatch and success. Each eligible anchor is
attempted and no numeric result is fabricated. These are supplemental fault
injection tests, clearly distinguished from the real nonzero-exit artifacts.
Runtime precondition tests verify no backend launches and no false missing-anchor
reason. A separate executable-version rejection records `not_started`, a null
return code and `UNQUALIFIED_BACKEND_RUNTIME` for target and copy backend metrics. Known failures appear in result JSON, not only execution logs.

## Historical regression

| Population | Input | Aligned | Unaligned | Native | Precise |
|---|---:|---:|---:|---|---|
| M3 all prepared | 350 | 330 | 20 | 120/330 | 100/230 |
| M3.1 all prepared | 125 | 105 | 20 | 30/105 | 20/55 |
| Confident copy1 | 45 | 42 | 3 | 18/42 | 12/30 |
| Confident copy2 | 30 | 28 | 2 | 12/28 | 8/20 |
| Combined confident, diagnostic reconciliation only | 75 | 70 | 5 | 30/70 | 20/50 |
| Historical Pooled copy1, unqualified production routing | 211 | 199 | 12 | 72/199 | 60/140 |
| Historical Pooled copy2, unqualified production routing | 139 | 131 | 8 | 48/131 | 40/90 |

The fresh indel grid remains **36 designs: 13 allowed, 23 BLOCKED**. No routing
or geometry implementation change is made. Updated older comparator test fixtures
supply the two newly required preprocessing comparison integers. Their tests
and historical expected numerical results are retained. The anchor-dependence
fixture now also reconciles its allele counts, so it tests independently valid
anchors with different native results under the stronger parser.

## Reproduction

Use Python 3.12 and `requirements-dev.lock`. Required image:

```text
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
```

Use direct entrypoints: the image's default `CRISPResso2_router.py` can mask child
nonzero exits. The established wrappers invoke the executable directly inside a
running container, mount `/workspace` and `/tmp`, and preserve `$PWD`. The actual
wrapper text, image/content identity and probes are recorded in `runtime.json`.
For a new runtime, replace IMAGE below with the full digest above:

```sh
IMAGE=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
docker pull "$IMAGE"
docker run -d --name m311-runtime --user "$(id -u):$(id -g)" \
  -v /workspace:/workspace -v /tmp:/tmp --entrypoint /bin/sleep "$IMAGE" infinity
mkdir -p /workspace/m311-tools
cat > /workspace/m311-tools/CRISPResso <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec docker exec --workdir "$PWD" m311-runtime "/CRISPResso2/.pixi/envs/default/bin/$(basename "$0")" "$@"
SH
cp /workspace/m311-tools/CRISPResso /workspace/m311-tools/CRISPRessoPooled
cp /workspace/m311-tools/CRISPResso /workspace/m311-tools/samtools
chmod +x /workspace/m311-tools/CRISPResso /workspace/m311-tools/CRISPRessoPooled /workspace/m311-tools/samtools
python -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-build-isolation --no-deps -e .
bash docs/validation/m41/run-tests.sh "$PWD/.venv/bin/python" /workspace/m41-source-final
.venv/bin/python -m build --no-isolation --outdir /workspace/m41-candidate2
python -m venv /workspace/m41-final-wheel-env
/workspace/m41-final-wheel-env/bin/pip install -r requirements-dev.lock
/workspace/m41-final-wheel-env/bin/pip install --no-deps /workspace/m41-candidate2/crispresso_pe_pipeline-0.4.1-py3-none-any.whl
mkdir -p /workspace/m41-final-wheel-suite
tar -xzf /workspace/m41-candidate2/crispresso_pe_pipeline-0.4.1.tar.gz -C /workspace/m41-final-wheel-suite
cd /workspace/m41-final-wheel-suite/crispresso_pe_pipeline-0.4.1
bash docs/validation/m41/run-tests.sh /workspace/m41-final-wheel-env/bin/python /workspace/m41-wheel-final
```

Every result directory must be new. Run the installed-wheel suite from the
extracted sdist, without source PYTHONPATH. Confirm `peanalyzer.__file__` points
inside the fresh venv's site-packages. Tests check installed API, schema equality,
barcode/profile resources and version 0.4.1. Capture the source pytest temporary
root before running another suite; in this run it was `/tmp/pytest-of-agent/pytest-19`.
From the source checkout, collect evidence with:

```sh
.venv/bin/python docs/validation/m41/collect_evidence.py \
  --source /workspace/m41-source-final --wheel /workspace/m41-wheel-final \
  --pytest-root /tmp/pytest-of-agent/pytest-19 --dist /workspace/m41-candidate2
```

Evidence is text-only: raw child JSON, mapping/quantification tables, extracted
alleles and execution provenance accompany the new results. No FASTQ/BAM/ZIP is
committed. Original artifact hashes remain in result JSON; extraction does not
replace them. The evidence bundle is in the sdist, not the installed wheel.
After evidence-only additions, rebuild and compare the complete wheel payload
with `tested-wheel-payload.json` before publication.

## Remaining scope limits

Copy results remain routing-conditioned, including possible insertion-associated
PE depletion. No correction or biological origin attribution is introduced.
The fixed overlap requirement can conservatively exclude short/repetitive real
products. Backend-dependent metrics still require pinned runtime provenance.
The audit's LOW schema/summary semantics, broad target unresolved taxonomy,
per-copy backend-option consistency and unverified `running_info.args` remain
out of scope. Coordinated artifact forgery, remote attestation, argv[0]
certification and transactional result publication are not redesigned.
