#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_replay_quality_guard_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/replay_eval_summary.json" <<'JSON'
{"delta":{"detection_rate":0.04,"false_positive_rate":-0.01,"regression_rate":-0.03,"review_load":-1}}
JSON

cat > "$OUT_DIR/before_benchmark.json" <<'JSON'
{"total_cases_after":28}
JSON

cat > "$OUT_DIR/after_benchmark.json" <<'JSON'
{"total_cases_after":32}
JSON

python3 -m gateforge.dataset_replay_quality_guard \
  --replay-evaluator "$OUT_DIR/replay_eval_summary.json" \
  --before-benchmark "$OUT_DIR/before_benchmark.json" \
  --after-benchmark "$OUT_DIR/after_benchmark.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_replay_quality_guard_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "confidence_present": "PASS" if payload.get("confidence_level") in {"low", "medium", "high"} else "FAIL",
    "samples_present": "PASS" if isinstance(payload.get("sample_size_after"), int) else "FAIL",
    "reasons_present": "PASS" if isinstance(payload.get("reasons"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "guard_status": payload.get("status"),
    "confidence_level": payload.get("confidence_level"),
    "sample_size_before": payload.get("sample_size_before"),
    "sample_size_after": payload.get("sample_size_after"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Replay Quality Guard Demo",
            "",
            f"- guard_status: `{summary['guard_status']}`",
            f"- confidence_level: `{summary['confidence_level']}`",
            f"- sample_size_before: `{summary['sample_size_before']}`",
            f"- sample_size_after: `{summary['sample_size_after']}`",
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
print(json.dumps({"bundle_status": bundle_status, "guard_status": summary["guard_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
