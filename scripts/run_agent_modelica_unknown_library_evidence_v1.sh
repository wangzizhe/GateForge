#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_unknown_library_evidence_v1}"
MANIFEST_PATH="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MANIFEST:-assets_private/agent_modelica_unknown_library_pool_v1/manifest.json}"
REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_REPAIR_MEMORY:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
FAILURE_TYPES="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_FAILURE_TYPES:-underconstrained_system,connector_mismatch,initialization_infeasible}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_SPLIT_SEED:-agent_modelica_unknown_library_taskset_v1}"
MIN_RETRIEVAL_COVERAGE_PCT="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MIN_RETRIEVAL_COVERAGE_PCT:-50.0}"
MIN_DIAGNOSTIC_PARSE_COVERAGE_PCT="${GATEFORGE_AGENT_UNKNOWN_LIBRARY_MIN_DIAGNOSTIC_PARSE_COVERAGE_PCT:-95.0}"

CHALLENGE_DIR="$OUT_DIR/challenge"
CURATED_DIR="$OUT_DIR/curated_retrieval"
BASELINE_DIR="$OUT_DIR/baseline_off"
RETRIEVAL_DIR="$OUT_DIR/retrieval_on"

mkdir -p "$OUT_DIR" "$CHALLENGE_DIR" "$CURATED_DIR" "$BASELINE_DIR" "$RETRIEVAL_DIR"

python3 -m gateforge.agent_modelica_unknown_library_taskset_v1 \
  --manifest "$MANIFEST_PATH" \
  --out-dir "$CHALLENGE_DIR" \
  --failure-types "$FAILURE_TYPES" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --seed "$SPLIT_SEED"

python3 -m gateforge.agent_modelica_unknown_library_curated_retrieval_v1 \
  --manifest "$MANIFEST_PATH" \
  --failure-types "$FAILURE_TYPES" \
  --history-out "$CURATED_DIR/history.json" \
  --out "$CURATED_DIR/summary.json"

python3 - "$REPAIR_MEMORY_PATH" "$CURATED_DIR/history.json" "$OUT_DIR/merged_repair_history.json" <<'PY'
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
curated_rows = curated.get("rows") if isinstance(curated.get("rows"), list) else []
rows.extend([row for row in curated_rows if isinstance(row, dict)])

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(
    json.dumps(
        {
            "schema_version": "agent_modelica_unknown_library_merged_history_v1",
            "rows": rows,
        },
        indent=2,
    ),
    encoding="utf-8",
)
PY

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
  --mode mock \
  --results-out "$BASELINE_DIR/results.json" \
  --out "$BASELINE_DIR/summary.json"

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
  --mode mock \
  --repair-history "$OUT_DIR/merged_repair_history.json" \
  --results-out "$RETRIEVAL_DIR/results.json" \
  --out "$RETRIEVAL_DIR/summary.json"

python3 -m gateforge.agent_modelica_unknown_library_retrieval_summary_v1 \
  --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
  --results "$RETRIEVAL_DIR/results.json" \
  --out "$OUT_DIR/retrieval_summary.json"

python3 -m gateforge.agent_modelica_unknown_library_evidence_v1 \
  --challenge-summary "$CHALLENGE_DIR/summary.json" \
  --baseline-off-summary "$BASELINE_DIR/summary.json" \
  --baseline-off-results "$BASELINE_DIR/results.json" \
  --retrieval-on-summary "$RETRIEVAL_DIR/summary.json" \
  --retrieval-on-results "$RETRIEVAL_DIR/results.json" \
  --retrieval-summary "$OUT_DIR/retrieval_summary.json" \
  --min-retrieval-coverage-pct "$MIN_RETRIEVAL_COVERAGE_PCT" \
  --min-diagnostic-parse-coverage-pct "$MIN_DIAGNOSTIC_PARSE_COVERAGE_PCT" \
  --out "$OUT_DIR/evidence_summary.json" \
  --gate-out "$OUT_DIR/gate_summary.json" \
  --decision-out "$OUT_DIR/decision_summary.json"

cat "$OUT_DIR/decision_summary.json"

