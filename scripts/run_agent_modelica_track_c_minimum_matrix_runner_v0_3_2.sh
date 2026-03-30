#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m gateforge.agent_modelica_track_c_minimum_matrix_runner_v0_3_2 "$@"
