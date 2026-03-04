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
                f"- `{row.get('rank')}` `{row.get('failure_type')}` priority=`{row.get('priority_score')}` count=`{row.get('count')}` delta_pass=`{row.get('delta_pass_rate_pct')}` signal_delta=`{row.get('strategy_signal_delta_score')}`"
            )
    else:
        lines.extend(["## Queue", "", "- `none`"])
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _priority_score(
    row: dict,
    *,
    outcome_weight: float,
    strategy_weight: float,
    strategy_target_score: float,
) -> float:
    delta_pass = float(row.get("delta_pass_rate_pct", 0.0) or 0.0)
    delta_time = float(row.get("delta_avg_elapsed_sec", 0.0) or 0.0)
    count = int(row.get("count", 0) or 0)
    treatment_signal = float(row.get("strategy_signal_treatment_score", 0.0) or 0.0)
    delta_signal = float(row.get("strategy_signal_delta_score", 0.0) or 0.0)

    # Outcome weakness: treatment pass-rate drop, slower runtime, and high frequency.
    outcome_weakness = (max(0.0, -delta_pass) * 1.0) + (max(0.0, delta_time) * 2.0) + (float(count) * 0.05)
    # Strategy weakness: low treatment quality score and non-improving signal trend.
    strategy_weakness = max(0.0, strategy_target_score - treatment_signal) + max(0.0, -delta_signal)
    score = (outcome_weight * outcome_weakness) + (strategy_weight * strategy_weakness)
    return round(score, 4)


def _priority_key(row: dict) -> tuple[float, int, str]:
    # Descending by priority_score, then descending count, then lexical by failure type.
    return (-float(row.get("priority_score", 0.0) or 0.0), -int(row.get("count", 0) or 0), str(row.get("failure_type") or ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build top failure queue from strategy A/B summary")
    parser.add_argument("--ab-summary", required=True)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--outcome-weight", type=float, default=0.7)
    parser.add_argument("--strategy-weight", type=float, default=0.3)
    parser.add_argument("--strategy-target-score", type=float, default=0.8)
    parser.add_argument("--out", default="artifacts/agent_modelica_top_failure_queue_v1/queue.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    ab = _load_json(args.ab_summary)
    per_failure = ab.get("per_failure_type") if isinstance(ab.get("per_failure_type"), dict) else {}
    sig_payload = (
        ab.get("strategy_signal_by_failure_type")
        if isinstance(ab.get("strategy_signal_by_failure_type"), dict)
        else {}
    )
    sig_treatment = sig_payload.get("treatment") if isinstance(sig_payload.get("treatment"), dict) else {}
    sig_delta = sig_payload.get("delta_score") if isinstance(sig_payload.get("delta_score"), dict) else {}

    candidates: list[dict] = []
    for ftype, row in per_failure.items():
        if not isinstance(row, dict):
            continue
        treatment_score = float((sig_treatment.get(ftype) or {}).get("score", 0.0) or 0.0)
        delta_score = float(sig_delta.get(ftype, 0.0) or 0.0)
        candidate = {
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
            "strategy_signal_treatment_score": treatment_score,
            "strategy_signal_delta_score": delta_score,
        }
        candidate["priority_score"] = _priority_score(
            candidate,
            outcome_weight=float(args.outcome_weight),
            strategy_weight=float(args.strategy_weight),
            strategy_target_score=float(args.strategy_target_score),
        )
        candidates.append(
            candidate
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
