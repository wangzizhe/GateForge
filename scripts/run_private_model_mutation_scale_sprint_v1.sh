#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export GATEFORGE_MIN_DISCOVERED_MODELS="${GATEFORGE_MIN_DISCOVERED_MODELS:-12}"
export GATEFORGE_MIN_ACCEPTED_MODELS="${GATEFORGE_MIN_ACCEPTED_MODELS:-8}"
export GATEFORGE_MIN_ACCEPTED_LARGE_MODELS="${GATEFORGE_MIN_ACCEPTED_LARGE_MODELS:-2}"
export GATEFORGE_MIN_GENERATED_MUTATIONS="${GATEFORGE_MIN_GENERATED_MUTATIONS:-80}"
export GATEFORGE_MIN_MUTATION_PER_MODEL="${GATEFORGE_MIN_MUTATION_PER_MODEL:-6}"
export GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS="${GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS:-50}"
export GATEFORGE_PRIVATE_BATCH_OUT_DIR="${GATEFORGE_PRIVATE_BATCH_OUT_DIR:-artifacts/private_model_mutation_scale_sprint_v1}"

bash scripts/run_private_model_mutation_scale_batch_v1.sh

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["GATEFORGE_PRIVATE_BATCH_OUT_DIR"])
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
scale = json.loads((out / "scale_gate_summary.json").read_text(encoding="utf-8"))

print(
    json.dumps(
        {
            "scale_gate_status": summary.get("scale_gate_status"),
            "accepted_models": summary.get("accepted_models"),
            "accepted_large_models": summary.get("accepted_large_models"),
            "generated_mutations": summary.get("generated_mutations"),
            "reproducible_mutations": summary.get("reproducible_mutations"),
        }
    )
)

if str(summary.get("scale_gate_status") or "") != "PASS":
    alerts = scale.get("alerts") if isinstance(scale.get("alerts"), list) else []
    print(json.dumps({"sprint_status": "FAIL", "scale_gate_alerts": alerts}))
    raise SystemExit(1)
PY
