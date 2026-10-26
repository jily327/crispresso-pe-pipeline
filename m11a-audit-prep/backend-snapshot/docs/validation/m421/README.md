# M4.2.1 focused post-audit remediation

Package **0.4.3** closes NEW-A (copy-dependent target selection), NEW-B
(policy requests destroying canonical output), and the qualified periodic
reconstruction residual. The direct parent is audited M4.2 commit
`db49e23f0881bed35a24747587275463949c764d`; main remains
`550df70f9f9627c7218b9f047d0b6bf3023b8d25`. This is one focused implementation
commit, with no PR, merge, history rewrite, new metric family or M5 work.
Historical evidence under m4, m41 and m42 is unchanged. Routing and geometry
implementations are unchanged.

Both the source and fresh installed-wheel suites pass **698 tests** with zero
failures, errors or skips. Each suite contains **59 integration-marked cases**:
**58 backend-executing cases** and **one deliberate preflight-only case**. The
three new cross-copy native regressions execute actual pinned Core; the
copy-specific-repeat production test correctly blocks before launching Core.
The audited 55 backend cases remain covered. This distinction avoids counting
a prevented backend launch as an actual analysis execution.

## NEW-A: target composition at the actual read geometry

The target compares every copy × state candidate at each observed R1/R2 length
class. Existing within-copy WT/PE symmetry remains necessary; cross-copy symmetry
is an additional target-only check. Different absolute lengths alone do not block.

A copy-dependent backend eligibility difference blocks target native with
`COPY_DEPENDENT_BACKEND_MERGEABILITY`, before production launches a selected target
backend population. A copy-dependent exact eligibility difference excludes the
entire length class from both target exact and target family evidence with
`COPY_DEPENDENT_PRODUCT_OBSERVABILITY`. If no qualified exact products remain,
exact is NOT_ASSESSABLE with a null fraction. Equally unobservable copies cannot
create a denominator. Mixed-length populations retain eligible classes and record
all excluded counts. Copy metrics still compare only their own WT/PE candidates.

The independent reproduction has copy lengths 240 and 234 nt and a shared
substitution edit. Copy1 contributes 18 WT + 2 PE; copy2 contributes 2 WT + 18 PE.
The pooled truth is 20/40. Raw comparator executions are deliberately retained
as diagnostics even when the production metric refuses their selected fractions.

| R1 + R2 | Raw native per anchor | Target native | Target exact | Target family, policies 0 and 1 |
|---|---|---|---|---|
| 150 + 150 | 20/40 | REPORTABLE 20/40 | REPORTABLE 20/40 | REPORTABLE 20/40 |
| 125 + 125 | 18/20 | BLOCKED: copy-dependent mergeability | REPORTABLE 20/40 | REPORTABLE 20/40 |
| 124 + 125 | 18/20 | BLOCKED: copy-dependent mergeability | NOT_ASSESSABLE; all 40 excluded | NOT_ASSESSABLE; all 40 excluded |

The independently qualified boundaries remain **11 nt for the pinned backend**
and **10 nt for exact reconstruction**. At 125+125 the 240-nt copy has 10 nt
overlap while the 234-nt copy has 16 nt; exact remains symmetric even though
backend survival is selective. At 124+125 the overlaps are 9 and 15 nt, so both
backend and exact eligibility differ. Production does not launch a comparator
for either selective backend geometry.

An equal-length copy-specific `(CA)x8` fixture has informative copy1 overlap and
ambiguous copy2 overlap at 150+106. Audited M4.2 exact was 2/20 despite pooled
20/40 truth. M4.2.1 exact is NOT_ASSESSABLE with all 40 excluded under the explicit
copy-observability reason. Family rows retain the same excluded evidence; their
pre-existing unique-definition gate additionally reports BLOCKED because this
repeat panel has nonunique reference alignment. No family policy rescues it.
Native is also preflight-blocked by the existing incomparable-coordinate gate;
this case intentionally has no actual backend analysis launch.

