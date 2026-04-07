#!/usr/bin/env bash
# Bootstrap the OpenModelica MSL into the library cache.
# Called by CI on cache miss; safe to skip if Modelica/ already present.
set -euo pipefail

LIBRARY_CACHE="${GATEFORGE_OM_DOCKER_LIBRARY_CACHE:-$HOME/.openmodelica/libraries}"
DOCKER_IMAGE="${GATEFORGE_OM_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"

mkdir -p "$LIBRARY_CACHE"

if [ -d "$LIBRARY_CACHE/Modelica" ]; then
  echo "[bootstrap] Modelica already present at $LIBRARY_CACHE/Modelica — skipping."
  exit 0
fi

echo "[bootstrap] Installing Modelica Standard Library into $LIBRARY_CACHE ..."
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat > "$WORK/install_msl.mos" <<'EOF'
installPackage(Modelica);
getErrorString();
EOF

# Mirror the mount layout used by run_omc_script_docker so installPackage
# writes into the host-side library cache directory.
mkdir -p "$WORK/.omc_home/.openmodelica/cache"

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e HOME=/workspace/.omc_home \
  -v "$WORK:/workspace" \
  -v "$LIBRARY_CACHE:/workspace/.omc_home/.openmodelica/libraries" \
  -w /workspace \
  "$DOCKER_IMAGE" \
  omc install_msl.mos

if [ -d "$LIBRARY_CACHE/Modelica" ]; then
  echo "[bootstrap] Modelica library installed successfully."
else
  echo "[bootstrap] ERROR: Modelica library not found after install." >&2
  exit 1
fi
