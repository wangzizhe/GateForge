#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
OUT_DIR="artifacts/dataset_failure_signal_calibrator_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/failure_distribution_benchmark.json" <<'JSON'
{"distribution_drift_score": 0.33, "false_positive_rate_after": 0.09, "regression_rate_after": 0.16}
JSON
cat > "$OUT_DIR/policy_patch_replay_evaluator.json" <<'JSON'
{"delta": {"detection_rate": -0.01}}
JSON

python3 -m gateforge.dataset_failure_signal_calibrator \
  --failure-distribution-benchmark "$OUT_DIR/failure_distribution_benchmark.json" \
  --policy-patch-replay-evaluator "$OUT_DIR/policy_patch_replay_evaluator.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_failure_signal_calibrator_demo")
p = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {"status_present": "PASS" if p.get("status") in {"PASS","NEEDS_REVIEW","FAIL"} else "FAIL", "weights_present": "PASS" if isinstance(p.get("weights"), dict) else "FAIL"}
summary = {"calibrator_status": p.get("status"), "calibration_mode": p.get("calibration_mode"), "result_flags": flags, "bundle_status": "PASS" if all(v=="PASS" for v in flags.values()) else "FAIL"}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "calibrator_status": summary["calibrator_status"]}))
if summary["bundle_status"] != "PASS":
  raise SystemExit(1)
PY
