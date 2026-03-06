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
        "# GateForge Agent Modelica First Failure Attribution v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- task_count: `{payload.get('task_count')}`",
        "",
        "## Top Rows",
        "",
    ]
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    if rows:
        for row in rows[:10]:
            lines.append(
                f"- `{row.get('task_id')}` first_observed=`{row.get('first_observed_failure_type')}` "
                f"gate=`{row.get('first_gate_break_reason')}` pre_repair=`{row.get('first_pre_repair_applied')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _first_gate_break_reason(first_attempt: dict) -> str:
    if not bool(first_attempt.get("check_model_pass", True)):
        return "check_model_fail"
    if not bool(first_attempt.get("simulate_pass", True)):
        return "simulate_fail"
    if not bool(first_attempt.get("physics_contract_pass", True)):
        reasons = first_attempt.get("physics_contract_reasons") if isinstance(first_attempt.get("physics_contract_reasons"), list) else []
        if reasons:
            return str(reasons[0])
        return "physics_contract_fail"
    if not bool(first_attempt.get("regression_pass", True)):
        reasons = first_attempt.get("regression_reasons") if isinstance(first_attempt.get("regression_reasons"), list) else []
        if reasons:
            return str(reasons[0])
        return "regression_fail"
    return "none"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract first-attempt failure attribution rows from run results")
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_first_failure_attribution_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    payload = _load_json(args.run_results)
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]

    rows: list[dict] = []
    for rec in records:
        attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        first_attempt = attempts[0] if attempts and isinstance(attempts[0], dict) else {}
        pre_repair = first_attempt.get("pre_repair") if isinstance(first_attempt.get("pre_repair"), dict) else {}
        repair = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
        first_observed = str(first_attempt.get("observed_failure_type") or "none")
        rows.append(
            {
                "task_id": str(rec.get("task_id") or ""),
                "scale": str(rec.get("scale") or "unknown"),
                "failure_type": str(rec.get("failure_type") or "unknown"),
                "first_observed_failure_type": first_observed if first_observed else "none",
                "first_gate_break_reason": _first_gate_break_reason(first_attempt),
                "first_reason": str(first_attempt.get("reason") or ""),
                "first_pre_repair_applied": bool(pre_repair.get("applied")),
                "first_pre_repair_reason": str(pre_repair.get("reason") or ""),
                "used_strategy": str(repair.get("strategy_id") or (rec.get("repair_strategy") or {}).get("strategy_id") or ""),
                "action_trace": [str(x) for x in (repair.get("actions_planned") or []) if isinstance(x, str)],
            }
        )

    observed_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("first_observed_failure_type") or "none")
        observed_counts[key] = int(observed_counts.get(key, 0)) + 1

    out = {
        "schema_version": "agent_modelica_first_failure_attribution_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if rows else "NEEDS_REVIEW",
        "task_count": len(rows),
        "first_observed_failure_type_counts": observed_counts,
        "rows": rows,
        "sources": {"run_results": args.run_results},
    }
    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": out.get("status"), "task_count": out.get("task_count")}))


if __name__ == "__main__":
    main()
