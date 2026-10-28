# Safe synthetic first run

No real experimental data is needed. These tiny paired FASTQs come from the
candidate's existing M7/M8/M11B qualification fixture generators; provenance and
source hashes are in [fixtures/provenance.json](fixtures/provenance.json).
They are practice inputs, not universal biological defaults.

Activate your installed app environment, then from this setup directory:

```bash
mkdir -p ~/peanalyzer/inputs/practice ~/peanalyzer/analyses
cp -n -r fixtures/pe fixtures/nuclease ~/peanalyzer/inputs/practice/
bash ./doctor.sh \
  --input "$HOME/peanalyzer/inputs/practice/pe/raw_R1.fastq.gz" \
  --input "$HOME/peanalyzer/inputs/practice/pe/raw_R2.fastq.gz"
bash ./launch-new-analysis.sh \
  "$HOME/peanalyzer/inputs/practice/pe/raw_R1.fastq.gz" \
  "$HOME/peanalyzer/inputs/practice/pe/raw_R2.fastq.gz" \
  "$HOME/peanalyzer/analyses"
```

Use a fresh practice destination if copies already exist; do not change inputs
registered by an earlier workspace. Open the complete printed URL. Follow
[FIRST_GUI_RUN.md](FIRST_GUI_RUN.md) with [PE values](fixtures/pe/GUI_VALUES.md):
one sample, Precise Edit, two copies of T1, **custom** library profile, trims
**8 / 8**, new workspace name `smoke-pe`. Copy each sequence exactly. The supplied
CSV/JSON files are reference values; the GUI does not have a CSV import button.
Do not type the backticks or code-fence markers.

Click **Validate & Review**, verify the intended inputs, then **Run Analysis**.
After verified completion choose **Open Results**. The existing PE fixture oracle
has **2 exact intended products / 24** in the target exact metric. Inspect the
metric definition and integer counts, not only a rounded percentage. Other
report metrics can have different denominators.

After the first job is complete, stop that server normally with Ctrl+C. Launch
again using the two files under `practice/nuclease/`. Use the [nuclease
values](fixtures/nuclease/GUI_VALUES.md): one sample/copy, Indel / Nuclease,
TIGR–Tas profile, 18-nt target, W2, custom profile and trims 8 / 8. Use a different
new workspace name `smoke-nuclease`. Review → Run → Open Results should complete.
The existing oracle is **8 indel reads / 20** (12 WT, four deletion and four
net-zero-indel fixture reads). This tests a qualified window; it is not a window
recommendation for another target.

Finally reopen a completed result:

```bash
bash ./launch-view-results.sh "$HOME/peanalyzer/analyses/smoke-pe"
```

The viewer must verify the full workspace. Keep original practice inputs and
hidden durable sibling folders. A recovery-launch inspection of a completed
workspace should classify it COMPLETED and offer Open Results, not another Run.
Do not deliberately interrupt a real dataset for this smoke test.

## Maintainer reproducibility harness

`validation/smoke_api.py` automates the same official launcher and public HTTP
Setup → Review → Run → Open Results route, including doctor read-only and wrapper
checks. It does not patch product code or invoke a private test server. It needs
the installed wheel, qualified runtime and a **new** scratch root:

```bash
python -B validation/smoke_api.py --package "$PWD" \
  --root "$HOME/peanalyzer/setup-smoke-new" \
  --core "$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso"
```

This performs real small synthetic scientific runs. It is separate from the
read-only doctor. See [VALIDATION.md](VALIDATION.md) for observed results and the
limits of what was independently checked on this host.
