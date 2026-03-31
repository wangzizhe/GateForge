from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_track_c_primary_slice_v0_3_3 import DEFAULT_FROZEN_REFERENCES


SCHEMA_VERSION = "agent_modelica_track_c_candidate_harvest_v0_3_3"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_candidate_harvest_v0_3_3"


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
    for key in ("tasks", "cases"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _frozen_case_ids(path: str | Path) -> set[str]:
    payload = _load_json(path)
    ids: set[str] = set()
    for row in _task_rows(payload):
        item_id = _item_id(row)
        if item_id:
            ids.add(item_id)
    return ids


def _infer_family_id(row: dict) -> str:
    family_id = _norm(row.get("v0_3_family_id"))
    if family_id:
        return family_id
    failure_type = _norm(row.get("failure_type") or row.get("expected_failure_type")).lower()
    if failure_type == "initialization_infeasible":
        return "initialization_singularity"
    if failure_type == "solver_sensitive_simulate_failure":
        return "runtime_numerical_instability"
    return "hard_multiround_simulate_failure"


def harvest_candidates(
    *,
    taskset_paths: list[str],
    out_dir: str = DEFAULT_OUT_DIR,
    frozen_references: list[dict] | None = None,
) -> dict:
    frozen_refs = [dict(row) for row in (frozen_references or list(DEFAULT_FROZEN_REFERENCES))]
    frozen_ids_by_ref = {
        _norm(row.get("ref_id")) or "unknown_ref": _frozen_case_ids(_norm(row.get("path")))
        for row in frozen_refs
    }
    harvested_rows: list[dict] = []
    for taskset_path in taskset_paths:
        payload = _load_json(taskset_path)
        for row in _task_rows(payload):
            item_id = _item_id(row)
            if not item_id:
                continue
            frozen_hits = sorted([ref_id for ref_id, ids in frozen_ids_by_ref.items() if item_id in ids])
            harvested_rows.append(
                {
                    **row,
                    "task_id": item_id,
                    "v0_3_family_id": _infer_family_id(row),
                    "source_taskset_path": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
                    "harvest_classification": "generated_candidate_holdout_clean" if not frozen_hits else "generated_candidate_excluded_frozen",
                    "holdout_clean": not frozen_hits,
                    "frozen_hits": frozen_hits,
                }
            )

    holdout_clean_rows = [row for row in harvested_rows if bool(row.get("holdout_clean"))]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if holdout_clean_rows else "NEEDS_MORE_GENERATION",
        "taskset_paths": [str(Path(path).resolve()) if Path(path).exists() else str(path) for path in taskset_paths],
        "metrics": {
            "harvested_count": len(harvested_rows),
            "holdout_clean_count": len(holdout_clean_rows),
            "frozen_overlap_count": len(harvested_rows) - len(holdout_clean_rows),
        },
        "tasks": harvested_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "taskset_candidates.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# Track C Candidate Harvest v0.3.3",
                "",
                f"- status: `{payload['status']}`",
                f"- harvested_count: `{payload['metrics']['harvested_count']}`",
                f"- holdout_clean_count: `{payload['metrics']['holdout_clean_count']}`",
                f"- frozen_overlap_count: `{payload['metrics']['frozen_overlap_count']}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest newly generated Track C candidates for v0.3.3.")
    parser.add_argument("--taskset", action="append", default=[])
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = harvest_candidates(
        taskset_paths=[str(x) for x in (args.taskset or []) if str(x).strip()],
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "holdout_clean_count": payload.get("metrics", {}).get("holdout_clean_count")}))


if __name__ == "__main__":
    main()
