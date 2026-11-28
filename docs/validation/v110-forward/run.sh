#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 ]]; then
    echo 'Usage: bash run.sh ATTACHMENT_DIRECTORY NEW_WORK_DIRECTORY' >&2
    exit 2
fi
inputs=$(realpath "$1")
work=$(realpath -m "$2")
mkdir "$work"
root=$(git rev-parse --show-toplevel)
here="$root/docs/validation/v110-forward"
frozen=25ce3a990ccef9e2daa8937f0c09023498ef4cb5
candidate=a9839358a53adecbb03846e7919d0a00506fd3d3
mkdir "$work/baseline" "$work/candidate"
git -C "$root" archive "$frozen" src | tar -x -C "$work/baseline"
git -C "$root" archive "$candidate" src tests pyproject.toml docs/validation/readthrough-singlecopy | tar -x -C "$work/candidate"
core=$(command -v peanalyzer-crispresso)
(
    cd "$work/candidate"
    export PYTHONPATH="$work/candidate/src"
    M4_RESULTS_DIR="$work/m4" M3_CORE_EXECUTABLE="$core" M4_INTEGRATION=1 python -m pytest -q tests/test_m4_integration.py
    python -m pytest -q tests/test_readthrough.py tests/test_readthrough_singlecopy.py --junitxml="$work/readthrough-tests.xml"
)
for name in baseline candidate; do
    PYTHONPATH="$work/$name/src" python "$here/forward_calls.py" "$work/m4" "$work/$name-synthetic.csv"
    PYTHONPATH="$work/$name/src" python "$here/compare_alsw.py" "$inputs" "$work/$name.csv.gz"
done
PYTHONPATH="$work/candidate/src" python "$here/compare_alsw.py" --oracle "$inputs" "$work/oracle.csv.gz"
PYTHONPATH="$work/candidate/src" python "$here/collect.py" "$work" "$work/m4" "$work/evidence.json" --candidate "$candidate"
diff -u "$here/evidence.json" "$work/evidence.json"
