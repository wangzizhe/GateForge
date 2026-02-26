#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_evidence_chain_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/replay_store_summary.json" <<'JSON'
{"status":"PASS","ingested_records":3}
JSON

cat > "$OUT_DIR/failure_label_calibrator_summary.json" <<'JSON'
{"status":"PASS","expected_match_ratio_pct":91.0}
JSON

cat > "$OUT_DIR/mutation_validator_summary.json" <<'JSON'
{"status":"PASS","expected_match_ratio_pct":88.0}
JSON

cat > "$OUT_DIR/failure_distribution_benchmark_v2_summary.json" <<'JSON'
{"status":"PASS","failure_type_drift":0.16}
JSON

cat > "$OUT_DIR/large_coverage_push_v1_summary.json" <<'JSON'
{"status":"PASS","push_target_large_cases":0}
JSON

cat > "$OUT_DIR/anchor_public_release_v1_summary.json" <<'JSON'
{"status":"PASS","public_release_score":84.0}
JSON

python3 -m gateforge.dataset_evidence_chain_v1 \
  --replay-observation-store-summary "$OUT_DIR/replay_store_summary.json" \
  --failure-label-calibrator-summary "$OUT_DIR/failure_label_calibrator_summary.json" \
  --mutation-validator-summary "$OUT_DIR/mutation_validator_summary.json" \
  --failure-distribution-benchmark-v2-summary "$OUT_DIR/failure_distribution_benchmark_v2_summary.json" \
  --large-coverage-push-v1-summary "$OUT_DIR/large_coverage_push_v1_summary.json" \
  --anchor-public-release-v1-summary "$OUT_DIR/anchor_public_release_v1_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_evidence_chain_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if float(summary.get("chain_health_score", 0.0) or 0.0) > 0 else "FAIL",
    "steps_present": "PASS" if len(summary.get("steps", [])) >= 4 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "chain_status": summary.get("status"),
    "chain_health_score": summary.get("chain_health_score"),
    "chain_completeness_pct": summary.get("chain_completeness_pct"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "chain_status": payload["chain_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
