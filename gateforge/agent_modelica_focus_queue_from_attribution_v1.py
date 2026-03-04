from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

GATE_WEIGHT = {
    "regression_fail": 4.0,
    "physics_contract_fail": 3.0,
    "simulate_fail": 2.0,
    "check_model_fail": 2.0,
    "unknown_fail": 1.0,
}


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
        "# GateForge Agent Modelica Focus Queue From Attribution v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- pair_count: `{payload.get('pair_count')}`",
        f"- queue_size: `{payload.get('queue_size')}`",
        "",
        "## Queue",
        "",
    ]
    queue = payload.get("queue") if isinstance(payload.get("queue"), list) else []
    if queue:
        for row in queue:
            lines.append(
                f"- `{row.get('rank')}` `{row.get('failure_type')}` + `{row.get('gate_break_reason')}` "
                f"count=`{row.get('count')}` priority=`{row.get('priority_score')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _read_history(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append_history(path: str, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _gate_family(reason: str) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return "unknown_fail"
    if text.startswith("runtime_regression:"):
        return "regression_fail"
    if text.startswith("physical_invariant_"):
        return "physics_contract_fail"
    if text.startswith("steady_state_regression"):
        return "regression_fail"
    if text in {"check_model_fail", "simulate_fail", "regression_fail", "physics_contract_fail"}:
        return text
    return text


def _objective(gate_reason: str) -> str:
    if gate_reason == "regression_fail":
        return "reduce_regression_fail"
    if gate_reason == "physics_contract_fail":
        return "reduce_physics_contract_fail"
    if gate_reason == "simulate_fail":
        return "reduce_simulate_fail"
    if gate_reason == "check_model_fail":
        return "reduce_check_model_fail"
    return "reduce_unknown_fail"


def _pair_streak(previous_entries: list[dict], pair: tuple[str, str]) -> int:
    streak = 0
    for row in reversed(previous_entries):
        queue = row.get("queue") if isinstance(row.get("queue"), list) else []
        queue_pairs = {
            (str(x.get("failure_type") or "unknown"), str(x.get("gate_break_reason") or "unknown_fail"))
            for x in queue
            if isinstance(x, dict)
        }
        if pair in queue_pairs:
            streak += 1
        else:
            break
    return streak


def _regression_fail_map(run_results_payload: dict) -> dict[str, bool]:
    records = run_results_payload.get("records") if isinstance(run_results_payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    out: dict[str, bool] = {}
    for rec in records:
        task_id = str(rec.get("task_id") or "")
        if not task_id:
            continue
        hard = rec.get("hard_checks") if isinstance(rec.get("hard_checks"), dict) else {}
        out[task_id] = not bool(hard.get("regression_pass", True))
    return out


def build_focus_queue(
    attribution_payload: dict,
    top_k: int = 2,
    run_results_payload: dict | None = None,
    previous_entries: list[dict] | None = None,
    persistence_weight: float = 3.0,
) -> dict:
    rows = attribution_payload.get("rows") if isinstance(attribution_payload.get("rows"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]
    regression_fail_by_task = _regression_fail_map(run_results_payload or {})
    pair_counts: dict[tuple[str, str], int] = {}
    for row in rows:
        task_id = str(row.get("task_id") or "")
        ftype = str(row.get("failure_type") or "unknown")
        if bool(regression_fail_by_task.get(task_id)):
            gate = "regression_fail"
        else:
            gate = _gate_family(str(row.get("gate_break_reason") or "unknown_fail"))
        key = (ftype, gate)
        pair_counts[key] = int(pair_counts.get(key, 0)) + 1

    ranked: list[dict] = []
    for (ftype, gate), count in pair_counts.items():
        streak = _pair_streak(previous_entries or [], (ftype, gate))
        persistence_bonus = round(float(streak) * float(persistence_weight), 4)
        priority = round((float(count) * 10.0) + float(GATE_WEIGHT.get(gate, 1.0)) + persistence_bonus, 4)
        ranked.append(
            {
                "failure_type": ftype,
                "gate_break_reason": gate,
                "count": count,
                "streak_count": streak,
                "persistence_bonus": persistence_bonus,
                "priority_score": priority,
                "objective": _objective(gate),
                "action_hint": f"focus_{ftype}_{gate}",
            }
        )
    ranked = sorted(ranked, key=lambda x: (-float(x.get("priority_score", 0.0)), str(x.get("failure_type")), str(x.get("gate_break_reason"))))
    queue = []
    for idx, row in enumerate(ranked[: max(1, int(top_k))], start=1):
        queue.append({"rank": idx, **row})
    return {
        "pair_count": len(pair_counts),
        "queue_size": len(queue),
        "queue": queue,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build top focus queue from failure attribution by gate+failure_type")
    parser.add_argument("--failure-attribution", required=True)
    parser.add_argument("--run-results", default=None)
    parser.add_argument("--history-jsonl", default=None)
    parser.add_argument("--persistence-weight", type=float, default=3.0)
    parser.add_argument("--append-history", action="store_true")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--out", default="artifacts/agent_modelica_focus_queue_from_attribution_v1/queue.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    attribution = _load_json(args.failure_attribution)
    run_results = _load_json(str(args.run_results)) if isinstance(args.run_results, str) and args.run_results.strip() else {}
    previous_entries = _read_history(str(args.history_jsonl)) if isinstance(args.history_jsonl, str) and args.history_jsonl.strip() else []
    payload = build_focus_queue(
        attribution_payload=attribution,
        top_k=max(1, int(args.top_k)),
        run_results_payload=run_results,
        previous_entries=previous_entries,
        persistence_weight=float(args.persistence_weight),
    )
    out = {
        "schema_version": "agent_modelica_focus_queue_from_attribution_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if int(payload.get("queue_size", 0)) > 0 else "NEEDS_REVIEW",
        **payload,
        "sources": {"failure_attribution": args.failure_attribution},
    }
    if isinstance(args.run_results, str) and args.run_results.strip():
        out["sources"]["run_results"] = args.run_results
    if isinstance(args.history_jsonl, str) and args.history_jsonl.strip():
        out["sources"]["history_jsonl"] = args.history_jsonl
    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    if args.append_history and isinstance(args.history_jsonl, str) and args.history_jsonl.strip():
        _append_history(
            str(args.history_jsonl),
            {
                "generated_at_utc": out.get("generated_at_utc"),
                "queue": out.get("queue", []),
                "queue_size": out.get("queue_size"),
                "pair_count": out.get("pair_count"),
                "source_failure_attribution": args.failure_attribution,
            },
        )
    print(json.dumps({"status": out.get("status"), "queue_size": out.get("queue_size")}))


if __name__ == "__main__":
    main()