Adversarial tests reverse the affected copy, place only the middle copy of three
below the boundary, use reference insertions/deletions, unequal mates, tandem
repeat and homopolymer overlaps, safe geometries, uniformly unobservable copies,
and simultaneous within-copy/cross-copy asymmetry. The mixed-length test retains
20/40 from the qualified class and excludes all 40 pairs from the biased class.
Single-copy assessment has no cross-copy reason. Existing actual independently
qualified copy-cohort controls remain reportable.

## NEW-B: invalid policies are local results

Policies are normalized before prepared-input verification/classification and
before backend launch. This applies to both collect_metrics and run_metrics.
Core WT/PE family distance, intended-state, position and tolerance semantics are
unchanged. All requests remain represented; no policy silently overwrites another.

- Missing `policy_id`: `MISSING_POLICY_ID`.
- Null/integer/string/list/bool request: `INVALID_TOLERANCE_POLICY`.
- Empty or non-string ID: `INVALID_POLICY_ID`.
- Duplicate nonempty ID: every conflicting request, including the first, is
  BLOCKED with `DUPLICATE_POLICY_ID`. Distinct valid IDs still compute.
- Unsupported fields, negative/float/bool counts, nonzero extra-indel tolerance,
  abundance/quality options and out-of-range positions:
  `UNSUPPORTED_TOLERANCE_POLICY`.

Valid result keys are user IDs. Invalid result keys are deterministic internal
storage keys based on request index, with collision avoidance against all supplied
IDs. The record's `policy_id` and `policy` preserve the user identity/request;
an internal key never disguises a duplicate as a valid distinct scientific policy.
Missing identities use the explicit diagnostic identity `invalid`. Non-dict
requests are retained under `invalid_policy` in serializable diagnostic form.
A top-level None means no requests; a list containing None means one invalid
request. A dict is accepted as one request; iterable requests are materialized once.

The matrix covers zero/one/multiple valid requests, duplicate/missing IDs,
malformed requests, all-invalid and mixed batches, top-level malformed inputs and
internal-key collisions. Canonical metric contents, QC, eligibility, anchor
evidence and raw product evidence are identical to the no-policy baseline in
every case. Valid requests compute normally; invalid requests have null fractions,
local reasons and excluded classification counts. No result publication is lost.

A test observes validation before canonical collection and backend invocation.
The three actual cross-copy production runs also request valid, duplicate,
null and missing-ID policies and each writes a complete result.json. A separate
clean Python process reaggregates serialized evidence containing valid and invalid
requests without FASTQ or backend access. Its results exactly match in-process
reaggregation.

The preserved tolerance control remains:

| Extra substitutions | WT family | PE family | Fraction |
|---|---:|---:|---|
| 0 | 1000 | 300 | 300/1300 |
| 1 | 1030 | 330 | 330/1360 |
| 2 | 1035 | 335 | 335/1370 |

Position 149 remains 320/1340; position 179 remains 310/1320. PE minimum distance
1 versus WT distance 3 remains PE at radius 3; equal minimum distances remain
family ambiguous. The original tests and actual tolerance experiment all pass.

## Periodic residual and historical preservation

A qualifying overlap is not treated as unique when a shorter sequence-consistent
alternative has at least four matching bases and reconstructs a different product
length. Shorter alternatives also retain the prior repeated-period check. This
removes the old restriction that the repeat period must fit twice within the
qualifying overlap. No motif, target name or special edit coordinate is used.

The grid tests periods 1 through 10, expansion and contraction, and both WT/PE
states: **40 ambiguous products are non-exact**. With the same definitions and
informative overlapping flanks, **80 positive-control classifications are exact**.
The hexanucleotide GGGGCC expansion is included. Raw mates, definitions, old/new
calls and reasons are stored in `periodic-grid.json`. This is a conservative
qualified ambiguity boundary, not a universal guarantee for every unseen repeat
or shorter than four-base alternative. Chance borders can conservatively exclude
products; merely containing a repeat does not exclude a uniquely qualified product.

