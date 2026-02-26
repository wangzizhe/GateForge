#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_anchor_benchmark_artifact_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/baseline_summary.json" <<'JSON'
{"status": "PASS", "baseline_id": "failure_baseline_v1", "total_selected_cases": 12}
JSON
cat > "$OUT_DIR/quality_gate.json" <<'JSON'
{"status": "PASS", "gate_result": "PASS"}
JSON
cat > "$OUT_DIR/external_proof_score.json" <<'JSON'
{"status": "PASS", "proof_score": 82.5}
JSON

python3 -m gateforge.dataset_anchor_benchmark_artifact_v1 \
  --failure-baseline-pack-summary "$OUT_DIR/baseline_summary.json" \
  --failure-distribution-quality-gate "$OUT_DIR/quality_gate.json" \
  --external-proof-score "$OUT_DIR/external_proof_score.json" \
  --reproducible-command "bash scripts/demo_dataset_failure_baseline_pack_v1.sh" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_anchor_benchmark_artifact_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "anchor_ready_present": "PASS" if isinstance(summary.get("anchor_ready"), bool) else "FAIL",
    "anchor_score_present": "PASS" if isinstance(summary.get("anchor_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "anchor_status": summary.get("status"),
    "anchor_ready": summary.get("anchor_ready"),
    "anchor_score": summary.get("anchor_score"),
    "baseline_id": summary.get("baseline_id"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "anchor_status": summary_out["anchor_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
