#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_2}"

exec bash scripts/run_agent_modelica_release_preflight_v0_1_1.sh
