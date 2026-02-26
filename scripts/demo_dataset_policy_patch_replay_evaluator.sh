#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_policy_patch_replay_evaluator_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/before_benchmark.json" <<'JSON'
{"detection_rate_after":0.78,"false_positive_rate_after":0.12,"regression_rate_after":0.21}
JSON

cat > "$OUT_DIR/after_benchmark.json" <<'JSON'
{"detection_rate_after":0.85,"false_positive_rate_after":0.08,"regression_rate_after":0.14}
JSON

cat > "$OUT_DIR/before_snapshot.json" <<'JSON'
{"risks":["r1","r2","r3"]}
JSON

cat > "$OUT_DIR/after_snapshot.json" <<'JSON'
{"risks":["r1"]}
JSON

cat > "$OUT_DIR/advisor.json" <<'JSON'
{"advice":{"suggested_action":"targeted_threshold_patch"}}
JSON

cat > "$OUT_DIR/apply_summary.json" <<'JSON'
{"final_status":"PASS"}
JSON

python3 -m gateforge.dataset_policy_patch_replay_evaluator \
  --before-benchmark "$OUT_DIR/before_benchmark.json" \
  --after-benchmark "$OUT_DIR/after_benchmark.json" \
  --before-snapshot "$OUT_DIR/before_snapshot.json" \
  --after-snapshot "$OUT_DIR/after_snapshot.json" \
  --patch-advisor "$OUT_DIR/advisor.json" \
  --patch-apply-summary "$OUT_DIR/apply_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_policy_patch_replay_evaluator_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "recommendation_present": "PASS" if isinstance(payload.get("recommendation"), str) else "FAIL",
    "delta_present": "PASS" if isinstance(payload.get("delta"), dict) else "FAIL",
    "score_present": "PASS" if isinstance(payload.get("evaluation_score"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "evaluator_status": payload.get("status"),
    "recommendation": payload.get("recommendation"),
    "evaluation_score": payload.get("evaluation_score"),
    "delta_detection_rate": (payload.get("delta") or {}).get("detection_rate"),
    "delta_regression_rate": (payload.get("delta") or {}).get("regression_rate"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Policy Patch Replay Evaluator Demo",
            "",
            f"- evaluator_status: `{summary['evaluator_status']}`",
            f"- recommendation: `{summary['recommendation']}`",
            f"- evaluation_score: `{summary['evaluation_score']}`",
            f"- delta_detection_rate: `{summary['delta_detection_rate']}`",
            f"- delta_regression_rate: `{summary['delta_regression_rate']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "evaluator_status": summary["evaluator_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
