#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_evidence_onepager_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/weekly.json" <<'JSON'
{"status":"PASS","week_tag":"2026-W10","kpis":{"real_model_count":12,"reproducible_mutation_count":36,"failure_distribution_stability_score":90.0,"gateforge_vs_plain_ci_advantage_score":10},"focus_next_week":["increase_real_model_count"]}
JSON
cat > "$OUT_DIR/history.json" <<'JSON'
{"status":"PASS","avg_stability_score":89.0,"avg_advantage_score":9.0}
JSON
cat > "$OUT_DIR/trend.json" <<'JSON'
{"status":"PASS","trend":{"status_transition":"PASS->PASS","delta_avg_stability_score":1.0}}
JSON
cat > "$OUT_DIR/runbook.json" <<'JSON'
{"status":"PASS","readiness":"READY","repro_steps":["bash scripts/demo_dataset_moat_weekly_summary_v1.sh"]}
JSON

python3 -m gateforge.dataset_moat_evidence_onepager_v1 \
  --moat-weekly-summary "$OUT_DIR/weekly.json" \
  --moat-weekly-summary-history "$OUT_DIR/history.json" \
  --moat-weekly-summary-history-trend "$OUT_DIR/trend.json" \
  --moat-repro-runbook-summary "$OUT_DIR/runbook.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_evidence_onepager_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
metrics = summary.get("public_metrics") if isinstance(summary.get("public_metrics"), dict) else {}
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "headline_present": "PASS" if isinstance(summary.get("headline"), str) and summary.get("headline") else "FAIL",
    "metrics_present": "PASS" if isinstance(metrics.get("real_model_count"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "onepager_status": summary.get("status"),
    "week_tag": summary.get("week_tag"),
    "headline": summary.get("headline"),
    "real_model_count": metrics.get("real_model_count"),
    "reproducible_mutation_count": metrics.get("reproducible_mutation_count"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "onepager_status": payload["onepager_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
