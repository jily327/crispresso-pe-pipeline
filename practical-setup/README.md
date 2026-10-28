# PEAnalyzer: install and open the local GUI

**Candidate reference material — wait for the final M11C.2 audit and merge before
using real experimental data.** Studied candidate:
`232d380c73f456181bade0e5c11138c8c5ec6570`, package **0.8.0**.
This artifact branch is not an application implementation base.

After the one-time [WSL2/application installation](WINDOWS_WSL2_INSTALL.md) and
[native CRISPResso runtime installation](CRISPRESSO_RUNTIME.md), run these commands
in the **Ubuntu/WSL terminal**, from this `practical-setup` directory:

```bash
source ~/.venvs/peanalyzer/bin/activate
bash ./doctor.sh --input "$HOME/peanalyzer/inputs/pool_R1.fastq.gz" \
  --input "$HOME/peanalyzer/inputs/pool_R2.fastq.gz"
peanalyzer-viewer \
  --setup-fastq "$HOME/peanalyzer/inputs/pool_R1.fastq.gz" \
  --setup-fastq "$HOME/peanalyzer/inputs/pool_R2.fastq.gz" \
  --setup-output-root "$HOME/peanalyzer/analyses" \
  --run-crispresso "$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso"
```

Use your actual FASTQ filenames. Open the **complete printed URL**, including
`/#…`, in Windows Edge, Chrome or Firefox. Keep the Ubuntu terminal and computer
running. The GUI listens on `127.0.0.1:8765`; it is not a public web service.

Before any real data, follow the [small synthetic first run](SYNTHETIC_SMOKE.md).
Then use [what to click](FIRST_GUI_RUN.md) and the [real-data checklist](REAL_DATA_CHECKLIST.md).
The convenience command equivalent to the launch above is:

```bash
bash ./launch-new-analysis.sh \
  "$HOME/peanalyzer/inputs/pool_R1.fastq.gz" \
  "$HOME/peanalyzer/inputs/pool_R2.fastq.gz" \
  "$HOME/peanalyzer/analyses"
```

| Need | Instructions |
|---|---|
| Windows → WSL2 → installed wheel | [WINDOWS_WSL2_INSTALL.md](WINDOWS_WSL2_INSTALL.md) |
| Exact native CRISPResso 2.3.4 | [CRISPRESSO_RUNTIME.md](CRISPRESSO_RUNTIME.md) |
| Samples, PE/nuclease, Review and Run | [FIRST_GUI_RUN.md](FIRST_GUI_RUN.md) |
| Safe practice inputs | [SYNTHETIC_SMOKE.md](SYNTHETIC_SMOKE.md) |
| Reopen, cancellation and recovery | [RECOVERY_AND_DATA_RETENTION.md](RECOVERY_AND_DATA_RETENTION.md) |
| Error → safe action | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Tested boundaries and remaining checks | [SETUP_FINDINGS.md](SETUP_FINDINGS.md), [validation record](VALIDATION.md) |

**Keep the input files, complete workspace, and hidden `.NAME.gui-inputs-JOB_ID`
sibling folders in place.** They are not disposable temporary files. Recovery
also has an account-local `/tmp` key limitation; read the retention guide before
planning a long run.

Only this setup package is published by this task. Production code and branches
are unchanged. If the candidate advances, recheck this package against the final
approved immutable SHA before practical use. A future release wheel removes the
need to clone/build the application; no release wheel URL is invented here.
