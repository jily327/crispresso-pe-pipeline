# Independent M11B audit preparation

Reference material only, frozen before inspecting M11B. No application implementation, private experimental data, or generated scientific results. Baseline main: `c5f6272612df06e7f939f58fc567e1c386cc750a`. Design reference: `05cfc68b62215a4c52862e09f081eab1c75ba39f`.

Read in order:

1. [Audit plan](M11B_AUDIT_PLAN.md): authority, observed contracts, procedure and severity.
2. [70-case adversarial matrix](M11B_ADVERSARIAL_MATRIX.md), also [machine-readable JSON](M11B_ADVERSARIAL_MATRIX.json).
3. [Direct/GUI and identity oracle](M11B_DIRECT_GUI_ORACLE.md).
4. [Execution/write tripwires](M11B_TRIPWIRE_SPEC.md).
5. [Cancellation oracle](M11B_CANCELLATION_ORACLE.md).
6. [Event invariants](M11B_EVENT_INVARIANTS.md).
7. [Browser/race procedures](BROWSER_AND_RACE_PLAN.md), [candidate adapter checklist](ADAPTER_CHECKLIST.md), [source map](SOURCE_MAP.md).

`fixtures/` contains only small deterministic synthetic inputs (PE and nuclease). `scripts/` contains test-side audit tooling; none is a production server, supervisor, job API or arbitrary command hook. `evidence/` records preparation checks, not a candidate verdict.

## Verify and self-test

Python 3.11+ for stdlib helpers (file_digest); preparation used Python 3.12. Linux `/proc` required for process fixture; Node.js for route harness canaries. Baseline-specific helpers require the project's locked environment, including GUI dependencies. Do not install these scripts into production package source.

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/verify_package.py .
PYTHONDONTWRITEBYTECODE=1 python scripts/test_audit_tools.py
PYTHONDONTWRITEBYTECODE=1 python scripts/cancellation_smoke.py
node scripts/test_browser_races.mjs
```

Set `PYTHONPATH` to the **verified pinned main checkout's src**, not a random editable install. Initialize Matplotlib's cache outside measured actions. Then:

```bash
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/audit-mpl PYTHONPATH=/path/to/pinned-main/src \
  /path/to/qualified-python scripts/baseline_review_canary.py fixtures
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/audit-mpl PYTHONPATH=/path/to/pinned-main/src \
  /path/to/qualified-python scripts/tripwire_canaries.py
```

Verify imported peanalyzer location before trusting results. Startup font-cache writes are not Setup writes; preload the runtime before enabling measured write guards. Tools never require private FASTQs.

## Integrity hierarchy and publication

`CHECKSUMS.json` inventories all payload bytes except itself, ZIP and ZIP sidecar. The ZIP contains the payload plus CHECKSUMS, avoiding self-hash/archive recursion. `ARCHIVE_SHA256.txt` hashes the final ZIP. `verify_package.py` checks the exact payload inventory and every ZIP entry against disk, with no unexpected files or symlinks. Python bytecode caches are not payload: use `PYTHONDONTWRITEBYTECODE=1`.

The completed package is copied byte-for-byte from `/workspace/peanalyzer-m11b-audit-prep/` into `m11b-audit-prep/` on `artifacts/m11b-audit-prep`, one artifact commit with parent exactly the pinned main. Git blob bytes, working copies and source package must agree. No main/development ref is moved; no PR or merge. The ZIP can be downloaded from the artifact branch's GitHub file page. Extract to a new directory and verify before use.

Known limits: future API binding, full identity check on real completed outputs, real Core/container cancellation, actual browser integration and all candidate results remain for the independent audit. Tooling canaries are not proof that M11B passes. Hard-crash/server-restart recovery, relocation, resume and force are outside this milestone. Keep unexplained differences as findings, not waivers.
