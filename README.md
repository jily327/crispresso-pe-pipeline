# crispresso-pe-pipeline

**M5.1 (0.5.1) adds offline biological-sample aggregation and explicit exact
replicate-level contrasts with family-scoped BH correction.** Use
[`peanalyzer summarize` and `peanalyzer stats`](docs/m5-statistics.md). Reads are
not biological replicates. Target, copy and policy populations stay separate;
nonreportable measurements retain their status. Every participating sample must
have one result for every target represented in the run; partial coverage fails
closed. Metadata with no results remains unused. See
[M5.1 remediation](docs/validation/m51/README.md) and [M5 qualification](docs/validation/m5/README.md).

**M4 implements production PE measurements with explicit target and copy
populations, integer denominators, provenance and reportability gates.**
**M4.2.2 (0.4.4)** withholds whole-target precise/family fractions when any
prepared pair has copy- or state-dependent product observability. Safe mixed
read lengths and independently qualified copy metrics remain supported. See
[remediation evidence](docs/validation/m422/README.md).

Use the [M4 Python API and measurement contracts](docs/m4-metrics.md), including
the target all-read native/precise metrics and separately labelled confident-copy
metrics. See [M4 evidence](docs/validation/m4/README.md) for qualification and
reproduction. M5 provides the statistical layer described above; biological
interpretation and reporting remain future work. The milestone history below describes the boundaries M4 uses.

A local, reproducible prime-editing amplicon sequencing pipeline under development
for inline-barcoded samples and multiple target copies/homeologs. The intended
workflow is barcode demultiplexing → CRISPRessoPooled → copy/target PE metrics →
biological statistics → reports.

**Milestones 1–3 implement metadata validation, paired barcode demultiplexing,
completion verification, analysis trimming and external CRISPResso2 diagnostics.**
The actual 2.3.4 synthetic validation found **ROUTING GATE: FAIL**: all 310
informative reads routed correctly, but all 40 deliberately ambiguous or
non-informative reads were forced into individual copies. The same experimental
spacer with a one-base homeolog mismatch was rejected. That default routing
approach remains blocked; M4 uses the subsequent qualified explicit-routing
boundary for copy metrics. These historical milestones do not implement biological statistics or reporting.

**M3.1 adds a separate explicit diagnostic-evidence router. Its qualified synthetic
gate passes: 75/125 pairs confidently assigned, 50 quarantined, zero cross-routes.**
This does not rehabilitate Pooled's default router. Prepared inputs and routed
cohorts are independently verified, and only confident cohorts enter direct
CRISPResso Core analyses. See [M3.1 qualification](docs/m31-routing.md) for scope,
limitations, exact metric denominators and backend alignment attrition.

See [Milestone 3 validation and reproduction](docs/m3-backend-validation.md) and
the [committed synthetic evidence](docs/validation/m3/README.md).

## Install and test

Use Python 3.12 for the tested, pinned development installation below. Package
metadata permits Python >=3.11, but the current NumPy/contourpy lock pins require
3.12; Python 3.11 would need a separately resolved compatible dependency set.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e '.[dev]'
python -m pytest -q
```

## Validate metadata

```sh
peanalyzer validate \
  --samples examples/samples.csv \
  --targets examples/targets.csv \
  --config examples/config.yaml
```

The command emits JSON with counts, warnings and resolved configuration. Exit 0
means structurally valid metadata; exit 2 means invalid input. Warnings do not
certify biological validity. Example sequences are synthetic schema fixtures,
not experimental designs. No CRISPResso installation is needed for validation.

## Demultiplex Hi-TOM reads

```sh
peanalyzer demux \
  --r1 /data/EV_only_1005_R1.fastq.gz \
  --r2 /data/EV_only_1005_R2.fastq.gz \
  --samples examples/ev_only_1005_samples.csv \
  --config examples/qi_hitom_config.yaml \
  --output results/ev_only_1005
```

The default `qi_hitom_v1` profile matches the full 9-nt motifs at offset 0,
independently on R1 and R2. Its catalog contains F1–F12 and RA–RH. Supply
`--barcodes /path/to/catalog.csv` to use a different catalog. The bundled source
is `src/peanalyzer/barcode_sets/qi_hitom_v1.csv` and is included in wheels.

Exact matching is the default. Unexpected valid pairs and ambiguous matches
never enter sample FASTQs. Original header, sequence, plus and quality bytes
are preserved by default; bridge mismatches are QC-only. Each successful run
publishes sample gzip FASTQs, the complete F × R CSV matrix and a JSON summary
with count reconciliation, output hashes and software provenance. A heatmap is
optional convenience output; rendering failures are explicit warnings. The output
directory must be new; unfinished runs stay in a separate `.incomplete-*` directory.

Version 0.2.1 adds case-insensitive filename checks, exclusive file creation and
catalog-aware matching guardrails. Custom catalogs require equal barcode lengths
within each direction; supplied catalogs cannot be extended by a sample sheet.
See [M2.1 hardening and the completion contract](docs/m2-hardening.md). Future
stages must verify that contract before consuming FASTQs.

See [demultiplexing documentation](docs/demultiplexing.md) for the Python API,
custom extraction/trimming, output contracts and manual real-data comparison.
Real FASTQs are not bundled or required by tests. Unexpected valid combinations
are not automatically attributed to PCR chimeras.

[`docs/architecture.md`](docs/architecture.md) defines the CSV/YAML schemas,
package boundaries, version-pinned CRISPResso invocation and output fields,
metric definitions, assumptions and remaining milestones. Models in
`src/peanalyzer/schemas.py` are the executable schema source of truth.

The precise metric is **precise full-amplicon intended PE**, distinct
from all reads assigned to a PE reference or unmodified in a quantification
window. CRISPRessoPooled's default Bowtie2 routing does not guarantee unambiguous
homeolog assignment; a validated routing gate is required before copy estimates.

M4 is ready for independent audit after its documented validation. Guide-mismatched
backend representations and unsupported copy geometry remain blocked. Copy
metrics are routing-conditioned; target metrics use all eligible prepared pairs.
No biological interpretation or statistical reporting is implied.
Work is developed on feature branches and integrated into `main`
only after review. Research use; biological definitions require experiment-specific
confirmation.
