# AUDIT PREP FROZEN — READY FOR FUTURE CANDIDATE

This is a candidate-independent audit kit, **not candidate approval and never an implementation base**.

- Repository: jily327/crispresso-pe-pipeline
- Exact fetched remote main: `72e0f86a495e079cab2ae50d2796e7a3423c78af`
- Artifact branch: `artifacts/practical-ux-audit-prep`
- Scope: 0.9.0 practical input/UX maintenance, with science and M11C contracts frozen.
- Independence: fetched only `refs/heads/main` with `--no-tags`; no implementation branch, candidate SHA or agent notes inspected/requested.
- This preparation does not change production, existing tests, packaging, dependencies, historical validation artifacts, or cloud configuration. Only files in this directory are committed.

## Contents and entry points

| Deliverable | File |
|---|---|
| Original feature contract | FEATURE-CONTRACT.txt |
| FASTQ attacks, ownership, Excel structural/row matrix | ORACLES.md A–D; audit_candidate.py; fixtures/excel-cases.json |
| Manual/Excel and legacy/upload parity | ORACLES.md E/F; test_oracles.py |
| Exact PE/comparator/copy definitions; simultaneous metrics | ORACLES.md H/I/J; fixtures/metric-display.json |
| Final verification without lifecycle redesign | ORACLES.md G; fixtures/job-timeline.json; executable event-state oracle |
| Versioning and historical protection | audit_tools.py version; ORACLES.md K/L |
| 1,597-file baseline SHA-256 tripwire with explicit categories | frozen-core.json; audit_tools.py tripwire |
| 29 real XLSX, paired synthetic gzip, truncated gzip | fixtures/; generate_fixtures.py; fixtures/manifest.json |
| Future HTTP/UI/execution adversarial tests | audit_candidate.py; ADAPTER.md |
| Twelve browser cases with actual file input APIs | BROWSER.md |
| Focused retained regression commands | REGRESSIONS.md |
| Prep run results and limitations | evidence/PREP-RESULTS.md and logs |

Run baseline self-validation from the pinned root venv:

```
python -m pytest -q audit/practical-ux/test_oracles.py
python audit/practical-ux/audit_tools.py tripwire
```

The future adapter tests are NOT claimed executed. The future independent auditor must bind actual transport/UI and fault barriers separately, following ADAPTER.md, then run tests explicitly. Unknown route names are not invented. Missing adapter is an error, not a skipped/passing audit. The original prep expectations, fixtures and baseline manifest remain frozen. Any amended expectation requires a separately documented contract decision made visible in the future audit report.

For future audit retrieve this exact commit (reported at handoff) as immutable artifact material and compare a separately authorized candidate. Do not merge this branch to create the implementation. Preserve raw evidence, separate automated passes/failures from manual review, unsupported instrumentation and unrun tests. No future candidate has been evaluated here.
