#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_mutation_scale_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/discovery_summary.json" <<'JSON'
{"status":"PASS","total_candidates":8}
JSON

cat > "$OUT_DIR/intake_pipeline_summary.json" <<'JSON'
{"status":"PASS","accepted_count":6}
JSON

cat > "$OUT_DIR/intake_runner_summary.json" <<'JSON'
{"status":"PASS","accepted_count":5,"accepted_large_count":2}
JSON

cat > "$OUT_DIR/mutation_pack_summary.json" <<'JSON'
{"status":"PASS","total_mutations":30}
JSON

cat > "$OUT_DIR/mutation_real_runner_summary.json" <<'JSON'
{"status":"PASS","executed_count":24}
JSON

python3 -m gateforge.dataset_real_model_mutation_scale_gate_v1 \
  --asset-discovery-summary "$OUT_DIR/discovery_summary.json" \
  --intake-pipeline-summary "$OUT_DIR/intake_pipeline_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --mutation-real-runner-summary "$OUT_DIR/mutation_real_runner_summary.json" \
  --min-reproducible-mutations 20 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_real_model_mutation_scale_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "accepted_models_present": "PASS" if int(summary.get("accepted_models", 0)) >= 5 else "FAIL",
    "mutations_present": "PASS" if int(summary.get("generated_mutations", 0)) >= 30 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({
    "scale_gate_status": summary.get("status"),
    "accepted_models": summary.get("accepted_models"),
    "generated_mutations": summary.get("generated_mutations"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "scale_gate_status": summary.get("status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
