#!/usr/bin/env bash
set -euo pipefail
release_dir=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" && pwd)
python_bin="$release_dir/venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  echo "Missing release virtual environment: $python_bin" >&2
  exit 1
fi
package_version=$("$python_bin" -c 'from importlib.metadata import version; print(version("crispresso-pe-pipeline"))')
if [[ ! "$package_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Unsupported installed release version: $package_version" >&2
  exit 1
fi
library_root=${PEANALYZER_LIBRARY_ROOT:-"$HOME/PEAnalyzer-analyses"}
output_root="$library_root/v$package_version"
mkdir -p -- "$output_root"
# The existing qualified wrapper must still enforce the pinned Core runtime.
core_command=${PEANALYZER_CRISPRESSO:-"$release_dir/bin/CRISPResso"}
if [[ ! -x "$core_command" ]]; then
  echo "Set PEANALYZER_CRISPRESSO to your qualified CRISPResso 2.3.4 wrapper." >&2
  exit 1
fi
docker info >/dev/null
printf 'Starting PEAnalyzer %s\n' "$package_version"
printf 'Analysis library: %s\n' "$library_root"
exec "$python_bin" -m peanalyzer.gui --workspace-library-root "$library_root" \
  --setup-output-root "$output_root" --run-crispresso "$core_command" "$@"