`classification-reconciliation.json` records old/new counts for all new copy
fixtures and all **475 historical target pairs**, with no historical classification
changes. The previous classifier is replayed from `audited_observability.py`, a verbatim
committed snapshot from the audited parent. Its SHA-256 is recorded in the
reconciliation. Regeneration needs no Git checkout or access to parent history.

| Population | Native | Precise |
|---|---|---|
| M3 target, 350 input / 330 aligned / 20 unaligned | 120/330 | 100/230 |
| M3.1 target, 125 input / 105 aligned / 20 unaligned | 30/105 | 20/55 |
| Confident copy1, 45 input / 42 aligned / 3 unaligned | 18/42 | 12/30 |
| Confident copy2, 30 input / 28 aligned / 2 unaligned | 12/28 | 8/20 |
| Combined confident, diagnostic only | 30/70 | 20/50 |
| Historical Pooled copy1, unqualified production routing | 72/199 | 60/140 |
| Historical Pooled copy2, unqualified production routing | 48/131 | 40/90 |

The fresh geometry grid remains **36 total / 13 allowed / 23 BLOCKED**. M4.1/M4.2
aligned ambiguity/discard reconciliation, preprocessing attrition, runtime scope,
failure reasons, reason-code validation, anchor partition divergence, state
symmetry and overlap titration all retain their passing regressions.

## Evidence inventory

- `actual/`, `cross-copy-results.json`, `classification-reconciliation.json`:
  new executions, target definitions, raw biased diagnostics, production results,
  Core JSON/counters/extracted alleles and per-haplotype reconciliation.
- `policy-validation-matrix.json`, `canonical-policy-independence.json`,
  `policy-execution-order.json`, `clean-process-reaggregation.json`: request-local
  failures, unchanged canonical hashes, ordering assertions and offline replay.
- `periodic-grid.json`: all periods, directions, states and positive controls.
- `historical-regression.json`, `geometry-grid.json`, `preserved-closures.json`,
  `preserved-tolerance.json`: fresh regression evidence.
- `test-results.json`, `source-tests.txt`, `wheel-tests.txt`, `wheel-parity.json`:
  complete cases/counts and source/wheel scientific equality.
- `runtime.json`, `packaging.json`, `portable-reproduction.json`,
  `tested-wheel-payload.json`, `gate.json`:
  pinned runtime, installed-wheel checks and final gate.
- `start-runtime.sh`, `run-tests.sh`, `collect_evidence.py`,
  `verify-package.py`, `audited_observability.py`: portable reproduction, packaging
  checks and audited comparison source.

Only text evidence is committed. No FASTQ, BAM or ZIP is included. Extracted allele
tables supplement the original artifact identities recorded in result JSON.
Evidence is distributed in the sdist; production wheel resources remain unchanged
apart from the focused code and version update.

## Portable reproduction

Prerequisites: Linux/bash/coreutils, Python 3.12, Docker access, network access to
install the lockfile and pull the pinned image, and this checkout or extracted
sdist. Work from the repository root. The following uses ignored `results/` paths
and a caller-chosen new runtime name. No existing container, fixed workspace path,
transient pytest directory or parent Git checkout is required.

