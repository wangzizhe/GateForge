#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_snapshot_orchestrate_demo

bash scripts/demo_review_kpis.sh
bash scripts/demo_repair_orchestrate_compare.sh
bash scripts/demo_ci_matrix.sh --none --checker-demo

python3 -m gateforge.governance_report \
  --repair-batch-summary artifacts/repair_orchestrate_compare_demo/summary.json \
  --review-ledger-summary artifacts/review_kpi_demo/kpi_summary.json \
  --ci-matrix-summary artifacts/ci_matrix_summary.json \
  --out artifacts/governance_snapshot_orchestrate_demo/summary.json \
  --report artifacts/governance_snapshot_orchestrate_demo/summary.md

cat artifacts/governance_snapshot_orchestrate_demo/summary.json
cat artifacts/governance_snapshot_orchestrate_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_snapshot_orchestrate_demo/summary.json").read_text(encoding="utf-8"))
flags = {
    "expect_status_known": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "expect_kpi_relation_present": "PASS"
    if "strategy_compare_relation" in (payload.get("kpis", {}) or {})
    else "FAIL",
    "expect_risks_list": "PASS" if isinstance(payload.get("risks", []), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "status": payload.get("status"),
    "strategy_compare_relation": payload.get("kpis", {}).get("strategy_compare_relation"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/governance_snapshot_orchestrate_demo/demo_summary.json").write_text(
    json.dumps(demo, indent=2), encoding="utf-8"
)
Path("artifacts/governance_snapshot_orchestrate_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Governance Snapshot From Orchestrate Compare Demo",
            "",
            f"- status: `{demo['status']}`",
            f"- strategy_compare_relation: `{demo['strategy_compare_relation']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- expect_status_known: `{flags['expect_status_known']}`",
            f"- expect_kpi_relation_present: `{flags['expect_kpi_relation_present']}`",
            f"- expect_risks_list: `{flags['expect_risks_list']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/governance_snapshot_orchestrate_demo/demo_summary.json
cat artifacts/governance_snapshot_orchestrate_demo/demo_summary.md
