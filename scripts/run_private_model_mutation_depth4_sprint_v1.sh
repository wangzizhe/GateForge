#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export GATEFORGE_MIN_DISCOVERED_MODELS="${GATEFORGE_MIN_DISCOVERED_MODELS:-12}"
export GATEFORGE_MIN_ACCEPTED_MODELS="${GATEFORGE_MIN_ACCEPTED_MODELS:-8}"
export GATEFORGE_MIN_ACCEPTED_LARGE_MODELS="${GATEFORGE_MIN_ACCEPTED_LARGE_MODELS:-2}"
export GATEFORGE_MIN_GENERATED_MUTATIONS="${GATEFORGE_MIN_GENERATED_MUTATIONS:-1200}"
export GATEFORGE_MIN_MUTATION_PER_MODEL="${GATEFORGE_MIN_MUTATION_PER_MODEL:-8}"
export GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS="${GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS:-900}"
export GATEFORGE_MUTATIONS_PER_FAILURE_TYPE="${GATEFORGE_MUTATIONS_PER_FAILURE_TYPE:-4}"
export GATEFORGE_PRIVATE_BATCH_OUT_DIR="${GATEFORGE_PRIVATE_BATCH_OUT_DIR:-artifacts/private_model_mutation_scale_depth4_sprint_v1}"

BASELINE_SUMMARY="${GATEFORGE_BASELINE_SCALE_SUMMARY:-artifacts/private_model_mutation_scale_sprint_v1/summary.json}"
OUT_DIR="${GATEFORGE_PRIVATE_BATCH_OUT_DIR}"

bash scripts/run_private_model_mutation_scale_batch_v1.sh

python3 -m gateforge.dataset_mutation_depth_upgrade_report_v1 \
  --current-scale-summary "$OUT_DIR/summary.json" \
  --baseline-scale-summary "$BASELINE_SUMMARY" \
  --target-mutations-per-failure-type 4 \
  --out "$OUT_DIR/depth_upgrade_report.json" \
  --report-out "$OUT_DIR/depth_upgrade_report.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["GATEFORGE_PRIVATE_BATCH_OUT_DIR"])
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
depth = json.loads((out / "depth_upgrade_report.json").read_text(encoding="utf-8"))

payload = {
    "scale_gate_status": summary.get("scale_gate_status"),
    "accepted_models": summary.get("accepted_models"),
    "accepted_large_models": summary.get("accepted_large_models"),
    "generated_mutations": summary.get("generated_mutations"),
    "reproducible_mutations": summary.get("reproducible_mutations"),
    "mutations_per_failure_type": summary.get("mutations_per_failure_type"),
    "depth_upgrade_status": depth.get("upgrade_status"),
    "generated_mutation_multiplier": depth.get("generated_mutation_multiplier"),
    "reproducibility_ratio_pct": depth.get("reproducibility_ratio_pct"),
}
print(json.dumps(payload))
if str(summary.get("scale_gate_status") or "") != "PASS":
    raise SystemExit(1)
PY
