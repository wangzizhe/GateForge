from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Failure Attribution v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- failed_count: `{payload.get('failed_count')}`",
        "",
        "## Top Rows",
        "",
    ]
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    if rows:
        for row in rows[:10]:
            lines.append(
                f"- `{row.get('task_id')}` `{row.get('failure_type')}` reason=`{row.get('gate_break_reason')}` strategy=`{row.get('used_strategy')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _gate_break_reason(rec: dict) -> str:
    hard = rec.get("hard_checks") if isinstance(rec.get("hard_checks"), dict) else {}
    if not bool(hard.get("check_model_pass", True)):
        return "check_model_fail"
    if not bool(hard.get("simulate_pass", True)):
        return "simulate_fail"
    if not bool(hard.get("physics_contract_pass", True)):
        reasons = rec.get("physics_contract_reasons") if isinstance(rec.get("physics_contract_reasons"), list) else []
        if reasons:
            return str(reasons[0])
        return "physics_contract_fail"
    if not bool(hard.get("regression_pass", True)):
        reasons = rec.get("regression_reasons") if isinstance(rec.get("regression_reasons"), list) else []
        if reasons:
            return str(reasons[0])
        return "regression_fail"
    return "unknown_fail"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract minimal failure attribution rows from run results")
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_failure_attribution_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    payload = _load_json(args.run_results)
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    failed = [x for x in records if not bool(x.get("passed", False))]

    rows: list[dict] = []
    for rec in failed:
        repair = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
        rows.append(
            {
                "task_id": str(rec.get("task_id") or ""),
                "scale": str(rec.get("scale") or "unknown"),
                "failure_type": str(rec.get("failure_type") or "unknown"),
                "gate_break_reason": _gate_break_reason(rec),
                "used_strategy": str(repair.get("strategy_id") or (rec.get("repair_strategy") or {}).get("strategy_id") or ""),
                "action_trace": [str(x) for x in (repair.get("actions_planned") or []) if isinstance(x, str)],
            }
        )

    out = {
        "schema_version": "agent_modelica_failure_attribution_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "failed_count": len(rows),
        "rows": rows,
        "sources": {"run_results": args.run_results},
    }
    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": out.get("status"), "failed_count": out.get("failed_count")}))


if __name__ == "__main__":
    main()