```sh
project_root="$PWD"
qualification_root="$project_root/results/m421-qualification"
mkdir -p "$qualification_root"
python -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .

runtime_name="pe-m421-$(id -u)-$$"
bash docs/validation/m421/start-runtime.sh "$qualification_root/tools" "$runtime_name" "$project_root"
export M3_CORE_EXECUTABLE="$qualification_root/tools/CRISPResso"
export M3_POOLED_EXECUTABLE="$qualification_root/tools/CRISPRessoPooled"
export M3_SAMTOOLS_EXECUTABLE="$qualification_root/tools/samtools"

bash docs/validation/m421/run-tests.sh "$project_root/.venv/bin/python" "$qualification_root/source"
.venv/bin/python -m build --no-isolation --outdir "$qualification_root/candidate"
python -m venv "$qualification_root/wheel-env"
"$qualification_root/wheel-env/bin/pip" install -r requirements-dev.lock
"$qualification_root/wheel-env/bin/pip" install --no-deps "$qualification_root/candidate/crispresso_pe_pipeline-0.4.3-py3-none-any.whl"
mkdir -p "$qualification_root/wheel-suite"
tar -xzf "$qualification_root/candidate/crispresso_pe_pipeline-0.4.3.tar.gz" -C "$qualification_root/wheel-suite"
cd "$qualification_root/wheel-suite/crispresso_pe_pipeline-0.4.3"
bash docs/validation/m421/run-tests.sh "$qualification_root/wheel-env/bin/python" "$qualification_root/wheel"
cd "$project_root"
.venv/bin/python docs/validation/m421/collect_evidence.py \
  --source "$qualification_root/source" --wheel "$qualification_root/wheel" \
  --dist "$qualification_root/candidate" --output docs/validation/m421 \
  --runtime-container "$runtime_name"
(cd /tmp && "$qualification_root/wheel-env/bin/python" \
  "$project_root/docs/validation/m421/collect_evidence.py" \
  --source "$qualification_root/source" --wheel "$qualification_root/wheel" \
  --dist "$qualification_root/candidate" --output "$qualification_root/replay" \
  --runtime-container "$runtime_name")
.venv/bin/python -m build --no-isolation --outdir "$qualification_root/final"
.venv/bin/python docs/validation/m421/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" \
  --dist "$qualification_root/final" --evidence docs/validation/m421 \
  --replay "$qualification_root/replay"
# Include the generated packaging attestation, then verify the complete sdist again.
.venv/bin/python -m build --sdist --no-isolation --outdir "$qualification_root/final"
.venv/bin/python docs/validation/m421/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" \
  --dist "$qualification_root/final" --evidence docs/validation/m421 \
  --replay "$qualification_root/replay"
```

Every test result root must be new. The container must see the checkout, extracted
wheel suite and result paths at identical absolute paths; the helper mounts the
supplied project root and /tmp. Direct executable wrappers preserve working
directory and nonzero exits, avoiding the image's default router. The runtime is
exactly `pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.
An installed-wheel collector run from outside the checkout regenerated all 72
generated evidence files byte-identically, recorded in `portable-reproduction.json`.
The optional collector container argument records actual image identity; tools
are resolved from the documented environment variables or PATH.

The runner gives pytest a stable caller-owned result subdirectory, but the collector
does not depend on its contents: policy matrices are rebuilt from durable actual
analysis outputs. Check installed imports from outside the checkout, API/schema/
barcode/profile resources, CLI version 0.4.3 and `pip check`. After evidence-only
additions, rebuild, compare every wheel member except RECORD with
`tested-wheel-payload.json`, and verify the final sdist includes all current evidence.
Remove only the runtime you created when finished: `docker rm -f "$runtime_name"`.

## Remaining LOW and informational limitations

Derived document validation does not independently cross-link arbitrary caller-
supplied family rows with evidence, population IDs or dictionary keys. The
executable path recomputes from sequences; no provenance-attestation redesign is
included. The canonical target unresolved bucket remains broad; cross-copy backend
options outside target-native comparison and `running_info.args` are not
independently certified. Eligibility summaries remain worst-status summaries;
individual records determine reportability.

Native is conservatively blocked if any observed length class selects candidates.
Exact/family may report the qualified length-class subset, with exclusions explicit.
The backend merge boundary qualifies the pinned geometry and does not guarantee
quality-, mismatch- or adapter-independent survival. Copy metrics remain routing-
conditioned, including possible insertion-associated depletion. Unseen repeats and
nonunique family coordinate alignments remain limited. Family evidence size and
classification time grow with unique haplotypes, and evidence retains aggregate
unassessable mates. Abundance, quality and extra-indel tolerance remain unsupported.
This implementation is ready for a targeted independent audit; no merge approval
or completed independent audit is implied.
