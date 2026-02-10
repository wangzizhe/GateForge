#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m gateforge.smoke --backend openmodelica_docker --out artifacts/evidence_docker.json
cat artifacts/evidence_docker.json

