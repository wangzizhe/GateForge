#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_LEARNING_ASSET_REFRESH_OUT_DIR:-artifacts/agent_modelica_learning_asset_refresh_v1}"
REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"
PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"
RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"
BACKFILL_HOLDOUT_RATIO="${GATEFORGE_AGENT_BACKFILL_HOLDOUT_RATIO:-0.15}"
MIN_SUCCESS_COUNT="${GATEFORGE_AGENT_CAPABILITY_LEARN_MIN_SUCCESS_COUNT:-3}"
TOP_ACTIONS="${GATEFORGE_AGENT_CAPABILITY_LEARN_TOP_ACTIONS:-4}"
TOP_STRATEGIES="${GATEFORGE_AGENT_CAPABILITY_LEARN_TOP_STRATEGIES:-2}"

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_repair_memory_backfill_v1 \
  --memory "$REPAIR_MEMORY_PATH" \
  --memory-out "$REPAIR_MEMORY_PATH" \
  --holdout-ratio "$BACKFILL_HOLDOUT_RATIO" \
  --out "$OUT_DIR/repair_memory_backfill_summary.json" \
  --report-out "$OUT_DIR/repair_memory_backfill_summary.md"

python3 -m gateforge.agent_modelica_repair_capability_learner_v1 \
  --repair-memory "$REPAIR_MEMORY_PATH" \
  --min-success-count-per-failure-type "$MIN_SUCCESS_COUNT" \
  --top-actions-per-failure-type "$TOP_ACTIONS" \
  --top-strategies-per-failure-type "$TOP_STRATEGIES" \
  --out-patch-template-adaptations "$PATCH_TEMPLATE_ADAPTATIONS_PATH" \
  --out-retrieval-policy "$RETRIEVAL_POLICY_PATH" \
  --out "$OUT_DIR/capability_learner_summary.json" \
  --report-out "$OUT_DIR/capability_learner_summary.md"

export GATEFORGE_AGENT_LEARNING_ASSET_REFRESH_OUT_DIR="$OUT_DIR"
python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(str(os.getenv("GATEFORGE_AGENT_LEARNING_ASSET_REFRESH_OUT_DIR") or "artifacts/agent_modelica_learning_asset_refresh_v1"))
backfill = json.loads((out_dir / "repair_memory_backfill_summary.json").read_text(encoding="utf-8"))
learner = json.loads((out_dir / "capability_learner_summary.json").read_text(encoding="utf-8"))
print(json.dumps({
    "status": "PASS",
    "backfill_updated_rows": backfill.get("updated_rows"),
    "filled_library_hints": backfill.get("filled_library_hints"),
    "filled_component_hints": backfill.get("filled_component_hints"),
    "filled_connector_hints": backfill.get("filled_connector_hints"),
    "filled_split": backfill.get("filled_split"),
    "learned_failure_type_count": learner.get("learned_failure_type_count"),
    "retrieval_policy_path": learner.get("out_retrieval_policy"),
    "patch_template_adaptations_path": learner.get("out_patch_template_adaptations"),
}))
PY
