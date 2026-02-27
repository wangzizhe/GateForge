#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_intake_weekly_target_guard_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{
  "status": "PASS",
  "accepted_count": 4,
  "accepted_large_count": 1,
  "reject_rate_pct": 22.5,
  "weekly_target_status": "PASS"
}
JSON

python3 -m gateforge.dataset_real_model_intake_weekly_target_guard_v1 \
  --intake-summary "$OUT_DIR/intake_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_intake_weekly_target_guard_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "gaps_present": "PASS" if isinstance(summary.get("target_gaps"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "guard_status": summary.get("status"),
    "target_gap_count": len(summary.get("target_gaps") or []),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "guard_status": demo["guard_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
