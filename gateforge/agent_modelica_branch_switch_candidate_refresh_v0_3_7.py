from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_branch_switch_candidate_refresh_v0_3_7"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_candidate_refresh_v0_3_7"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _result_rows(payload: dict) -> list[dict]:
    rows = payload.get("results")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def refresh_branch_switch_candidates(
    *,
    candidate_taskset_path: str,
    results_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    taskset = _load_json(candidate_taskset_path)
    results_payload = _load_json(results_path)
    tasks = _task_rows(taskset)
    results_index = {_item_id(row): row for row in _result_rows(results_payload) if _item_id(row)}
    top_protocol = (
        results_payload.get("baseline_measurement_protocol")
        if isinstance(results_payload.get("baseline_measurement_protocol"), dict)
        else {}
    )

    refreshed_rows = []
    matched_result_count = 0
    planner_invoked_count = 0
    deterministic_only_count = 0
    wrong_branch_count = 0
    correct_branch_count = 0

    for task in tasks:
        item_id = _item_id(task)
        result = dict(results_index.get(item_id, {}) or {})
        if result:
            matched_result_count += 1
        protocol = (
            result.get("baseline_measurement_protocol")
            if isinstance(result.get("baseline_measurement_protocol"), dict)
            else task.get("baseline_measurement_protocol")
        ) or top_protocol
        merged = {
            **task,
            "verdict": _norm(result.get("verdict") or task.get("verdict")),
            "executor_status": _norm(result.get("executor_status") or task.get("executor_status")),
            "resolution_path": _norm(result.get("resolution_path") or task.get("resolution_path")),
            "planner_invoked": result.get("planner_invoked") if "planner_invoked" in result else task.get("planner_invoked"),
            "rounds_used": int(result.get("rounds_used") or task.get("rounds_used") or 0),
            "llm_request_count": int(result.get("llm_request_count") or task.get("llm_request_count") or 0),
            "check_model_pass": result.get("check_model_pass") if "check_model_pass" in result else task.get("check_model_pass"),
            "simulate_pass": result.get("simulate_pass") if "simulate_pass" in result else task.get("simulate_pass"),
            "wrong_branch_entered": result.get("wrong_branch_entered") if "wrong_branch_entered" in result else task.get("wrong_branch_entered"),
            "correct_branch_selected": result.get("correct_branch_selected") if "correct_branch_selected" in result else task.get("correct_branch_selected"),
            "error_message": _norm(result.get("error_message") or task.get("error_message")),
            "baseline_measurement_protocol": protocol,
        }
        if merged.get("planner_invoked") is True:
            planner_invoked_count += 1
        if _norm(merged.get("resolution_path")) == "deterministic_rule_only":
            deterministic_only_count += 1
        if bool(merged.get("wrong_branch_entered")):
            wrong_branch_count += 1
        if bool(merged.get("correct_branch_selected")):
            correct_branch_count += 1
        refreshed_rows.append(merged)

    total = len(refreshed_rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total > 0 else "EMPTY",
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "results_path": str(Path(results_path).resolve()) if Path(results_path).exists() else str(results_path),
        "metrics": {
            "total_rows": total,
            "matched_result_count": matched_result_count,
            "planner_invoked_count": planner_invoked_count,
            "planner_invoked_pct": round(100.0 * planner_invoked_count / total, 1) if total else 0.0,
            "deterministic_only_count": deterministic_only_count,
            "deterministic_only_pct": round(100.0 * deterministic_only_count / total, 1) if total else 0.0,
            "wrong_branch_count": wrong_branch_count,
            "correct_branch_count": correct_branch_count,
        },
        "tasks": refreshed_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "taskset_candidates_refreshed.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lines = [
        "# v0.3.7 Branch-Switch Candidate Refresh",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{metrics.get('total_rows')}`",
        f"- planner_invoked_pct: `{metrics.get('planner_invoked_pct')}`",
        f"- deterministic_only_pct: `{metrics.get('deterministic_only_pct')}`",
        f"- wrong_branch_count: `{metrics.get('wrong_branch_count')}`",
        f"- correct_branch_count: `{metrics.get('correct_branch_count')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh v0.3.7 branch-switch candidates with live run results.")
    parser.add_argument("--candidate-taskset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = refresh_branch_switch_candidates(
        candidate_taskset_path=str(args.candidate_taskset),
        results_path=str(args.results),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
