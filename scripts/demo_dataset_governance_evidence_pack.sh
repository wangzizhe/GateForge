#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_evidence_pack_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/snapshot_summary.json" <<'JSON'
{
  "status": "PASS",
  "risks": [],
  "kpis": {
    "dataset_failure_distribution_drift_score": 0.11,
    "dataset_model_scale_ladder_status": "PASS"
  }
}
JSON

cat > "$OUT_DIR/snapshot_trend.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "PASS->PASS",
    "new_risks": [],
    "severity_score": 0,
    "severity_level": "low"
  }
}
JSON

cat > "$OUT_DIR/failure_taxonomy_coverage_summary.json" <<'JSON'
{"status":"PASS","alerts":[]}
JSON

cat > "$OUT_DIR/failure_distribution_benchmark_summary.json" <<'JSON'
{"status":"PASS","alerts":[]}
JSON

cat > "$OUT_DIR/model_scale_ladder_summary.json" <<'JSON'
{"status":"PASS","alerts":[]}
JSON

cat > "$OUT_DIR/failure_policy_patch_advisor.json" <<'JSON'
{"status":"PASS","advice":{"suggested_action":"keep"}}
JSON
cat > "$OUT_DIR/blind_spot_backlog_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","total_open_tasks":3,"priority_counts":{"P0":1,"P1":1,"P2":1,"P3":0}}
JSON
cat > "$OUT_DIR/policy_patch_replay_evaluator_summary.json" <<'JSON'
{"status":"PASS","recommendation":"ADOPT_PATCH","evaluation_score":4,"delta":{"detection_rate":0.05,"false_positive_rate":-0.02,"regression_rate":-0.04}}
JSON

python3 -m gateforge.dataset_governance_evidence_pack \
  --snapshot-summary "$OUT_DIR/snapshot_summary.json" \
  --snapshot-trend "$OUT_DIR/snapshot_trend.json" \
  --failure-taxonomy-coverage "$OUT_DIR/failure_taxonomy_coverage_summary.json" \
  --failure-distribution-benchmark "$OUT_DIR/failure_distribution_benchmark_summary.json" \
  --model-scale-ladder "$OUT_DIR/model_scale_ladder_summary.json" \
  --failure-policy-patch-advisor "$OUT_DIR/failure_policy_patch_advisor.json" \
  --blind-spot-backlog "$OUT_DIR/blind_spot_backlog_summary.json" \
  --policy-patch-replay-evaluator "$OUT_DIR/policy_patch_replay_evaluator_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_evidence_pack_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "integrity_present": "PASS" if isinstance(payload.get("integrity"), dict) else "FAIL",
    "proof_points_present": "PASS" if isinstance(payload.get("proof_points"), list) else "FAIL",
    "score_present": "PASS" if isinstance(payload.get("evidence_strength_score"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "evidence_pack_status": payload.get("status"),
    "evidence_strength_score": payload.get("evidence_strength_score"),
    "residual_risk_count": payload.get("residual_risk_count"),
    "proof_point_count": len(payload.get("proof_points") or []),
    "backlog_open_tasks": (payload.get("action_outcome") or {}).get("backlog_open_tasks"),
    "policy_patch_roi_score": (payload.get("action_outcome") or {}).get("policy_patch_roi_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance Evidence Pack Demo",
            "",
            f"- evidence_pack_status: `{summary['evidence_pack_status']}`",
            f"- evidence_strength_score: `{summary['evidence_strength_score']}`",
            f"- residual_risk_count: `{summary['residual_risk_count']}`",
            f"- proof_point_count: `{summary['proof_point_count']}`",
            f"- backlog_open_tasks: `{summary['backlog_open_tasks']}`",
            f"- policy_patch_roi_score: `{summary['policy_patch_roi_score']}`",
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
print(json.dumps({"bundle_status": bundle_status, "evidence_pack_status": summary["evidence_pack_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
