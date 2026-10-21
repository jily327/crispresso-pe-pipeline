# crispresso-pe-pipeline

A local, reproducible prime-editing amplicon sequencing pipeline under development
for inline-barcoded samples and multiple target copies/homeologs. The intended
workflow is barcode demultiplexing → CRISPRessoPooled → copy/target PE metrics →
biological statistics → reports.

**Milestone 1 implements metadata validation only.** It does not analyze FASTQs,
run CRISPResso, calculate editing efficiency or fit statistical models.

## Install and test

Python >=3.11; the development lock was tested on Python 3.12.

```sh
python3 -m venv .venv
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

[`docs/architecture.md`](docs/architecture.md) defines the CSV/YAML schemas,
package boundaries, version-pinned CRISPResso invocation and output fields,
metric definitions, assumptions and remaining milestones. Models in
`src/peanalyzer/schemas.py` are the executable schema source of truth.

The proposed primary metric is **precise full-amplicon intended PE**, distinct
from all reads assigned to a PE reference or unmodified in a quantification
window. CRISPRessoPooled's default Bowtie2 routing does not guarantee unambiguous
homeolog assignment; a validated routing gate is required before copy estimates.

Next is Milestone 2: paired gzip barcode demultiplexing with QC and count
reconciliation. Work is developed on feature branches and integrated into `main`
only after review. Research use; biological definitions require experiment-specific
confirmation.
