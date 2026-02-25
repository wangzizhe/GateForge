#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_snapshot_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_pipeline.sh >/dev/null
bash scripts/demo_dataset_history.sh >/dev/null
if [ ! -f artifacts/dataset_history_demo/history_summary.json ]; then
  bash scripts/demo_dataset_history.sh >/dev/null
fi
if [ ! -f artifacts/dataset_history_demo/history_summary.json ]; then
  echo "missing artifacts/dataset_history_demo/history_summary.json" >&2
  exit 1
fi
bash scripts/demo_dataset_policy_lifecycle.sh >/dev/null
bash scripts/demo_dataset_governance_history.sh >/dev/null
bash scripts/demo_dataset_strategy_autotune.sh >/dev/null
bash scripts/demo_dataset_strategy_autotune_apply_history.sh >/dev/null
bash scripts/demo_dataset_promotion_candidate_history.sh >/dev/null
bash scripts/demo_dataset_promotion_candidate_apply_history.sh >/dev/null
bash scripts/demo_dataset_promotion_effectiveness.sh >/dev/null
bash scripts/demo_dataset_promotion_effectiveness_history.sh >/dev/null

ARGS=(
  --dataset-pipeline-summary artifacts/dataset_pipeline_demo/summary.json
  --dataset-history-summary artifacts/dataset_history_demo/history_summary.json
  --dataset-history-trend artifacts/dataset_history_demo/history_trend.json
  --dataset-governance-summary artifacts/dataset_policy_lifecycle_demo/ledger_summary.json
  --dataset-governance-trend artifacts/dataset_governance_history_demo/trend.json
  --dataset-policy-effectiveness artifacts/dataset_policy_lifecycle_demo/effectiveness.json
  --dataset-strategy-advisor artifacts/dataset_strategy_autotune_demo/advisor.json
  --dataset-strategy-apply-history artifacts/dataset_strategy_autotune_apply_history_demo/history_summary.json
  --dataset-strategy-apply-history-trend artifacts/dataset_strategy_autotune_apply_history_demo/history_trend.json
)

if [ -f artifacts/dataset_promotion_candidate_history_demo/history_summary.json ] && [ -f artifacts/dataset_promotion_candidate_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-history artifacts/dataset_promotion_candidate_history_demo/history_summary.json)
  ARGS+=(--dataset-promotion-history-trend artifacts/dataset_promotion_candidate_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json ] && [ -f artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-apply-history artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json)
  ARGS+=(--dataset-promotion-apply-history-trend artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_demo/effectiveness.json ]; then
  ARGS+=(--dataset-promotion-effectiveness artifacts/dataset_promotion_effectiveness_demo/effectiveness.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json ]; then
  ARGS+=(--dataset-promotion-effectiveness-history artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-effectiveness-history-trend artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json)
fi

python3 -m gateforge.dataset_governance_snapshot \
  "${ARGS[@]}" \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_snapshot_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "kpis_present": "PASS" if isinstance(payload.get("kpis"), dict) else "FAIL",
    "risks_present": "PASS" if isinstance(payload.get("risks"), list) else "FAIL",
    "promotion_effectiveness_history_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_promotion_effectiveness_history_trend_status"), (str, type(None)))
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "status": payload.get("status"),
    "risks_count": len(payload.get("risks") or []),
    "promotion_effectiveness_history_trend_status": (payload.get("kpis") or {}).get(
        "dataset_promotion_effectiveness_history_trend_status"
    ),
    "promotion_effectiveness_history_latest_decision": (payload.get("kpis") or {}).get(
        "dataset_promotion_effectiveness_history_latest_decision"
    ),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance Snapshot Demo",
            "",
            f"- status: `{summary['status']}`",
            f"- risks_count: `{summary['risks_count']}`",
            f"- promotion_effectiveness_history_trend_status: `{summary['promotion_effectiveness_history_trend_status']}`",
            f"- promotion_effectiveness_history_latest_decision: `{summary['promotion_effectiveness_history_latest_decision']}`",
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
print(json.dumps({"bundle_status": bundle_status, "status": summary["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
