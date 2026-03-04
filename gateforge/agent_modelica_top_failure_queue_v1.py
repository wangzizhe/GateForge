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
        "# GateForge Agent Modelica Top Failure Queue v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- queue_size: `{payload.get('queue_size')}`",
        "",
    ]
    queue = payload.get("queue", [])
    if isinstance(queue, list) and queue:
        lines.extend(["## Queue", ""])
        for row in queue:
            lines.append(
                f"- `{row.get('rank')}` `{row.get('failure_type')}` count=`{row.get('count')}` delta_pass=`{row.get('delta_pass_rate_pct')}`"
            )
    else:
        lines.extend(["## Queue", "", "- `none`"])
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _priority_key(row: dict) -> tuple[float, int, str]:
    # Prefer failures that are frequent and not improving.
    delta_pass = float(row.get("delta_pass_rate_pct", 0.0) or 0.0)
    count = int(row.get("count", 0) or 0)
    ftype = str(row.get("failure_type") or "")
    penalty = 0.0 if delta_pass <= 0 else delta_pass
    return (penalty, -count, ftype)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build top failure queue from strategy A/B summary")
    parser.add_argument("--ab-summary", required=True)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--out", default="artifacts/agent_modelica_top_failure_queue_v1/queue.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    ab = _load_json(args.ab_summary)
    per_failure = ab.get("per_failure_type") if isinstance(ab.get("per_failure_type"), dict) else {}

    candidates: list[dict] = []
    for ftype, row in per_failure.items():
        if not isinstance(row, dict):
            continue
        candidates.append(
            {
                "failure_type": str(ftype),
                "count": int(row.get("count", 0) or 0),
                "delta_pass_rate_pct": float(row.get("delta_pass_rate_pct", 0.0) or 0.0),
                "delta_avg_elapsed_sec": (
                    float(row.get("delta_avg_elapsed_sec"))
                    if isinstance(row.get("delta_avg_elapsed_sec"), (int, float))
                    else None
                ),
                "control_pass_rate_pct": float(row.get("control_pass_rate_pct", 0.0) or 0.0),
                "treatment_pass_rate_pct": float(row.get("treatment_pass_rate_pct", 0.0) or 0.0),
            }
        )

    ranked = sorted(candidates, key=_priority_key)
    top_k = max(1, int(args.top_k))
    queue = []
    for idx, row in enumerate(ranked[:top_k], start=1):
        objective = "raise_treatment_pass_rate" if row["delta_pass_rate_pct"] < 0 else "reduce_elapsed_time"
        queue.append(
            {
                "rank": idx,
                **row,
                "objective": objective,
                "action_hint": f"focus_{row['failure_type']}",
            }
        )

    payload = {
        "schema_version": "agent_modelica_top_failure_queue_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "queue_size": len(queue),
        "queue": queue,
        "sources": {
            "ab_summary": args.ab_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "queue_size": payload.get("queue_size")}))


if __name__ == "__main__":
    main()
