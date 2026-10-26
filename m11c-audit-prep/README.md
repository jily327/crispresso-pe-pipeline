# Independent M11C Recovery & Hardening audit package

Frozen against main **a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503** before inspecting any future M11C implementation. Prior independent M11B prep: **5b89009d460eab76b08574664e5c7340684c808a**. This is audit preparation, not a candidate verdict.

- [Audit plan and severity](M11C_AUDIT_PLAN.md)
- [105 adversarial cases](M11C_ADVERSARIAL_MATRIX.md) / [machine-readable cases](adversarial-cases.json)
- [Recovery/purity/identity oracle](M11C_RECOVERY_ORACLE.md)
- [Force closure and BLOCKING partial-force trap](M11C_FORCE_CLOSURE_ORACLE.md)
- [Host lease, server death and detached descendants](M11C_PROCESS_CONTAINMENT_ORACLE.md)
- [10 deterministic race schedules](M11C_TOCTOU_MATRIX.md) / [machine-readable schedules](race-schedules.json)
- [Fresh/resume/force scientific parity](M11C_FRESH_RECOVERY_PARITY.md)
- [Source map](SOURCE_MAP.md), [future adapter checklist](ADAPTER_CHECKLIST.md), [reproduction commands](REPRODUCE.md)
- [ZIP download](peanalyzer-m11c-audit-prep.zip), [archive SHA-256](ARCHIVE_SHA256.txt), [payload integrity](integrity.json)

## Executed preparation controls

| Control | Observed baseline/tool result |
|---|---|
| Independent closure | 192 valid subsets match authoritative backend; 64 analyze demux subsets rejected; 13 supported single-family path inventories |
| Identity sensitivity | 9 mutation dimensions invalidate/refuse old independent identity |
| Pure inspection | Positive read/closure and warmed authoritative verifier remain read-only; 6 forbidden-operation controls reject, including caught violations |
| Qualified PE | Fresh, failure/resume, SIGTERM/resume and routing force agree; exact/native PE `[4,8,16,20] / 24` |
| Qualified nuclease | Same recovery parity; indel `[2,4,14,16] / 20`; W2 qwc `104-113`; 58 actual child settings checked |
| Completed resume | 0 scientific stages, 14 reused in each mode; completion marker bytes retained |
| Partial-force negative control | Stale unforced demux detected after downstream deletion: 667 PE / 155 nuclease inventory paths removed; future candidate must reject before deletion |
| Process fixture | Five group/session/stdio modes; survivor/false-CANCELLED detection, PID-reuse refusal, canary survival and own-birth cleanup |
| Server hard kill/restart | Actual baseline JobStore/worker envelope in killable TestClient process permits two live fixed workers after restart; future candidate must retain host-global exclusion |
| Reports | Artifact hashes, SVG XML and exact inline SVG inclusion checked in four fresh/recovered reports |

Evidence is under [evidence/](evidence/). All candidate matrix cases remain **NOT_RUN_FUTURE_CANDIDATE**. No fresh full application suite or browser/WSL qualification is claimed. Qualified Core runs establish science; local fixed processes establish control sensitivity, with no claim that host signals kill the container transport. See document-specific limitations.

## Integrity and publication

All repository-facing text is English. The package is copied byte-for-byte from the completed scratch directory into `m11c-audit-prep/` on `artifacts/m11c-audit-prep`, branched directly from the exact main SHA above. One artifact-only commit is authorized; no application source, main, PR or merge changes are included.

`integrity.json` covers every payload file except itself, ZIP and ZIP sidecar. The ZIP contains every payload file plus integrity.json under one stable prefix; it excludes itself and its external hash sidecar. The sidecar hashes the complete ZIP. Git pins all three integrity artifacts. This avoids impossible recursive hashes. Verify published bytes with:

```bash
PYTHONDONTWRITEBYTECODE=1 python m11c-audit-prep/scripts/verify_package.py m11c-audit-prep
```

Use GitHub's raw/download control for the ZIP; a `/workspace` path is not a portable download. Exact artifact commit and remote publication checks are reported after the single commit, outside the self-referential archive.
