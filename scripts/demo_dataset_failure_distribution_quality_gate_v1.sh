#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_distribution_quality_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/pack.json" <<'JSON'
{
  "selected_cases": [
    {"model_scale": "small", "failure_type": "a"},
    {"model_scale": "small", "failure_type": "b"},
    {"model_scale": "medium", "failure_type": "c"},
    {"model_scale": "medium", "failure_type": "d"},
    {"model_scale": "large", "failure_type": "e"},
    {"model_scale": "large", "failure_type": "f"}
  ]
}
JSON

python3 -m gateforge.dataset_failure_distribution_quality_gate_v1 \
  --failure-baseline-pack "$OUT_DIR/pack.json" \
  --min-medium-share-pct 25 \
  --min-large-share-pct 20 \
  --min-unique-failure-types 5 \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_failure_distribution_quality_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "gate_result_present": "PASS" if summary.get("gate_result") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "shares_present": "PASS" if isinstance(summary.get("medium_share_pct"), (int, float)) and isinstance(summary.get("large_share_pct"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "quality_gate_status": summary.get("status"),
    "gate_result": summary.get("gate_result"),
    "medium_share_pct": summary.get("medium_share_pct"),
    "large_share_pct": summary.get("large_share_pct"),
    "unique_failure_types": summary.get("unique_failure_types"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "quality_gate_status": summary_out["quality_gate_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
