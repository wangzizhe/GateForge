from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PUBLIC_HARDPACK_PATH = "benchmarks/agent_modelica_hardpack_v1.json"
DEFAULT_PRIVATE_HARDPACK_PATH = "benchmarks/private/agent_modelica_hardpack_v1.json"


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
        "# GateForge Agent Modelica Landscape Snapshot v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- weekly_decision: `{payload.get('weekly_decision')}`",
        f"- two_week_decision: `{payload.get('two_week_decision')}`",
        f"- hardpack_status: `{payload.get('hardpack_status')}`",
        "",
        "## Next Landscape",
        "",
    ]
    nxt = payload.get("next_landscape") if isinstance(payload.get("next_landscape"), list) else []
    if nxt:
        lines.extend([f"- {x}" for x in nxt])
    else:
        lines.append("- none")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")

def _default_hardpack_path() -> str:
    return DEFAULT_PRIVATE_HARDPACK_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize current modelica agent landscape and next actions")
    parser.add_argument("--weekly-summary", required=True)
    parser.add_argument("--weekly-decision", required=True)
    parser.add_argument("--two-week-summary", default="")
    parser.add_argument("--hardpack", default=_default_hardpack_path())
    parser.add_argument("--out", default="artifacts/agent_modelica_landscape_snapshot_v1/snapshot.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    weekly = _load_json(args.weekly_summary)
    weekly_decision_payload = _load_json(args.weekly_decision)
    two_week = _load_json(args.two_week_summary) if str(args.two_week_summary).strip() else {}
    hardpack = _load_json(args.hardpack)

    weekly_decision = str(weekly_decision_payload.get("decision") or "UNKNOWN")
    two_week_decision = str(two_week.get("decision") or "UNKNOWN")
    hardpack_status = str(hardpack.get("status") or ("PASS" if hardpack else "MISSING"))
    next_landscape: list[str] = []

    if weekly_decision == "ROLLBACK" or two_week_decision == "ROLLBACK":
        next_landscape.append("freeze promotion and restore previous stable promoted_playbook")
        next_landscape.append("prioritize top failure attribution reasons and rerun hardpack weekly chain")
    elif weekly_decision == "HOLD" and two_week_decision in {"HOLD", "UNKNOWN"}:
        next_landscape.append("keep top-k constrained promotion and collect one more hardpack week")
        next_landscape.append("focus on reducing median_time_to_pass or median_repair_rounds on top2 failure types")
    else:
        next_landscape.append("promote current strategy window and monitor safety deltas next week")
        next_landscape.append("expand hardpack stress cases for weak failure types if available")

    payload = {
        "schema_version": "agent_modelica_landscape_snapshot_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "weekly_status": weekly.get("status"),
        "weekly_decision": weekly_decision,
        "two_week_decision": two_week_decision,
        "hardpack_status": hardpack_status,
        "signals": {
            "weekly_success_at_k_pct": weekly.get("success_at_k_pct"),
            "weekly_median_time_to_pass_sec": weekly.get("median_time_to_pass_sec"),
            "weekly_median_repair_rounds": weekly.get("median_repair_rounds"),
            "weekly_regression_count": weekly.get("regression_count"),
            "weekly_physics_fail_count": weekly.get("physics_fail_count"),
        },
        "next_landscape": next_landscape,
        "sources": {
            "weekly_summary": args.weekly_summary,
            "weekly_decision": args.weekly_decision,
            "two_week_summary": args.two_week_summary if str(args.two_week_summary).strip() else None,
            "hardpack": args.hardpack,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "weekly_decision": payload.get("weekly_decision")}))


if __name__ == "__main__":
    main()
