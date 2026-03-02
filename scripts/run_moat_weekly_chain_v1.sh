#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_moat_weekly_chain_v1"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_moat_scorecard_baseline_v1.sh >/dev/null
bash scripts/demo_dataset_model_asset_inventory_report_v1.sh >/dev/null
bash scripts/demo_dataset_failure_distribution_baseline_freeze_v1.sh >/dev/null
bash scripts/demo_dataset_moat_repro_runbook_v1.sh >/dev/null
bash scripts/demo_dataset_moat_weekly_summary_v1.sh >/dev/null
bash scripts/demo_dataset_moat_weekly_summary_history_v1.sh >/dev/null
bash scripts/demo_dataset_moat_weekly_summary_history_trend_v1.sh >/dev/null
bash scripts/demo_dataset_modelica_asset_uniqueness_index_v1.sh >/dev/null
bash scripts/demo_dataset_mutation_depth_pressure_history_v1.sh >/dev/null
bash scripts/demo_dataset_moat_defensibility_report_v1.sh >/dev/null
bash scripts/demo_dataset_moat_defensibility_history_v1.sh >/dev/null
bash scripts/demo_dataset_moat_defensibility_history_trend_v1.sh >/dev/null
bash scripts/demo_dataset_moat_external_claims_brief_v1.sh >/dev/null
bash scripts/demo_dataset_moat_execution_cadence_v1.sh >/dev/null
bash scripts/demo_dataset_moat_execution_cadence_history_v1.sh >/dev/null
bash scripts/demo_dataset_moat_execution_cadence_history_trend_v1.sh >/dev/null

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts")
out = root / "dataset_moat_weekly_chain_v1"

def _load(rel: str) -> dict:
    return json.loads((root / rel).read_text(encoding="utf-8"))

scorecard = _load("dataset_moat_scorecard_baseline_v1_demo/demo_summary.json")
inventory = _load("dataset_model_asset_inventory_report_v1_demo/demo_summary.json")
freeze = _load("dataset_failure_distribution_baseline_freeze_v1_demo/demo_summary.json")
runbook = _load("dataset_moat_repro_runbook_v1_demo/demo_summary.json")
weekly = _load("dataset_moat_weekly_summary_v1_demo/demo_summary.json")
history = _load("dataset_moat_weekly_summary_history_v1_demo/demo_summary.json")
trend = _load("dataset_moat_weekly_summary_history_trend_v1_demo/demo_summary.json")
uniqueness = _load("dataset_modelica_asset_uniqueness_index_v1_demo/demo_summary.json")
depth_history = _load("dataset_mutation_depth_pressure_history_v1_demo/demo_summary.json")
defensibility = _load("dataset_moat_defensibility_report_v1_demo/demo_summary.json")
defensibility_history = _load("dataset_moat_defensibility_history_v1_demo/demo_summary.json")
defensibility_trend = _load("dataset_moat_defensibility_history_trend_v1_demo/demo_summary.json")
claims = _load("dataset_moat_external_claims_brief_v1_demo/demo_summary.json")
cadence = _load("dataset_moat_execution_cadence_v1_demo/demo_summary.json")
cadence_history = _load("dataset_moat_execution_cadence_history_v1_demo/demo_summary.json")
cadence_trend = _load("dataset_moat_execution_cadence_history_trend_v1_demo/demo_summary.json")

flags = {
    "scorecard_pass": "PASS" if scorecard.get("bundle_status") == "PASS" else "FAIL",
    "inventory_pass": "PASS" if inventory.get("bundle_status") == "PASS" else "FAIL",
    "freeze_pass": "PASS" if freeze.get("bundle_status") == "PASS" else "FAIL",
    "runbook_pass": "PASS" if runbook.get("bundle_status") == "PASS" else "FAIL",
    "weekly_pass": "PASS" if weekly.get("bundle_status") == "PASS" else "FAIL",
    "history_pass": "PASS" if history.get("bundle_status") == "PASS" else "FAIL",
    "trend_pass": "PASS" if trend.get("bundle_status") == "PASS" else "FAIL",
    "uniqueness_pass": "PASS" if uniqueness.get("bundle_status") == "PASS" else "FAIL",
    "depth_history_pass": "PASS" if depth_history.get("bundle_status") == "PASS" else "FAIL",
    "defensibility_pass": "PASS" if defensibility.get("bundle_status") == "PASS" else "FAIL",
    "defensibility_history_pass": "PASS" if defensibility_history.get("bundle_status") == "PASS" else "FAIL",
    "defensibility_trend_pass": "PASS" if defensibility_trend.get("bundle_status") == "PASS" else "FAIL",
    "claims_pass": "PASS" if claims.get("bundle_status") == "PASS" else "FAIL",
    "cadence_pass": "PASS" if cadence.get("bundle_status") == "PASS" else "FAIL",
    "cadence_history_pass": "PASS" if cadence_history.get("bundle_status") == "PASS" else "FAIL",
    "cadence_trend_pass": "PASS" if cadence_trend.get("bundle_status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "bundle_status": bundle_status,
    "scorecard_status": scorecard.get("scorecard_status"),
    "inventory_status": inventory.get("inventory_status"),
    "freeze_status": freeze.get("freeze_status"),
    "runbook_status": runbook.get("runbook_status"),
    "weekly_status": weekly.get("weekly_status"),
    "history_status": history.get("history_status"),
    "trend_status": trend.get("trend_status"),
    "asset_uniqueness_status": uniqueness.get("asset_uniqueness_status"),
    "depth_history_status": depth_history.get("history_status"),
    "defensibility_status": defensibility.get("defensibility_status"),
    "defensibility_history_status": defensibility_history.get("history_status"),
    "defensibility_trend_status": defensibility_trend.get("trend_status"),
    "claims_status": claims.get("claims_status"),
    "cadence_status": cadence.get("cadence_status"),
    "cadence_history_status": cadence_history.get("history_status"),
    "cadence_trend_status": cadence_trend.get("trend_status"),
    "result_flags": flags,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# GateForge Moat Weekly Chain v1",
            "",
            f"- bundle_status: `{summary['bundle_status']}`",
            f"- scorecard_status: `{summary['scorecard_status']}`",
            f"- inventory_status: `{summary['inventory_status']}`",
            f"- freeze_status: `{summary['freeze_status']}`",
            f"- runbook_status: `{summary['runbook_status']}`",
            f"- weekly_status: `{summary['weekly_status']}`",
            f"- history_status: `{summary['history_status']}`",
            f"- trend_status: `{summary['trend_status']}`",
            f"- asset_uniqueness_status: `{summary['asset_uniqueness_status']}`",
            f"- depth_history_status: `{summary['depth_history_status']}`",
            f"- defensibility_status: `{summary['defensibility_status']}`",
            f"- defensibility_history_status: `{summary['defensibility_history_status']}`",
            f"- defensibility_trend_status: `{summary['defensibility_trend_status']}`",
            f"- claims_status: `{summary['claims_status']}`",
            f"- cadence_status: `{summary['cadence_status']}`",
            f"- cadence_history_status: `{summary['cadence_history_status']}`",
            f"- cadence_trend_status: `{summary['cadence_trend_status']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "weekly_status": summary["weekly_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
