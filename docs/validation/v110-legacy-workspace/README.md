# Read-only v1.0.1 workflow replay

The historical producer is the v1.0.1 wheel built from commit `25ce3a990ccef9e2daa8937f0c09023498ef4cb5`. Its installed workflow code and resources are checked against the frozen checkout and the package fingerprint recorded by the workflow. Its M7 test fixture generates one forward-strand sample with two copies, one intended PE product and three WT products per copy. The workflow starts from the raw paired FASTQs and produces its own demultiplexing, preparation, routing, native CRISPResso2, statistics and report artifacts.

The candidate runs `verify_workflow_output` and the desktop viewer's read-only workspace projection. The verifier takes a SHA-256 inventory of every regular file under the inputs and completed workspace before those calls, then repeats the inventory afterwards. `result.json` records the versions, integer outcomes and inventory digests. `file-hashes.csv.gz` contains the individual before and after hashes and byte sizes. The evidence contains newly generated synthetic data. Archived ALSW comparisons use separate evidence and inputs.

To reproduce, start in the candidate checkout with its Python environment active, Docker access to the pinned image and the application's normal private recovery-key directory available. Use a fresh scratch directory.

```bash
case_dir="$(mktemp -d)"
git clone --quiet --shared --no-checkout . "$case_dir/original"
git -C "$case_dir/original" checkout --quiet --detach 25ce3a990ccef9e2daa8937f0c09023498ef4cb5
python -m pip install --no-deps --no-build-isolation --target "$case_dir/distribution" "$case_dir/original"
PYTHONPATH="$case_dir/distribution:$case_dir/original/tests" python docs/validation/v110-legacy-workspace/generate.py "$case_dir"
python docs/validation/v110-legacy-workspace/verify.py "$case_dir" "$case_dir/evidence"
```
