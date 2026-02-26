#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_portfolio_balance_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "mutations": [
    {"mutation_id":"m1","target_scale":"large","expected_failure_type":"simulate_error"},
    {"mutation_id":"m2","target_scale":"medium","expected_failure_type":"model_check_error"},
    {"mutation_id":"m3","target_scale":"small","expected_failure_type":"semantic_regression"},
    {"mutation_id":"m4","target_scale":"large","expected_failure_type":"numerical_instability"}
  ]
}
JSON

cat > "$OUT_DIR/failure_corpus_saturation_summary.json" <<'JSON'
{
  "target_failure_types": ["simulate_error","model_check_error","semantic_regression","numerical_instability","constraint_violation"],
  "total_gap_actions": 1
}
JSON

cat > "$OUT_DIR/evidence_chain_summary.json" <<'JSON'
{"chain_health_score": 80.0}
JSON

python3 -m gateforge.dataset_mutation_portfolio_balance_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --failure-corpus-saturation-summary "$OUT_DIR/failure_corpus_saturation_summary.json" \
  --evidence-chain-summary "$OUT_DIR/evidence_chain_summary.json" \
  --min-large-mutation-ratio-pct 20 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_portfolio_balance_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if summary.get("portfolio_balance_score") is not None else "FAIL",
    "scale_counts_present": "PASS" if isinstance(summary.get("scale_counts"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "portfolio_status": summary.get("status"),
    "portfolio_balance_score": summary.get("portfolio_balance_score"),
    "large_mutation_ratio_pct": summary.get("large_mutation_ratio_pct"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "portfolio_status": payload["portfolio_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
