#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_multi_round_failure_evidence_v1}"
MANIFEST_PATH="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_MANIFEST:-assets_private/agent_modelica_multi_round_failure_pack_v1/manifest.json}"
REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
FAILURE_TYPES="${GATEFORGE_AGENT_MULTI_ROUND_FAILURE_TYPES:-cascading_structural_failure,coupled_conflict_failure,false_friend_patch_trap}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_MULTI_ROUND_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_MULTI_ROUND_SPLIT_SEED:-agent_modelica_multi_round_failure_taskset_v1}"
VARIANT_TAG="${GATEFORGE_AGENT_MULTI_ROUND_VARIANT_TAG:-}"
ALLOW_PARTIAL_TASKSET="${GATEFORGE_AGENT_MULTI_ROUND_ALLOW_PARTIAL_TASKSET:-0}"

mkdir -p "$OUT_DIR"

TASKSET_CMD=(
  python3 -m gateforge.agent_modelica_multi_round_failure_taskset_v1
  --manifest "$MANIFEST_PATH" \
  --out-dir "$OUT_DIR/challenge" \
  --failure-types "$FAILURE_TYPES" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --seed "$SPLIT_SEED"
)
if [ -n "$VARIANT_TAG" ]; then
  TASKSET_CMD+=(--variant-tag "$VARIANT_TAG")
fi
if [ "$ALLOW_PARTIAL_TASKSET" = "1" ]; then
  TASKSET_CMD+=(--allow-partial-taskset)
fi
"${TASKSET_CMD[@]}"

python3 -m gateforge.agent_modelica_multi_round_curated_retrieval_v1 \
  --manifest "$MANIFEST_PATH" \
  --failure-types "$FAILURE_TYPES" \
  --history-out "$OUT_DIR/curated_retrieval/history.json" \
  --out "$OUT_DIR/curated_retrieval/summary.json"

python3 - "$REPAIR_MEMORY_PATH" "$OUT_DIR/curated_retrieval/history.json" "$OUT_DIR/merged_repair_history.json" <<'PY'
import json
import sys
from pathlib import Path
memory_path = Path(sys.argv[1])
curated_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])
rows = []
if memory_path.exists():
    try:
        payload = json.loads(memory_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    source_rows = payload.get("rows") if isinstance(payload.get("rows"), list) else payload.get("records")
    if isinstance(source_rows, list):
        rows.extend([row for row in source_rows if isinstance(row, dict)])
curated = json.loads(curated_path.read_text(encoding="utf-8"))
rows.extend([row for row in (curated.get("rows") or []) if isinstance(row, dict)])
out_path.write_text(json.dumps({"schema_version": "agent_modelica_multi_round_merged_history_v1", "rows": rows}, indent=2), encoding="utf-8")
PY

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/challenge/taskset_frozen.json" \
  --mode mock \
  --results-out "$OUT_DIR/baseline_off_live/results.json" \
  --out "$OUT_DIR/baseline_off_live/summary.json"

python3 -m gateforge.agent_modelica_multi_round_baseline_summary_v1 \
  --challenge-summary "$OUT_DIR/challenge/summary.json" \
  --baseline-summary "$OUT_DIR/baseline_off_live/summary.json" \
  --baseline-results "$OUT_DIR/baseline_off_live/results.json" \
  --out "$OUT_DIR/multi_round_baseline_summary.json"

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/challenge/taskset_frozen.json" \
  --mode mock \
  --results-out "$OUT_DIR/deterministic_on_live/results.json" \
  --out "$OUT_DIR/deterministic_on_live/summary.json"

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$OUT_DIR/challenge/taskset_frozen.json" \
  --mode mock \
  --repair-history "$OUT_DIR/merged_repair_history.json" \
  --results-out "$OUT_DIR/retrieval_on_live/results.json" \
  --out "$OUT_DIR/retrieval_on_live/summary.json"

python3 -m gateforge.agent_modelica_unknown_library_retrieval_summary_v1 \
  --taskset "$OUT_DIR/challenge/taskset_frozen.json" \
  --results "$OUT_DIR/retrieval_on_live/results.json" \
  --out "$OUT_DIR/retrieval_summary.json"

python3 -m gateforge.agent_modelica_multi_round_evidence_v1 \
  --challenge-summary "$OUT_DIR/challenge/summary.json" \
  --baseline-summary "$OUT_DIR/multi_round_baseline_summary.json" \
  --baseline-results "$OUT_DIR/baseline_off_live/results.json" \
  --deterministic-summary "$OUT_DIR/deterministic_on_live/summary.json" \
  --deterministic-results "$OUT_DIR/deterministic_on_live/results.json" \
  --retrieval-summary "$OUT_DIR/retrieval_on_live/summary.json" \
  --retrieval-results "$OUT_DIR/retrieval_on_live/results.json" \
  --retrieval-audit-summary "$OUT_DIR/retrieval_summary.json" \
  --out "$OUT_DIR/evidence_summary.json" \
  --gate-out "$OUT_DIR/gate_summary.json" \
  --decision-out "$OUT_DIR/decision_summary.json"
