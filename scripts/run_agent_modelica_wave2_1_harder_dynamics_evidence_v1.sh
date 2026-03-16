#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_OUT_DIR:-artifacts/agent_modelica_wave2_1_harder_dynamics_evidence_v1}"
MANIFEST_PATH="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_MANIFEST:-assets_private/agent_modelica_wave2_1_harder_dynamics_pack_v1/manifest.json}"
FAILURE_TYPES="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_FAILURE_TYPES:-solver_sensitive_simulate_failure,event_logic_error,semantic_drift_after_compile_pass}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_SPLIT_SEED:-agent_modelica_wave2_1_harder_dynamics_taskset_v1}"
REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"

CHALLENGE_DIR="$OUT_DIR/challenge"
CURATED_DIR="$OUT_DIR/curated_retrieval"
BASELINE_DIR="$OUT_DIR/baseline_off"
DETERMINISTIC_DIR="$OUT_DIR/deterministic_on"
RETRIEVAL_DIR="$OUT_DIR/retrieval_on"

python3 -m gateforge.agent_modelica_wave2_1_harder_dynamics_taskset_v1 \
  --manifest "$MANIFEST_PATH" \
  --out-dir "$CHALLENGE_DIR" \
  --failure-types "$FAILURE_TYPES" \
  --holdout-ratio "$HOLDOUT_RATIO" \
  --seed "$SPLIT_SEED"

python3 -m gateforge.agent_modelica_wave2_1_curated_retrieval_v1 \
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
    payload = json.loads(memory_path.read_text(encoding="utf-8"))
    source_rows = payload.get("rows") if isinstance(payload.get("rows"), list) else payload.get("records")
    if isinstance(source_rows, list):
        rows.extend([row for row in source_rows if isinstance(row, dict)])
curated = json.loads(curated_path.read_text(encoding="utf-8"))
rows.extend([row for row in (curated.get("rows") or []) if isinstance(row, dict)])
out_path.write_text(json.dumps({"schema_version": "agent_modelica_wave2_1_merged_history_v1", "rows": rows}, indent=2), encoding="utf-8")
PY

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
  --mode mock \
  --results-out "$BASELINE_DIR/results.json" \
  --out "$BASELINE_DIR/summary.json"

env GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR=1 \
python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset "$CHALLENGE_DIR/taskset_frozen.json" \
  --mode mock \
  --results-out "$DETERMINISTIC_DIR/results.json" \
  --out "$DETERMINISTIC_DIR/summary.json"

env GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR=1 \
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

python3 -m gateforge.agent_modelica_wave2_1_baseline_summary_v1 \
  --challenge-summary "$CHALLENGE_DIR/summary.json" \
  --baseline-summary "$BASELINE_DIR/summary.json" \
  --baseline-results "$BASELINE_DIR/results.json" \
  --out "$OUT_DIR/wave2_1_baseline_summary.json"

python3 -m gateforge.agent_modelica_wave2_1_evidence_v1 \
  --challenge-summary "$CHALLENGE_DIR/summary.json" \
  --baseline-summary "$BASELINE_DIR/summary.json" \
  --baseline-results "$BASELINE_DIR/results.json" \
  --deterministic-summary "$DETERMINISTIC_DIR/summary.json" \
  --deterministic-results "$DETERMINISTIC_DIR/results.json" \
  --retrieval-summary "$RETRIEVAL_DIR/summary.json" \
  --retrieval-results "$RETRIEVAL_DIR/results.json" \
  --retrieval-audit-summary "$OUT_DIR/retrieval_summary.json" \
  --out "$OUT_DIR/evidence_summary.json" \
  --gate-out "$OUT_DIR/gate_summary.json" \
  --decision-out "$OUT_DIR/decision_summary.json"
