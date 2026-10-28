#!/usr/bin/env bash
# Inspection only: no installation, directory creation, lock acquisition or signals.
set -euo pipefail
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B "$script_dir/doctor.py" "$@"
