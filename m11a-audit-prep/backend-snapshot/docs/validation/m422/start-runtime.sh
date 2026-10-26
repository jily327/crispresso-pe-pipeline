#!/usr/bin/env bash
# Start a new pinned container and generate direct entrypoints in a chosen path.
set -euo pipefail
tools_dir="$(realpath -m "$1")"
runtime_name="$2"
mount_root="$(realpath "$3")"
image=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
docker pull "$image"
docker run -d --name "$runtime_name" --user "$(id -u):$(id -g)" \
  -v "$mount_root:$mount_root" -v /tmp:/tmp --entrypoint /bin/sleep "$image" infinity
mkdir -p "$tools_dir"
for executable in CRISPResso CRISPRessoPooled samtools; do
  printf '#!/usr/bin/env bash\nset -euo pipefail\nexec docker exec --workdir "$PWD" %q "/CRISPResso2/.pixi/envs/default/bin/$(basename "$0")" "$@"\n' "$runtime_name" > "$tools_dir/$executable"
  chmod +x "$tools_dir/$executable"
done
"$tools_dir/CRISPResso" --version
"$tools_dir/CRISPRessoPooled" --version
"$tools_dir/samtools" --version
