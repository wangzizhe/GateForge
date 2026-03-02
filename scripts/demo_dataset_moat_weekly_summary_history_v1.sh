#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_weekly_summary_history_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/history.jsonl

cat > "$OUT_DIR/w1.json" <<'JSON'
{"status":"PASS","week_tag":"2026-W09","kpis":{"real_model_count":10,"reproducible_mutation_count":30,"failure_distribution_stability_score":88.0,"gateforge_vs_plain_ci_advantage_score":8}}
JSON
cat > "$OUT_DIR/w2.json" <<'JSON'
{"status":"PASS","week_tag":"2026-W10","kpis":{"real_model_count":12,"reproducible_mutation_count":36,"failure_distribution_stability_score":90.0,"gateforge_vs_plain_ci_advantage_score":10}}
JSON

python3 -m gateforge.dataset_moat_weekly_summary_history_v1 \
  --record "$OUT_DIR/w1.json" \
  --record "$OUT_DIR/w2.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_weekly_summary_history_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "records_present": "PASS" if isinstance(summary.get("total_records"), int) and summary.get("total_records") >= 2 else "FAIL",
    "avg_present": "PASS" if isinstance(summary.get("avg_stability_score"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "history_status": summary.get("status"),
    "total_records": summary.get("total_records"),
    "latest_week_tag": summary.get("latest_week_tag"),
    "avg_stability_score": summary.get("avg_stability_score"),
    "avg_advantage_score": summary.get("avg_advantage_score"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "history_status": payload["history_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
