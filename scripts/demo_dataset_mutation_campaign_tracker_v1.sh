#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_campaign_tracker_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "mutations": [
    {"mutation_id":"m1"},{"mutation_id":"m2"},{"mutation_id":"m3"},{"mutation_id":"m4"},
    {"mutation_id":"m5"},{"mutation_id":"m6"},{"mutation_id":"m7"},{"mutation_id":"m8"}
  ]
}
JSON

cat > "$OUT_DIR/mutation_portfolio_balance_summary.json" <<'JSON'
{"status":"PASS","portfolio_balance_score":80.0,"rebalance_actions":[]}
JSON

cat > "$OUT_DIR/modelica_library_expansion_plan_summary.json" <<'JSON'
{"weekly_new_models_target":3}
JSON

cat > "$OUT_DIR/evidence_chain_summary.json" <<'JSON'
{"status":"PASS","chain_health_score":82.0}
JSON

cat > "$OUT_DIR/replay_observation_store_summary.json" <<'JSON'
{"ingested_records":7}
JSON

python3 -m gateforge.dataset_mutation_campaign_tracker_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-portfolio-balance-summary "$OUT_DIR/mutation_portfolio_balance_summary.json" \
  --modelica-library-expansion-plan-summary "$OUT_DIR/modelica_library_expansion_plan_summary.json" \
  --evidence-chain-summary "$OUT_DIR/evidence_chain_summary.json" \
  --replay-observation-store-summary "$OUT_DIR/replay_observation_store_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_campaign_tracker_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "completion_present": "PASS" if summary.get("completion_ratio_pct") is not None else "FAIL",
    "phase_present": "PASS" if summary.get("campaign_phase") in {"stabilize", "scale_out", "accelerate"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "tracker_status": summary.get("status"),
    "campaign_phase": summary.get("campaign_phase"),
    "completion_ratio_pct": summary.get("completion_ratio_pct"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "tracker_status": payload["tracker_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
