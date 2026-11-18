#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Usage: bash run-regression.sh INPUT_DIRECTORY NEW_OUTPUT_DIRECTORY" >&2
    exit 2
fi
here=$(cd -- "$(dirname -- "$0")" && pwd)
# Reproduce the historical failure with its original classifier, including when
# the current checkout contains a newer candidate that fixes that failure.
baseline=25ce3a990ccef9e2daa8937f0c09023498ef4cb5
baseline_dir=$(mktemp -d)
trap 'rm -rf -- "$baseline_dir"' EXIT
git -C "$(git -C "$here" rev-parse --show-toplevel)" archive "$baseline" src/peanalyzer | tar -x -C "$baseline_dir"
(
export PYTHONPATH="$baseline_dir/src${PYTHONPATH:+:$PYTHONPATH}"
python "$here/audit.py" "$1" "$2"
python "$here/verify_pairs.py" "$1" "$2"
for population in 1A all_known; do
    python "$here/run_core.py" "$1" "$2" "$population"
done
python "$here/recount_core.py" "$1" "$2"
for baseline in "$here"/evidence/*; do
    diff -u "$baseline" "$2/${baseline##*/}"
done
)
python "$here/compare_candidate.py" "$1" "$2/candidate"
echo 'PASS: hash-identified raw regression, independent recount and pinned Core comparison.'
