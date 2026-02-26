#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_anchor_public_release_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/anchor_release_bundle_v3_summary.json" <<'JSON'
{
  "release_score": 88.5,
  "release_bundle_id": "anchor_release_v3_20260226",
  "reproducible_playbook": [
    "bash scripts/demo_dataset_open_source_model_intake_v1.sh",
    "bash scripts/demo_dataset_mutation_factory_v1.sh",
    "bash scripts/demo_dataset_failure_distribution_benchmark_v2.sh"
  ]
}
JSON

cat > "$OUT_DIR/gateforge_vs_plain_ci_summary.json" <<'JSON'
{
  "verdict": "GATEFORGE_ADVANTAGE",
  "advantage_score": 7
}
JSON

cat > "$OUT_DIR/failure_distribution_benchmark_v2_summary.json" <<'JSON'
{
  "validated_match_ratio_pct": 89.0,
  "failure_type_drift": 0.14
}
JSON

cat > "$OUT_DIR/moat_trend_snapshot_summary.json" <<'JSON'
{
  "metrics": {
    "moat_score": 81.5
  }
}
JSON

cat > "$OUT_DIR/large_coverage_push_v1_summary.json" <<'JSON'
{
  "status": "PASS",
  "push_target_large_cases": 0
}
JSON

python3 -m gateforge.dataset_anchor_public_release_v1 \
  --anchor-release-bundle-v3-summary "$OUT_DIR/anchor_release_bundle_v3_summary.json" \
  --gateforge-vs-plain-ci-summary "$OUT_DIR/gateforge_vs_plain_ci_summary.json" \
  --failure-distribution-benchmark-v2-summary "$OUT_DIR/failure_distribution_benchmark_v2_summary.json" \
  --moat-trend-snapshot-summary "$OUT_DIR/moat_trend_snapshot_summary.json" \
  --large-coverage-push-v1-summary "$OUT_DIR/large_coverage_push_v1_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_anchor_public_release_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
claims = summary.get("headline_claims") if isinstance(summary.get("headline_claims"), list) else []
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if float(summary.get("public_release_score", 0.0) or 0.0) > 0 else "FAIL",
    "claims_present": "PASS" if len(claims) >= 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "public_release_status": summary.get("status"),
    "public_release_ready": summary.get("public_release_ready"),
    "public_release_score": summary.get("public_release_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "public_release_status": payload["public_release_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
