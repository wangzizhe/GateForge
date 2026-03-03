#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export GATEFORGE_MODEL_SCALE_PROFILE="${GATEFORGE_MODEL_SCALE_PROFILE:-large_first}"
export GATEFORGE_MIN_DISCOVERED_MODELS="${GATEFORGE_MIN_DISCOVERED_MODELS:-20}"
export GATEFORGE_MIN_ACCEPTED_MODELS="${GATEFORGE_MIN_ACCEPTED_MODELS:-15}"
export GATEFORGE_MIN_ACCEPTED_LARGE_MODELS="${GATEFORGE_MIN_ACCEPTED_LARGE_MODELS:-8}"
export GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT="${GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT:-30}"
export GATEFORGE_MIN_GENERATED_MUTATIONS="${GATEFORGE_MIN_GENERATED_MUTATIONS:-3000}"
export GATEFORGE_MIN_MUTATION_PER_MODEL="${GATEFORGE_MIN_MUTATION_PER_MODEL:-10}"
export GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS="${GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS:-2200}"
export GATEFORGE_MUTATIONS_PER_FAILURE_TYPE="${GATEFORGE_MUTATIONS_PER_FAILURE_TYPE:-6}"
export GATEFORGE_DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE="${GATEFORGE_DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE:-70}"
export GATEFORGE_DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE="${GATEFORGE_DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE:-120}"
export GATEFORGE_PRIVATE_BATCH_OUT_DIR="${GATEFORGE_PRIVATE_BATCH_OUT_DIR:-artifacts/private_model_mutation_largefirst_sprint_v1}"

bash scripts/run_private_model_mutation_scale_batch_v1.sh

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["GATEFORGE_PRIVATE_BATCH_OUT_DIR"])
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))

payload = {
    "scale_gate_status": summary.get("scale_gate_status"),
    "model_scale_profile": summary.get("model_scale_profile"),
    "accepted_models": summary.get("accepted_models"),
    "accepted_large_models": summary.get("accepted_large_models"),
    "accepted_large_ratio_pct": summary.get("accepted_large_ratio_pct"),
    "min_accepted_large_ratio_pct": summary.get("min_accepted_large_ratio_pct"),
    "generated_mutations": summary.get("generated_mutations"),
    "reproducible_mutations": summary.get("reproducible_mutations"),
}
print(json.dumps(payload))
if str(summary.get("scale_gate_status") or "") != "PASS":
    raise SystemExit(1)
if str(summary.get("model_scale_profile") or "") != "large_first":
    raise SystemExit(1)
PY
