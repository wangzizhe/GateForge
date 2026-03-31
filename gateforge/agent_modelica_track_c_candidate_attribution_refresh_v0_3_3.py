from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_c_candidate_attribution_refresh_v0_3_3"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_candidate_attribution_refresh_v0_3_3"


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


def _task_rows(payload: dict) -> list[dict]:
    for key in ("tasks", "cases"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _result_rows(payload: dict) -> list[dict]:
    for key in ("results", "records"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def refresh_candidate_attribution(
    *,
    candidate_taskset_path: str,
    results_paths: list[str],
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    taskset = _load_json(candidate_taskset_path)
    tasks = _task_rows(taskset)
    results_index: dict[str, dict] = {}
    for path in results_paths:
        payload = _load_json(path)
        for row in _result_rows(payload):
            item_id = _item_id(row)
            if item_id and item_id not in results_index:
                results_index[item_id] = row

    refreshed_rows: list[dict] = []
    matched = 0
    attributed = 0
    for row in tasks:
        item_id = _item_id(row)
        result = results_index.get(item_id, {})
        resolution_path = _norm(result.get("resolution_path"))
        planner_invoked = bool(result.get("planner_invoked"))
        planner_decisive = bool(result.get("planner_decisive"))
        rounds_used = int(result.get("rounds_used") or 0)
        llm_request_count = int(
            result.get("llm_request_count")
            or result.get("llm_request_count_delta")
            or 0
        )
        if result:
            matched += 1
        if resolution_path or planner_invoked or rounds_used or llm_request_count:
            attributed += 1
        refreshed_rows.append(
            {
                **row,
                "resolution_path": resolution_path,
                "planner_invoked": planner_invoked,
                "planner_decisive": planner_decisive,
                "rounds_used": rounds_used,
                "llm_request_count": llm_request_count,
                "attribution_status": (
                    "attributed"
                    if resolution_path or planner_invoked or rounds_used or llm_request_count
                    else "matched_without_attribution" if result
                    else "missing_result"
                ),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "results_paths": [str(Path(path).resolve()) if Path(path).exists() else str(path) for path in results_paths],
        "metrics": {
            "candidate_count": len(tasks),
            "matched_result_count": matched,
            "attributed_count": attributed,
        },
        "tasks": refreshed_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "taskset_candidates_refreshed.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Track C harvested candidates with attribution-bearing results.")
    parser.add_argument("--candidate-taskset", required=True)
    parser.add_argument("--results", action="append", default=[])
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = refresh_candidate_attribution(
        candidate_taskset_path=str(args.candidate_taskset),
        results_paths=[str(x) for x in (args.results or []) if str(x).strip()],
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "attributed_count": payload.get("metrics", {}).get("attributed_count")}))


if __name__ == "__main__":
    main()
