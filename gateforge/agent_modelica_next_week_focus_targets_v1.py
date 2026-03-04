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
        "# GateForge Agent Modelica Next Week Focus Targets v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- week_tag: `{payload.get('week_tag')}`",
        f"- target_count: `{payload.get('target_count')}`",
        "",
    ]
    targets = payload.get("targets")
    if isinstance(targets, list) and targets:
        lines.extend(["## Targets", ""])
        for row in targets:
            lines.append(
                f"- `{row.get('rank')}` `{row.get('failure_type')}` objective=`{row.get('objective')}` action=`{row.get('action_hint')}`"
            )
    else:
        lines.extend(["## Targets", "", "- `none`"])
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract next-week focus targets from top2 focus loop summary")
    parser.add_argument("--focus-summary", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_next_week_focus_targets_v1/targets.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    summary = _load_json(args.focus_summary)
    queue = summary.get("queue") if isinstance(summary.get("queue"), list) else []
    queue = [x for x in queue if isinstance(x, dict)]

    week_tag = str(summary.get("week_tag") or "unknown_week")
    targets = [
        {
            "rank": int(x.get("rank", i + 1) or (i + 1)),
            "failure_type": str(x.get("failure_type") or "unknown"),
            "objective": str(x.get("objective") or "reduce_elapsed_time"),
            "action_hint": str(x.get("action_hint") or "focus_unknown"),
            "delta_pass_rate_pct": float(x.get("delta_pass_rate_pct", 0.0) or 0.0),
            "delta_avg_elapsed_sec": float(x.get("delta_avg_elapsed_sec", 0.0) or 0.0),
            "count": int(x.get("count", 0) or 0),
        }
        for i, x in enumerate(queue)
    ]

    payload = {
        "schema_version": "agent_modelica_next_week_focus_targets_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if targets else "NEEDS_REVIEW",
        "week_tag": week_tag,
        "target_count": len(targets),
        "targets": targets,
        "sources": {
            "focus_summary": args.focus_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "target_count": payload.get("target_count")}))


if __name__ == "__main__":
    main()
