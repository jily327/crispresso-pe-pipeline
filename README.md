# crispresso-pe-pipeline

A local, reproducible prime-editing amplicon sequencing pipeline under development
for inline-barcoded samples and multiple target copies/homeologs. The intended
workflow is barcode demultiplexing → CRISPRessoPooled → copy/target PE metrics →
biological statistics → reports.

**Milestones 1–2.1 implement metadata validation and paired barcode demultiplexing.**
CRISPResso execution, target/homeolog assignment, PE quantification, statistics
and final reporting are not implemented.

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

The proposed primary metric is **precise full-amplicon intended PE**, distinct
from all reads assigned to a PE reference or unmodified in a quantification
window. CRISPRessoPooled's default Bowtie2 routing does not guarantee unambiguous
homeolog assignment; a validated routing gate is required before copy estimates.

Next is Milestone 3: pinned CRISPRessoPooled integration and explicit validation
of target/copy routing. Work is developed on feature branches and integrated into `main`
only after review. Research use; biological definitions require experiment-specific
confirmation.
