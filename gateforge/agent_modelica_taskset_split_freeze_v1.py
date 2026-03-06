from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
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
        "# GateForge Agent Modelica Taskset Split Freeze v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- train_count: `{payload.get('train_count')}`",
        f"- holdout_count: `{payload.get('holdout_count')}`",
        f"- assigned_count: `{payload.get('assigned_count')}`",
        f"- preexisting_split_count: `{payload.get('preexisting_split_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _task_key(task: dict, seed: str) -> str:
    parts = [
        seed,
        _norm(task.get("task_id")).lower(),
        _norm(task.get("failure_type")).lower(),
        _norm(task.get("scale")).lower(),
        _norm(task.get("mutated_model_path")).lower(),
    ]
    return "|".join(parts)


def _assign_split(task: dict, holdout_ratio: float, seed: str) -> str:
    key = _task_key(task, seed=seed)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10000
    threshold = int(max(0.0, min(1.0, float(holdout_ratio))) * 10000)
    return "holdout" if bucket < threshold else "train"


def _split_counts(tasks: list[dict]) -> tuple[int, int]:
    train_count = 0
    holdout_count = 0
    for task in tasks:
        split = _norm(task.get("split")).lower()
        if split == "holdout":
            holdout_count += 1
        else:
            train_count += 1
    return train_count, holdout_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze deterministic train/holdout split on taskset before large-scale runs")
    parser.add_argument("--taskset-in", required=True)
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_split_v1")
    parser.add_argument("--force", action="store_true", help="reassign split even if split already exists")
    parser.add_argument("--out-taskset", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_taskset_split_freeze_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    payload = _load_json(args.taskset_in)
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]

    assigned_count = 0
    preexisting_split_count = 0
    for task in tasks:
        existing = _norm(task.get("split")).lower()
        if existing in {"train", "holdout"} and not bool(args.force):
            preexisting_split_count += 1
            continue
        task["split"] = _assign_split(task=task, holdout_ratio=float(args.holdout_ratio), seed=str(args.seed))
        assigned_count += 1

    # Ensure non-empty holdout for non-empty taskset.
    if tasks:
        train_count, holdout_count = _split_counts(tasks)
        if holdout_count <= 0:
            # deterministically move lexicographically smallest task_id (fallback to first)
            first = sorted(tasks, key=lambda x: (_norm(x.get("task_id")), _norm(x.get("mutated_model_path"))))[0]
            first["split"] = "holdout"
            assigned_count += 1
            train_count, holdout_count = _split_counts(tasks)
    else:
        train_count, holdout_count = 0, 0

    out_payload = dict(payload)
    out_payload["tasks"] = tasks
    out_payload["split_freeze"] = {
        "schema_version": "agent_modelica_taskset_split_freeze_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": str(args.seed),
        "holdout_ratio": float(args.holdout_ratio),
    }
    _write_json(args.out_taskset, out_payload)

    summary = {
        "schema_version": "agent_modelica_taskset_split_freeze_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if tasks else "FAIL",
        "total_tasks": len(tasks),
        "train_count": train_count,
        "holdout_count": holdout_count,
        "assigned_count": assigned_count,
        "preexisting_split_count": preexisting_split_count,
        "seed": str(args.seed),
        "holdout_ratio": float(args.holdout_ratio),
        "out_taskset": args.out_taskset,
        "sources": {"taskset_in": args.taskset_in},
        "reasons": [] if tasks else ["taskset_empty"],
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "holdout_count": holdout_count, "total_tasks": len(tasks)}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
