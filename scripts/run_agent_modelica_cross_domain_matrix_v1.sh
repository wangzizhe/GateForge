#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TRACK_ID="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_ID:-buildings_v1}"
LIBRARY="${GATEFORGE_AGENT_CROSS_DOMAIN_LIBRARY:-Buildings}"
PACK_PATH="${GATEFORGE_AGENT_CROSS_DOMAIN_PACK:-assets_private/agent_modelica_cross_domain_${TRACK_ID}_fixture_v1/hardpack_frozen.json}"
OUT_DIR="${GATEFORGE_AGENT_CROSS_DOMAIN_MATRIX_OUT_DIR:-artifacts/agent_modelica_cross_domain_matrix_v1/$TRACK_ID}"
PLANNER_BACKEND="${GATEFORGE_AGENT_CROSS_DOMAIN_PLANNER_BACKEND:-auto}"
COMPARISON_BACKEND="${GATEFORGE_AGENT_CROSS_DOMAIN_COMPARISON_BACKEND:-auto}"
MAX_ROUNDS="${GATEFORGE_AGENT_CROSS_DOMAIN_MAX_ROUNDS:-8}"
TIMEOUT_SEC="${GATEFORGE_AGENT_CROSS_DOMAIN_TIMEOUT_SEC:-300}"
COMPARISON_TIMEOUT_SEC="${GATEFORGE_AGENT_CROSS_DOMAIN_COMPARISON_TIMEOUT_SEC:-120}"
EXPERIENCE_SOURCE="${GATEFORGE_AGENT_CROSS_DOMAIN_EXPERIENCE_SOURCE:-}"
PLANNER_EXPERIENCE_MAX_TOKENS="${GATEFORGE_AGENT_CROSS_DOMAIN_PLANNER_EXPERIENCE_MAX_TOKENS:-400}"
DRY_RUN="${GATEFORGE_AGENT_CROSS_DOMAIN_DRY_RUN:-0}"

ARGS=(
  --track-id "$TRACK_ID"
  --library "$LIBRARY"
  --pack "$PACK_PATH"
  --out-dir "$OUT_DIR"
  --planner-backend "$PLANNER_BACKEND"
  --comparison-backend "$COMPARISON_BACKEND"
  --max-rounds "$MAX_ROUNDS"
  --timeout-sec "$TIMEOUT_SEC"
  --comparison-timeout-sec "$COMPARISON_TIMEOUT_SEC"
  --planner-experience-max-tokens "$PLANNER_EXPERIENCE_MAX_TOKENS"
)

if [ -n "$EXPERIENCE_SOURCE" ]; then
  ARGS+=(--experience-source "$EXPERIENCE_SOURCE")
fi
if [ "$DRY_RUN" = "1" ]; then
  ARGS+=(--dry-run)
fi

python3 -m gateforge.agent_modelica_cross_domain_matrix_runner_v1 "${ARGS[@]}"
cat "$OUT_DIR/matrix_summary.json"
