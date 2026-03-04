from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MEMORY_PATH = "data/private_failure_corpus/agent_modelica_repair_memory_v1.json"
PRIVATE_RELATIVE_PREFIXES = (
    "assets_private/",
    "examples_private/",
    "data/private_",
)


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


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
        "# GateForge Agent Modelica Repair Memory Store v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{payload.get('total_rows')}`",
        f"- added_rows: `{payload.get('added_rows')}`",
        f"- updated_rows: `{payload.get('updated_rows')}`",
        f"- skipped_rows: `{payload.get('skipped_rows')}`",
        f"- success_rows_seen: `{payload.get('success_rows_seen')}`",
        f"- memory_path: `{payload.get('memory_path')}`",
        "",
    ]
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    lines.append("## Reasons")
    lines.append("")
    if reasons:
        lines.extend([f"- `{str(x)}`" for x in reasons])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _is_private_memory_path(path: str) -> bool:
    raw = _norm(path).replace("\\", "/")
    if not raw:
        return False
    if raw.startswith("/"):
        return any(
            segment in raw
            for segment in (
                "/assets_private/",
                "/examples_private/",
                "/data/private_",
            )
        )
    return any(raw.startswith(prefix) for prefix in PRIVATE_RELATIVE_PREFIXES)


def _task_lookup(taskset_payload: dict) -> dict[str, dict]:
    tasks = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    out: dict[str, dict] = {}
    for task in tasks:
        task_id = _norm(task.get("task_id"))
        if task_id:
            out[task_id] = task
    return out


