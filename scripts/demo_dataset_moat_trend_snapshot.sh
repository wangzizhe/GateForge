#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_trend_snapshot_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/evidence_pack.json" <<'JSON'
{"status":"PASS","evidence_strength_score":78,"evidence_sections_present":8}
JSON

cat > "$OUT_DIR/registry_summary.json" <<'JSON'
{"total_records":22,"missing_model_scales":[]}
JSON

cat > "$OUT_DIR/backlog_summary.json" <<'JSON'
{"total_open_tasks":4,"priority_counts":{"P0":1,"P1":2,"P2":1,"P3":0}}
JSON

cat > "$OUT_DIR/replay_eval_summary.json" <<'JSON'
{"status":"PASS","recommendation":"ADOPT_PATCH","evaluation_score":4}
JSON

cat > "$OUT_DIR/milestone_checkpoint_summary.json" <<'JSON'
{"status":"PASS","checkpoint_score":84.0,"milestone_decision":"GO"}
JSON

cat > "$OUT_DIR/milestone_checkpoint_trend_summary.json" <<'JSON'
{"status":"PASS","trend":{"status_transition":"PASS->PASS"}}
JSON

cat > "$OUT_DIR/milestone_public_brief_summary.json" <<'JSON'
{"milestone_status":"PASS","milestone_decision":"GO"}
JSON

cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{
  "status":"PASS",
  "accepted_count":4,
  "accepted_large_count":1,
  "accepted_scale_counts":{"small":1,"medium":2,"large":1},
  "reject_rate_pct":22.5,
  "weekly_target_status":"PASS"
}
JSON

cat > "$OUT_DIR/previous_intake_summary.json" <<'JSON'
{
  "status":"PASS",
  "accepted_count":3,
  "accepted_large_count":0,
  "accepted_scale_counts":{"small":1,"medium":2,"large":0},
  "reject_rate_pct":30.0,
  "weekly_target_status":"NEEDS_REVIEW"
}
JSON

cat > "$OUT_DIR/intake_growth_execution_board_summary.json" <<'JSON'
{"status":"PASS","execution_score":84.0,"critical_open_tasks":0,"projected_weeks_to_target":0}
JSON

cat > "$OUT_DIR/intake_growth_execution_board_history_summary.json" <<'JSON'
{"status":"PASS","avg_execution_score":82.0,"critical_open_tasks_rate":0.0}
JSON

cat > "$OUT_DIR/intake_growth_execution_board_history_trend_summary.json" <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON

cat > "$OUT_DIR/previous_summary.json" <<'JSON'
{
  "status": "NEEDS_REVIEW",
  "metrics": {
    "coverage_depth_index": 55,
    "governance_effectiveness_index": 60,
    "policy_learning_velocity": 52,
    "milestone_readiness_index": 70,
    "moat_score": 56
  }
}
JSON

python3 -m gateforge.dataset_moat_trend_snapshot \
  --evidence-pack "$OUT_DIR/evidence_pack.json" \
  --failure-corpus-registry-summary "$OUT_DIR/registry_summary.json" \
  --blind-spot-backlog "$OUT_DIR/backlog_summary.json" \
  --policy-patch-replay-evaluator "$OUT_DIR/replay_eval_summary.json" \
  --milestone-checkpoint-summary "$OUT_DIR/milestone_checkpoint_summary.json" \
  --milestone-checkpoint-trend-summary "$OUT_DIR/milestone_checkpoint_trend_summary.json" \
  --milestone-public-brief-summary "$OUT_DIR/milestone_public_brief_summary.json" \
  --real-model-intake-summary "$OUT_DIR/intake_summary.json" \
  --previous-real-model-intake-summary "$OUT_DIR/previous_intake_summary.json" \
  --intake-growth-execution-board-summary "$OUT_DIR/intake_growth_execution_board_summary.json" \
  --intake-growth-execution-board-history-summary "$OUT_DIR/intake_growth_execution_board_history_summary.json" \
  --intake-growth-execution-board-history-trend-summary "$OUT_DIR/intake_growth_execution_board_history_trend_summary.json" \
  --previous-snapshot "$OUT_DIR/previous_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_moat_trend_snapshot_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
metrics = payload.get("metrics") or {}
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "metrics_present": "PASS" if isinstance(metrics, dict) else "FAIL",
    "moat_score_present": "PASS" if isinstance(metrics.get("moat_score"), (int, float)) else "FAIL",
    "milestone_readiness_present": "PASS" if isinstance(metrics.get("milestone_readiness_index"), (int, float)) else "FAIL",
    "intake_growth_present": "PASS" if isinstance(metrics.get("intake_growth_score"), (int, float)) else "FAIL",
    "execution_readiness_present": "PASS" if isinstance(metrics.get("execution_readiness_index"), (int, float)) else "FAIL",
    "trend_present": "PASS" if isinstance(payload.get("trend"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "moat_status": payload.get("status"),
    "moat_score": metrics.get("moat_score"),
    "milestone_readiness_index": metrics.get("milestone_readiness_index"),
    "intake_growth_score": metrics.get("intake_growth_score"),
    "execution_readiness_index": metrics.get("execution_readiness_index"),
    "accepted_count_delta": ((payload.get("intake_growth") or {}).get("accepted_count_delta")),
    "accepted_large_delta": ((payload.get("intake_growth") or {}).get("accepted_large_delta")),
    "reject_rate_pct": ((payload.get("intake_growth") or {}).get("reject_rate_pct")),
    "moat_score_delta": ((payload.get("trend") or {}).get("delta") or {}).get("moat_score"),
    "status_transition": (payload.get("trend") or {}).get("status_transition"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Moat Trend Snapshot Demo",
            "",
            f"- moat_status: `{summary['moat_status']}`",
            f"- moat_score: `{summary['moat_score']}`",
            f"- milestone_readiness_index: `{summary['milestone_readiness_index']}`",
            f"- intake_growth_score: `{summary['intake_growth_score']}`",
            f"- execution_readiness_index: `{summary['execution_readiness_index']}`",
            f"- accepted_count_delta: `{summary['accepted_count_delta']}`",
            f"- accepted_large_delta: `{summary['accepted_large_delta']}`",
            f"- reject_rate_pct: `{summary['reject_rate_pct']}`",
            f"- moat_score_delta: `{summary['moat_score_delta']}`",
            f"- status_transition: `{summary['status_transition']}`",
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
print(json.dumps({"bundle_status": bundle_status, "moat_status": summary["moat_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
