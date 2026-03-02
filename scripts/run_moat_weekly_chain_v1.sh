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

flags = {
    "scorecard_pass": "PASS" if scorecard.get("bundle_status") == "PASS" else "FAIL",
    "inventory_pass": "PASS" if inventory.get("bundle_status") == "PASS" else "FAIL",
    "freeze_pass": "PASS" if freeze.get("bundle_status") == "PASS" else "FAIL",
    "runbook_pass": "PASS" if runbook.get("bundle_status") == "PASS" else "FAIL",
    "weekly_pass": "PASS" if weekly.get("bundle_status") == "PASS" else "FAIL",
    "history_pass": "PASS" if history.get("bundle_status") == "PASS" else "FAIL",
    "trend_pass": "PASS" if trend.get("bundle_status") == "PASS" else "FAIL",
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
