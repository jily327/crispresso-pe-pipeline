# First GUI run: what to click

Use the [synthetic practice run](SYNTHETIC_SMOKE.md) first. Real-data use must wait
for the final M11C.2 independent audit and merge. These instructions describe
candidate `232d380c73f456181bade0e5c11138c8c5ec6570`.

## Launch and open

Activate the application venv in Ubuntu and run the [quick-start](README.md).
Open the entire printed `http://127.0.0.1:8765/#…` URL in your Windows browser.
The fragment is a local session credential: do not post it in screenshots or
messages. The browser may remove it from the address bar after opening. Keep the
terminal running. Node is not needed.

## 1. Samples & Sequencing

Choose **New Analysis**, enter an **Analysis name**, and use **1. Samples**.
For ordinary raw Hi-TOM data select **Raw paired-end pool + barcode sample sheet**.
Select the registered **Pool R1** and **Pool R2**. The launch command repeats
`--setup-fastq` once per mate. This is one sequencing pool containing multiple
internally barcoded samples, not one FASTQ pair per biological sample.

Use **Add sample** for each expected biological sample. Enter the real
`sample_name`, stable `barcode_id`, forward and reverse barcode sequences,
`editor`, `treatment`, `dpi`, and `biological_replicate`; supply paired/block
metadata where applicable. Replicates are biological samples, not reads or target
copies. Do not invent dpi, guide sequences, barcodes or replicate identities.
Duplicate biological replicate identities within the same condition are invalid.

The current wizard uses editable rows. It does not upload FASTQs, import your CSV
via a file picker, or register a separate pair per row. Files must be registered
when launching. QI-HITOM barcode sequences must agree with the bundled catalog.

### Alternative: an existing verified M2 archive

Instead of the raw-pool launcher, use:

```bash
peanalyzer-viewer \
  --setup-demux "$HOME/peanalyzer/inputs/my-verified-M2-archive" \
  --setup-output-root "$HOME/peanalyzer/analyses" \
  --run-crispresso "$HOME/peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso"
```

Select **Verified M2 demux archive** and the registered archive, then supply the
matching sample metadata. This must be a complete backend-verifiable M2 archive,
not an arbitrary folder of per-sample reads. It remains immutable external input.
Prepared analysis FASTQs go into the new workflow workspace.

## 2. Analysis Mode

Choose **2. Mode**, then **Precise Edit** (PE) or **Indel / Nuclease**. Changing
mode/profile can clear incompatible target inputs after a warning. The modes
use separate existing scientific contracts; they are not interchangeable ways
to calculate an editing percentage.

## 3. Target

For PE, enter one biological target's WT and intended edited amplicons, copy name,
real pegRNA spacer and extension, and optional nicking guide/scaffold. Use **Add
copy** for additional copies/homeologs of that same target. Shared experimental
guide/extension constraints apply; do not fabricate copy-specific guides. The
GUI does not support a real multi-target run. A geometry warning can mean target
metrics remain possible while copy metrics are blocked; it does not authorize
inventing a copy assignment.

For nuclease, enter one target and one copy. A generic **Target profile** needs
explicit zero-based inclusive quantification-window coordinates: `0-0` means
the first base, while sentinel `0` is invalid. Do not copy illustrative
coordinates into a real experiment. For **TIGR–Tas**, enter the real **18-nt TIGR
target** and choose **Selected window** W1, W2, W3 or W4; W2 is initially selected.
Review Python's returned orientation, interval and window annotations. The 58
locked nuclease settings are requirements, not user-adjustable parameters or
proof that a backend run has already passed qualification.

## 4. Configuration

Choose **4. Configuration**. Select the actual **Library extraction profile**.
Automatic trims apply only to the qualified untrimmed QI-HITOM layout (9 barcode
bases plus 18 bridge bases, 27 total). Custom layout currently means read-start
barcodes without a bridge, with both **R1 analysis 5′ trim** and **R2 analysis 5′
trim** explicitly supplied. Do not assume a library is qualified from its name.
The synthetic fixture's trim of 8 is not a recommendation for real data.

Select **Proposed output parent (optional)** and enter a new **Proposed workspace
name**. The parent must already exist and be registered at launch; the new child
workspace must not exist. An output proposal is necessary for Run even though
Setup/Review can be used without one. Keep it in the Linux filesystem and away
from input directories. Do not pre-create the child folder.

## 5. Review → Run → results

Click **Validate & Review**. Fix errors; read warnings and verify sample identities,
input pairing, target sequences, trims, coordinates, output path and proposed
stages. Editing a draft invalidates its previous Review. If files change, stop
and validate the intended inputs again. Setup and Review do not execute science.

When the current Review is accepted, click **Run Analysis**. One scientific job
can run at a time. The progress table reports actual stage states; absence of
a percentage is intentional. A scientific BLOCKED/NOT_ASSESSABLE metric need
not mean the workflow failed. An operational failure displays its real stage
and technical code; it is not zero editing.

Wait for verified completion, then click **Open Results**. This uses the existing
M10 verifier and viewer. PE exact intended and CRISPResso-native fractions have
different definitions/denominators; nuclease uses its own qualified window.
Inspect integer counts, exclusions and status reasons, not percentages alone.
The GUI provides descriptive summaries; creating contrasts is not exposed here.

While a job runs, browser reload can reconnect if the server is still alive.
Reloading an unsubmitted draft does not save it. Do not close the server or put
the computer to sleep during a run. For cancellation and later reopening, read
[recovery and retention](RECOVERY_AND_DATA_RETENTION.md).
