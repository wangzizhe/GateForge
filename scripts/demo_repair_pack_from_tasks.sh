#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/repair_pack_demo

bash scripts/demo_repair_tasks.sh

python3 -m gateforge.repair_pack \
  --tasks-summary artifacts/repair_tasks_demo/summary.json \
  --pack-id repair_pack_demo_v0 \
  --planner-backend rule \
  --strategy-profile industrial_strict \
  --out artifacts/repair_pack_demo/pack.json

python3 -m gateforge.repair_batch \
  --pack artifacts/repair_pack_demo/pack.json \
  --continue-on-fail \
  --summary-out artifacts/repair_pack_demo/summary.json \
  --report-out artifacts/repair_pack_demo/summary.md

cat artifacts/repair_pack_demo/pack.json
cat artifacts/repair_pack_demo/summary.json
cat artifacts/repair_pack_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

pack = json.loads(Path("artifacts/repair_pack_demo/pack.json").read_text(encoding="utf-8"))
summary = json.loads(Path("artifacts/repair_pack_demo/summary.json").read_text(encoding="utf-8"))
flags = {
    "expect_pack_cases_positive": "PASS" if len(pack.get("cases", [])) > 0 else "FAIL",
    "expect_pack_source_linked": "PASS" if isinstance(pack.get("generated_from"), str) else "FAIL",
    "expect_strategy_profile_set": "PASS" if pack.get("strategy_profile") == "industrial_strict" else "FAIL",
    "expect_summary_has_effectiveness_counts": "PASS"
    if all(k in summary for k in ("improved_count", "worse_count", "unchanged_count", "safety_block_count"))
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo_summary = {
    "pack_id": pack.get("pack_id"),
    "case_count": len(pack.get("cases", [])),
    "summary_total_cases": summary.get("total_cases"),
    "improved_count": summary.get("improved_count"),
    "worse_count": summary.get("worse_count"),
    "safety_block_count": summary.get("safety_block_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/repair_pack_demo/demo_summary.json").write_text(
    json.dumps(demo_summary, indent=2), encoding="utf-8"
)
Path("artifacts/repair_pack_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Repair Pack From Tasks Demo",
            "",
            f"- pack_id: `{demo_summary['pack_id']}`",
            f"- case_count: `{demo_summary['case_count']}`",
            f"- summary_total_cases: `{demo_summary['summary_total_cases']}`",
            f"- improved_count: `{demo_summary['improved_count']}`",
            f"- worse_count: `{demo_summary['worse_count']}`",
            f"- safety_block_count: `{demo_summary['safety_block_count']}`",
            f"- bundle_status: `{demo_summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- expect_pack_cases_positive: `{flags['expect_pack_cases_positive']}`",
            f"- expect_pack_source_linked: `{flags['expect_pack_source_linked']}`",
            f"- expect_strategy_profile_set: `{flags['expect_strategy_profile_set']}`",
            f"- expect_summary_has_effectiveness_counts: `{flags['expect_summary_has_effectiveness_counts']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/repair_pack_demo/demo_summary.json
cat artifacts/repair_pack_demo/demo_summary.md
