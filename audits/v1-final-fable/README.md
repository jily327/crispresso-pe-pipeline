# PEAnalyzer v1.0.0 — final independent audit artifacts

Audited commit: `00b528e9c2ea7c1b14d8607c5c38ff46416054ae` (`main`, package 1.0.0). This branch is that commit plus this directory only; no production file differs.

Verdict: **PEANALYZER V1.0.0 FINAL AUDIT: PASS WITH CONDITIONS**

Start with `V1_FINAL_AUDIT_EXECUTIVE_SUMMARY.md`, then `V1_FINAL_RELEASE_DECISION.md` and `V1_RELEASE_RISK_REGISTER.md`.

| Path | Purpose |
|---|---|
| `V1_*.md` | The eight audit reports |
| `scripts/design.py` | Synthetic molecule/FASTQ generator (stdlib only; the source of designed truth) |
| `scripts/make_*_experiment.py` | Build PE, nuclease and two-copy experiments |
| `scripts/verify_*_workspace.py` | Independent oracles (own CRISPResso parser, own statistics) |
| `scripts/gui_client.py`, `exp_gui_*.py`, `exp_recovery.py`, `exp_library.py`, `exp_excel_*.py` | Real-server HTTP experiments |
| `scripts/xlsx_reader.py` | Stdlib XLSX reader used to check the workbook without openpyxl |
| `evidence/*.json` | Machine-readable results of each experiment |
| `evidence/truth/` | Designed molecule inventories |
| `evidence/logs/` | Test-suite, build and integration logs (session tokens redacted) |

All data are synthetic. Absolute paths inside evidence files refer to the auditor's temporary directory and carry no meaning elsewhere.
