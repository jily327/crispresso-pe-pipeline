#!/usr/bin/env bash
# Provision native executables from the exact previously qualified image.
# Docker is used only to copy files from a STOPPED container, never to run science.
set -euo pipefail
[[ $# -le 1 ]] || { echo "Usage: $0 [NEW_RUNTIME_DIRECTORY]" >&2; exit 2; }
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'Requires x86_64 Linux/WSL2.' >&2; exit 2; }
dest=${1:-"$HOME/peanalyzer/runtime/crispresso-2.3.4"}
[[ "$dest" = /* && ! -e "$dest" && ! -L "$dest" ]] || { echo 'Choose a new absolute runtime directory. Nothing overwritten.' >&2; exit 2; }
image=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
docker info >/dev/null
docker pull --platform linux/amd64 "$image"
cid=$(docker create --platform linux/amd64 "$image")
trap 'docker rm "$cid" >/dev/null' EXIT
mkdir -p -- "$dest/bin" "$dest/cache/matplotlib"
docker cp "$cid:/CRISPResso2" "$dest/CRISPResso2"
docker image inspect --format '{{.Id}}' "$image" > "$dest/image-id.txt"
printf '%s\n' "$image" > "$dest/image-reference.txt"
cat > "$dest/bin/CRISPResso" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
base=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
runtime="$base/CRISPResso2"
export PYTHONPATH="$runtime"
export PYTHONDONTWRITEBYTECODE=1
export PATH="$runtime/.pixi/envs/default/bin:$PATH"
export LD_LIBRARY_PATH="$runtime/.pixi/envs/default/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MPLCONFIGDIR="$base/cache/matplotlib"
exec "$runtime/.pixi/envs/default/bin/python" "$runtime/.pixi/envs/default/bin/CRISPResso" "$@"
WRAPPER
chmod 755 "$dest/bin/CRISPResso"
"$dest/bin/CRISPResso" --version
"$dest/CRISPResso2/.pixi/envs/default/bin/fastp" --version
printf '\nNative Core executable: %s/bin/CRISPResso\nKeep this directory in place.\n' "$dest"
