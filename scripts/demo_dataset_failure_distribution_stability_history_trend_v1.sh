#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_failure_distribution_stability_history_trend_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/previous.json" <<'JSON'
{"status":"PASS","avg_stability_score":82.0,"avg_distribution_drift_score":0.14,"avg_rare_failure_replay_rate":0.9}
JSON
cat > "$OUT_DIR/current.json" <<'JSON'
{"status":"NEEDS_REVIEW","avg_stability_score":74.0,"avg_distribution_drift_score":0.24,"avg_rare_failure_replay_rate":0.6}
JSON

python3 -m gateforge.dataset_failure_distribution_stability_history_trend_v1 \
  --current "$OUT_DIR/current.json" \
  --previous "$OUT_DIR/previous.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_failure_distribution_stability_history_trend_v1_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = payload.get("trend") or {}
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "transition_present": "PASS" if isinstance(trend.get("status_transition"), str) and "->" in trend.get("status_transition") else "FAIL",
    "alerts_present": "PASS" if isinstance(trend.get("alerts"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "trend_status": payload.get("status"),
    "status_transition": trend.get("status_transition"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "trend_status": summary["trend_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
