#!/usr/bin/env bash
set -euo pipefail

# PEAnalyzer version-neutral WSL launcher with best-effort Windows browser opening.
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
core_command=${PEANALYZER_CRISPRESSO:-"$release_dir/bin/CRISPResso"}
if [[ ! -x "$core_command" ]]; then
  echo "Set PEANALYZER_CRISPRESSO to your qualified CRISPResso 2.3.4 wrapper." >&2
  exit 1
fi
# Work from Linux home; avoid inheriting /mnt/c paths for the Docker wrapper.
cd "$HOME"
docker info >/dev/null
printf 'Starting PEAnalyzer %s\n' "$package_version"
printf 'Analysis library: %s\n' "$library_root"

# Keep the token-bearing URL in a private, unique log instead of using a static file.
launch_log=$(mktemp "${TMPDIR:-/tmp}/peanalyzer-launch.XXXXXXXX.log")
chmod 600 "$launch_log"

"$python_bin" -u -m peanalyzer.gui --workspace-library-root "$library_root" \
  --setup-output-root "$output_root" --run-crispresso "$core_command" "$@" \
  > >(tee "$launch_log") 2>&1 &
server_pid=$!
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  rm -f -- "$launch_log"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

url=""
for ((attempt=0; attempt<150; attempt++)); do
  url=$(grep -oEm1 'http://127\.0\.0\.1:[0-9]+/#[A-Za-z0-9_-]+' "$launch_log" || true)
  if [[ -n "$url" ]]; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo 'ERROR: PEAnalyzer exited before publishing its local URL.' >&2
    wait "$server_pid"
    exit $?
  fi
  sleep 0.1
done

if [[ -n "$url" ]]; then
  printf 'PEAnalyzer local URL: %s\n' "$url"
  if command -v powershell.exe >/dev/null 2>&1; then
    # The URL is server-generated: localhost + port + URL-safe hash token only.
    # Start-Process uses the Windows default URL handler (no shell execution).
    if ! powershell.exe -NoProfile -NonInteractive -Command "Start-Process -FilePath '$url'" >/dev/null 2>&1; then
      echo 'Browser auto-open failed; open the printed local URL manually.' >&2
    fi
  else
    echo 'Windows PowerShell interop is unavailable; open the printed local URL manually.' >&2
  fi
else
  echo 'Browser auto-open skipped: no local URL appeared. Check the startup output.' >&2
fi

# Keep WSL running as long as the PEAnalyzer GUI server is running.
wait "$server_pid"
