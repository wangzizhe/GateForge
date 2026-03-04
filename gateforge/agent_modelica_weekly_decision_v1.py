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


def _load_jsonl(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


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
        "# GateForge Agent Modelica Weekly Decision v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- week_tag: `{payload.get('week_tag')}`",
        f"- previous_week_tag: `{payload.get('previous_week_tag')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        lines.extend([f"- `{x}`" for x in reasons])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _f(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _pick_previous_from_ledger(ledger_rows: list[dict], current_week_tag: str) -> dict:
    for row in reversed(ledger_rows):
        if str(row.get("week_tag") or "") != current_week_tag:
            return row
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Make weekly promote/hold/rollback decision from weekly metrics")
    parser.add_argument("--current-page", required=True)
    parser.add_argument("--previous-page", default="")
    parser.add_argument("--ledger", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_weekly_decision_v1/decision.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current_page)
    week_tag = str(current.get("week_tag") or "unknown_week")
    previous = _load_json(args.previous_page) if str(args.previous_page).strip() else {}
    if not previous and str(args.ledger).strip():
        previous = _pick_previous_from_ledger(_load_jsonl(args.ledger), current_week_tag=week_tag)
    prev_tag = str(previous.get("week_tag") or "")

    reasons: list[str] = []
    status = "PASS"
    baseline_status = str(current.get("baseline_status") or current.get("status") or "FAIL")
    if baseline_status == "FAIL":
        reasons.append("baseline_fail")

    regression_count = _f(current.get("regression_count"))
    physics_fail_count = _f(current.get("physics_fail_count"))
    if regression_count > 0:
        reasons.append("regression_count_positive")
    if physics_fail_count > 0:
        reasons.append("physics_fail_count_positive")

    d = current.get("delta_vs_previous") if isinstance(current.get("delta_vs_previous"), dict) else {}
    success_delta = _f(d.get("success_at_k_pct"))
    time_delta = _f(d.get("median_time_to_pass_sec"))
    rounds_delta = _f(d.get("median_repair_rounds"))
    core_improved = success_delta > 0 or time_delta < 0 or rounds_delta < 0
    core_regressed = success_delta < 0 or time_delta > 0 or rounds_delta > 0
    if core_improved:
        reasons.append("core_metric_improved")
    elif core_regressed:
        reasons.append("core_metric_regressed")
    else:
        reasons.append("core_metric_tied")

    if baseline_status == "FAIL" or regression_count > 0 or physics_fail_count > 0:
        decision = "ROLLBACK"
    elif core_improved:
        decision = "PROMOTE"
    else:
        decision = "HOLD"

    payload = {
        "schema_version": "agent_modelica_weekly_decision_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": decision,
        "week_tag": week_tag,
        "previous_week_tag": prev_tag or None,
        "reasons": reasons,
        "signals": {
            "success_delta": round(success_delta, 2),
            "time_delta": round(time_delta, 2),
            "rounds_delta": round(rounds_delta, 2),
            "core_improved": core_improved,
            "core_regressed": core_regressed,
            "regression_count": regression_count,
            "physics_fail_count": physics_fail_count,
        },
        "sources": {
            "current_page": args.current_page,
            "previous_page": args.previous_page if str(args.previous_page).strip() else None,
            "ledger": args.ledger if str(args.ledger).strip() else None,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
