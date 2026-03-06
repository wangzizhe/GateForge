#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_CORE_VIEW_OUT_DIR:-artifacts/agent_modelica_core_view_v1}"
SCOPE_PATH="${GATEFORGE_AGENT_CORE_SCOPE_PATH:-core/agent_modelica/core_scope_v1.json}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_core_scope_snapshot_v1 \
  --repo-root "$ROOT_DIR" \
  --scope "$SCOPE_PATH" \
  --out "$OUT_DIR/snapshot.json" \
  --report-out "$OUT_DIR/snapshot.md"

cat "$OUT_DIR/snapshot.json"
