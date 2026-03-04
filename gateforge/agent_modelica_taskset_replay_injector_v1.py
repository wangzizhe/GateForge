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
        "# GateForge Agent Modelica Taskset Replay Injector v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- current_task_count: `{payload.get('current_task_count')}`",
        f"- replay_candidate_count: `{payload.get('replay_candidate_count')}`",
        f"- injected_replay_count: `{payload.get('injected_replay_count')}`",
        "",
        "## Injected Mix",
        "",
    ]
    mix = payload.get("injected_mix", {})
    if isinstance(mix, dict) and mix:
        for key in sorted(mix.keys()):
            lines.append(f"- {key}: `{mix[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _is_hard_fail(rec: dict) -> bool:
    if not isinstance(rec, dict):
        return False
    if not bool(rec.get("passed", False)):
        return True
    hard = rec.get("hard_checks") if isinstance(rec.get("hard_checks"), dict) else {}
    if hard and any(not bool(hard.get(key)) for key in ("check_model_pass", "simulate_pass", "physics_contract_pass", "regression_pass")):
        return True
    if isinstance(rec.get("physics_contract_reasons"), list) and rec.get("physics_contract_reasons"):
        return True
    if isinstance(rec.get("regression_reasons"), list) and rec.get("regression_reasons"):
        return True
    return False


def _elapsed(rec: dict) -> float:
    try:
        return float(rec.get("elapsed_sec", rec.get("time_to_pass_sec", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _rank_replay_tasks(prev_taskset: dict, prev_run_results: dict) -> list[dict]:
    tasks = prev_taskset.get("tasks") if isinstance(prev_taskset.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    task_by_id = {str(t.get("task_id") or ""): t for t in tasks if str(t.get("task_id") or "")}

    records = prev_run_results.get("records") if isinstance(prev_run_results.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]

    hard: list[tuple[float, str]] = []
    slow: list[tuple[float, str]] = []
    for rec in records:
        task_id = str(rec.get("task_id") or "")
        if task_id not in task_by_id:
            continue
        elapsed = _elapsed(rec)
        if _is_hard_fail(rec):
            hard.append((elapsed, task_id))
        else:
            slow.append((elapsed, task_id))

    hard.sort(key=lambda x: (-x[0], x[1]))
    slow.sort(key=lambda x: (-x[0], x[1]))
    order = [task_id for _, task_id in [*hard, *slow]]

    ranked: list[dict] = []
    seen: set[str] = set()
    for rank, task_id in enumerate(order, start=1):
        if task_id in seen:
            continue
        seen.add(task_id)
        task = dict(task_by_id[task_id])
        task["_replay_rank"] = rank
        task["_replay_class"] = "hard_fail" if any(task_id == t for _, t in hard) else "slow_pass"
        ranked.append(task)
    return ranked


def _round_robin_pick(candidates: list[dict], limit: int) -> list[dict]:
    if limit <= 0:
        return []
    by_failure: dict[str, list[dict]] = {}
    for row in candidates:
        ftype = str(row.get("failure_type") or "unknown")
        by_failure.setdefault(ftype, []).append(row)

    ordered_failures = sorted(by_failure.keys())
    picked: list[dict] = []
    while len(picked) < limit and ordered_failures:
        progress = False
        for ftype in ordered_failures:
            bucket = by_failure.get(ftype) or []
            if not bucket:
                continue
            picked.append(bucket.pop(0))
            progress = True
            if len(picked) >= limit:
                break
        if not progress:
            break
    return picked


def _select_replay_tasks(ranked: list[dict], max_replay: int) -> list[dict]:
    if max_replay <= 0:
        return []
    hard = [x for x in ranked if str(x.get("_replay_class") or "") == "hard_fail"]
    slow = [x for x in ranked if str(x.get("_replay_class") or "") == "slow_pass"]

    selected = _round_robin_pick(candidates=hard, limit=max_replay)
    if len(selected) < max_replay:
        selected_ids = {str(x.get("task_id") or "") for x in selected}
        remaining_slow = [x for x in slow if str(x.get("task_id") or "") not in selected_ids]
        selected.extend(_round_robin_pick(candidates=remaining_slow, limit=max_replay - len(selected)))
    return selected[:max_replay]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject previous hard cases into current weekly taskset")
    parser.add_argument("--current-taskset", required=True)
    parser.add_argument("--prev-taskset", required=True)
    parser.add_argument("--prev-run-results", required=True)
    parser.add_argument("--max-replay", type=int, default=6)
    parser.add_argument("--out-taskset", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_taskset_replay_injector_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current_taskset)
    prev_taskset = _load_json(args.prev_taskset)
    prev_results = _load_json(args.prev_run_results)

    current_tasks = current.get("tasks") if isinstance(current.get("tasks"), list) else []
    current_tasks = [x for x in current_tasks if isinstance(x, dict)]
    current_size = len(current_tasks)

    ranked = _rank_replay_tasks(prev_taskset=prev_taskset, prev_run_results=prev_results)
    max_replay = max(0, int(args.max_replay))
    selected = _select_replay_tasks(ranked=ranked, max_replay=max_replay)
    selected_ids = {str(x.get("task_id") or "") for x in selected}

    merged: list[dict] = [dict(x) for x in selected]
    for task in current_tasks:
        task_id = str(task.get("task_id") or "")
        if task_id and task_id in selected_ids:
            continue
        merged.append(dict(task))
        if len(merged) >= current_size:
            break
    merged = merged[:current_size]

    out_taskset = {
        "schema_version": str(current.get("schema_version") or "agent_modelica_taskset_v1"),
        "snapshot_version": str(current.get("snapshot_version") or "unknown"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": merged,
        "sources": {
            "current_taskset": args.current_taskset,
            "prev_taskset": args.prev_taskset,
            "prev_run_results": args.prev_run_results,
        },
    }
    _write_json(args.out_taskset, out_taskset)

    injected = [x for x in merged if str(x.get("_replay_class") or "")]
    injected_mix = {"hard_fail": 0, "slow_pass": 0}
    for row in injected:
        replay_class = str(row.get("_replay_class") or "")
        if replay_class in injected_mix:
            injected_mix[replay_class] = int(injected_mix[replay_class]) + 1

    payload = {
        "schema_version": "agent_modelica_taskset_replay_injector_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "current_task_count": current_size,
        "replay_candidate_count": len(ranked),
        "injected_replay_count": len(injected),
        "injected_mix": injected_mix,
        "max_replay": max_replay,
        "out_taskset": args.out_taskset,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "injected_replay_count": payload.get("injected_replay_count"),
            }
        )
    )


if __name__ == "__main__":
    main()