def _fingerprint(row: dict) -> str:
    basis = {
        "failure_type": _norm(row.get("failure_type")).lower(),
        "scale": _norm(row.get("scale")).lower(),
        "model_hint": _norm(row.get("source_model_path") or row.get("mutated_model_path") or row.get("model_id")).lower(),
        "strategy_id": _norm(row.get("used_strategy")).lower(),
        "actions": [str(x).strip().lower() for x in (row.get("action_trace") or []) if isinstance(x, str)],
        "pass": bool(row.get("success", False)),
    }
    raw = json.dumps(basis, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_repair_memory_update(
    run_results_payload: dict,
    taskset_payload: dict,
    existing_memory_payload: dict,
    *,
    include_failed: bool = False,
    max_rows: int = 5000,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    records = run_results_payload.get("records") if isinstance(run_results_payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    task_by_id = _task_lookup(taskset_payload)

    existing_rows = existing_memory_payload.get("rows") if isinstance(existing_memory_payload.get("rows"), list) else []
    existing_rows = [x for x in existing_rows if isinstance(x, dict)]
    by_fp: dict[str, dict] = {}
    for row in existing_rows:
        fp = _norm(row.get("fingerprint"))
        if not fp:
            row.setdefault("action_trace", [str(x) for x in (row.get("action_trace") or []) if isinstance(x, str)])
            row.setdefault("used_strategy", _norm(row.get("used_strategy")))
            row.setdefault("success", bool(row.get("success")))
            fp = _fingerprint(row)
            row["fingerprint"] = fp
        if fp:
            by_fp[fp] = row

    added = 0
    updated = 0
    skipped = 0
    success_rows_seen = 0
    failed_rows_seen = 0

    for rec in records:
        passed = bool(rec.get("passed"))
        if passed:
            success_rows_seen += 1
        else:
            failed_rows_seen += 1
        if not include_failed and not passed:
            skipped += 1
            continue

        task_id = _norm(rec.get("task_id"))
        task = task_by_id.get(task_id, {})
        strategy = rec.get("repair_strategy") if isinstance(rec.get("repair_strategy"), dict) else {}
        actions = strategy.get("actions") if isinstance(strategy.get("actions"), list) else []
        actions = [str(x) for x in actions if isinstance(x, str)]
        failure_type = _norm(rec.get("failure_type") or task.get("failure_type") or "unknown").lower()
        scale = _norm(rec.get("scale") or task.get("scale") or "unknown").lower()
        source_model_path = _norm(task.get("source_model_path"))
        mutated_model_path = _norm(task.get("mutated_model_path"))
        model_hint = source_model_path or mutated_model_path or task_id

        row = {
            "fingerprint": "",
            "recorded_at_utc": now,
            "last_seen_at_utc": now,
            "task_id": task_id,
            "failure_type": failure_type,
            "scale": scale,
            "source_model_path": source_model_path,
            "mutated_model_path": mutated_model_path,
            "model_id": Path(model_hint).stem if model_hint else "",
            "used_strategy": _norm(strategy.get("strategy_id")),
            "action_trace": actions,
            "success": passed,
            "status": "PASS" if passed else "FAIL",
            "hard_checks": rec.get("hard_checks") if isinstance(rec.get("hard_checks"), dict) else {},
            "source_run_results": _norm(run_results_payload.get("source_run_results") or ""),
        }
        fp = _fingerprint(row)
        row["fingerprint"] = fp
        if fp in by_fp:
            current = by_fp[fp]
            current["last_seen_at_utc"] = now
            current["seen_count"] = int(current.get("seen_count", 1) or 1) + 1
            updated += 1
        else:
            row["seen_count"] = 1
            by_fp[fp] = row
            added += 1

    rows = list(by_fp.values())
    rows = sorted(
        rows,
        key=lambda x: (
            str(x.get("last_seen_at_utc") or ""),
            str(x.get("fingerprint") or ""),
        ),
        reverse=True,
    )
    rows = rows[: max(1, int(max_rows))]

    return {
        "schema_version": "agent_modelica_repair_memory_v1",
        "generated_at_utc": now,
        "rows": rows,
        "stats": {
            "total_rows": len(rows),
            "added_rows": added,
            "updated_rows": updated,
            "skipped_rows": skipped,
            "success_rows_seen": success_rows_seen,
            "failed_rows_seen": failed_rows_seen,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist successful modelica repair traces to private memory")
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--taskset", default="")
    parser.add_argument("--memory", default=DEFAULT_MEMORY_PATH)
    parser.add_argument("--allow-non-private", action="store_true")
    parser.add_argument("--include-failed", action="store_true")
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_memory_store_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    reasons: list[str] = []
    status = "PASS"
    memory_path = _norm(args.memory) or DEFAULT_MEMORY_PATH
    if not args.allow_non_private and not _is_private_memory_path(memory_path):
        reasons.append("non_private_memory_path_blocked")
        status = "FAIL"

    run_results = _load_json(args.run_results)
    run_results["source_run_results"] = args.run_results
    taskset = _load_json(args.taskset) if _norm(args.taskset) else {}
    existing_memory = _load_json(memory_path)

    payload = build_repair_memory_update(
        run_results_payload=run_results,
        taskset_payload=taskset,
        existing_memory_payload=existing_memory,
        include_failed=bool(args.include_failed),
        max_rows=max(1, int(args.max_rows)),
    )
    memory_rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}

    if status == "PASS":
        _write_json(memory_path, payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "memory_path": memory_path,
        "run_results_path": args.run_results,
        "taskset_path": args.taskset if _norm(args.taskset) else None,
        "total_rows": len(memory_rows),
        "added_rows": int(stats.get("added_rows", 0) or 0),
        "updated_rows": int(stats.get("updated_rows", 0) or 0),
        "skipped_rows": int(stats.get("skipped_rows", 0) or 0),
        "success_rows_seen": int(stats.get("success_rows_seen", 0) or 0),
        "failed_rows_seen": int(stats.get("failed_rows_seen", 0) or 0),
        "include_failed": bool(args.include_failed),
        "allow_non_private": bool(args.allow_non_private),
        "reasons": reasons,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "total_rows": summary.get("total_rows")}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
