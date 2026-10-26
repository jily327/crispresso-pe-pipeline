# Reproduction and evidence boundaries

Use a separate clean checkout at exact baseline `a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503`. Do not execute science from the artifact commit: its different git identity is expected to invalidate reuse. Install the baseline locked dependencies and GUI test dependencies in a virtualenv; do not change the checkout during a scientific run. `runtime-identity.json` records the actual preparation environment. Never fetch the future implementation as part of preparation reproduction.

The commands below use task-specific shell variables. Substitute local paths and a new unused output parent. All scripts refuse existing run directories where destructive fixture construction is involved. The qualified Core executable must resolve to 2.3.4 in the pinned image; provide a local qualified runtime or the already qualified transport. Do not infer process containment from a container wrapper.

```bash
AUDIT_PACKAGE=/absolute/path/peanalyzer-m11c-audit-prep
AUDIT_BASELINE=/absolute/path/clean-baseline-checkout
AUDIT_PYTHON=/absolute/path/venv/bin/python
AUDIT_RUNS=/absolute/path/new-disposable-audit-runs
AUDIT_CORE=/absolute/path/qualified/CRISPResso
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$AUDIT_BASELINE/src"
export MPLCONFIGDIR=/tmp/m11c-audit-mpl
export XDG_CACHE_HOME=/tmp/m11c-audit-cache
mkdir "$AUDIT_RUNS"

"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/selftest.py" --baseline "$AUDIT_BASELINE" --output "$AUDIT_RUNS/selftest"
"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/process_canaries.py" "$AUDIT_RUNS/process"
"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/server_death_canary.py" --baseline "$AUDIT_BASELINE" --fixtures "$AUDIT_PACKAGE/fixtures/pe" --output "$AUDIT_RUNS/server-death"
"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/baseline_science.py" --baseline "$AUDIT_BASELINE" --fixtures "$AUDIT_PACKAGE/fixtures" --output "$AUDIT_RUNS/science" --core "$AUDIT_CORE"
"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/validate_science.py" --baseline "$AUDIT_BASELINE" --runs "$AUDIT_RUNS/science" --output "$AUDIT_RUNS/strengthened" --core "$AUDIT_CORE"
"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/check_reports.py" "$AUDIT_RUNS/science/pe/fresh/report" "$AUDIT_RUNS/science/pe/cancelled/report" "$AUDIT_RUNS/science/nuclease/fresh/report" "$AUDIT_RUNS/science/nuclease/cancelled/report" --out "$AUDIT_RUNS/report-checks.json"
```

The science driver ends with intentional partial-force negative controls that leave the disposable `failed` roots incomplete. It restores the copied samples source afterward. Fresh and cancelled/resumed roots remain valid. The strengthened driver uses the latter for another routing force and completed resume. This is expected fixture behavior, not permission to run the negative control on an existing user workspace.

For an independent future closure or identity capture:

```bash
"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/force_oracle.py" /disposable/workflow/plan.json --force routing --out /separate/audit/closure.json
"$AUDIT_PYTHON" "$AUDIT_PACKAGE/scripts/recovery_identity.py" /disposable/workspace --software /separate/audit/current-software.json --backend /separate/audit/current-backend.json --force routing --lease /declared/host-lease --out /separate/audit/identity.json
```

Supply current software/backend identities independently from the actual runtime. The backend object must contain `executable`; additional version/digest fields remain bound verbatim. Capture token files OUTSIDE the scientific workspace so audit output does not itself invalidate its inventory. No script guesses a candidate recovery API.

Preparation command outcomes and development corrections are recorded in [evidence/commands.json](evidence/commands.json). Original large workflow roots remain outside the committed package; compact science projections, run/reuse records, process evidence and trap deletion paths are included. No arbitrary user raw data is included.
