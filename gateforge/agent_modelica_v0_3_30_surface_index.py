from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_30_common import (
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_V0329_ENTRY_TASKSET_PATH,
    SCHEMA_PREFIX,
    SURFACE_INDEX_FIXTURE,
    build_medium_candidate_rhs_symbols,
    extract_component_name_from_step,
    load_json,
    now_utc,
    norm,
    parse_canonical_rhs_from_repair_step,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_surface_index"


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _fixture_rows(tasks: list[dict]) -> list[dict]:
    fixture = (SURFACE_INDEX_FIXTURE.get("task_rows") or [{}])[0]
    rows: list[dict] = []
    for task in tasks:
        step = ((task.get("repair_steps") or [{}])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        rows.append(
            {
                "task_id": norm(task.get("task_id")),
                "source_id": norm(task.get("source_id")),
                "component_name": extract_component_name_from_step(step),
                "canonical_rhs_symbol": norm(fixture.get("canonical_rhs_symbol")),
                "canonical_package_path": norm(fixture.get("canonical_package_path")),
                "candidate_rhs_symbols": list(fixture.get("candidate_rhs_symbols") or []),
                "local_cluster_rhs_values": [norm(fixture.get("canonical_rhs_symbol"))],
                "adjacent_component_package_paths": [norm(fixture.get("canonical_package_path"))],
                "source_export_ok": True,
            }
        )
    return rows


def build_v0330_surface_index(
    *,
    entry_taskset_path: str = str(DEFAULT_V0329_ENTRY_TASKSET_PATH),
    out_dir: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    taskset = load_json(entry_taskset_path)
    tasks = _single_rows(taskset)
    rows: list[dict] = []
    if use_fixture_only:
        rows = _fixture_rows(tasks)
    else:
        for task in tasks:
            step = ((task.get("repair_steps") or [{}])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
            candidate_info = build_medium_candidate_rhs_symbols(
                source_model_text=norm(task.get("source_model_text")),
                canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(step),
                use_fixture_only=False,
            )
            rows.append(
                {
                    "task_id": norm(task.get("task_id")),
                    "source_id": norm(task.get("source_id")),
                    "component_name": extract_component_name_from_step(step),
                    "canonical_rhs_symbol": norm(candidate_info.get("canonical_rhs_symbol")),
                    "canonical_package_path": norm(candidate_info.get("canonical_package_path")),
                    "candidate_rhs_symbols": list(candidate_info.get("candidate_rhs_symbols") or []),
                    "local_cluster_rhs_values": list(candidate_info.get("local_cluster_rhs_values") or []),
                    "adjacent_component_package_paths": list(candidate_info.get("adjacent_component_package_paths") or []),
                    "source_export_ok": bool(candidate_info.get("candidate_rhs_symbols")),
                }
            )
    task_count = len(rows)
    source_export_ok_count = sum(1 for row in rows if bool(row.get("source_export_ok")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if task_count and source_export_ok_count == task_count else ("PARTIAL" if task_count else "EMPTY"),
        "source_mode": "bounded_local_medium_surface",
        "task_count": task_count,
        "surface_export_success_rate_pct": round(100.0 * source_export_ok_count / float(task_count), 1) if task_count else 0.0,
        "canonical_in_candidate_rate_pct": round(
            100.0
            * sum(1 for row in rows if norm(row.get("canonical_rhs_symbol")) in [norm(x) for x in (row.get("candidate_rhs_symbols") or [])])
            / float(task_count),
            1,
        )
        if task_count
        else 0.0,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "task_rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "surface_index.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.30 Surface Index",
                "",
                f"- status: `{summary.get('status')}`",
                f"- surface_export_success_rate_pct: `{summary.get('surface_export_success_rate_pct')}`",
                f"- canonical_in_candidate_rate_pct: `{summary.get('canonical_in_candidate_rate_pct')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.30 local medium surface index.")
    parser.add_argument("--entry-taskset", default=str(DEFAULT_V0329_ENTRY_TASKSET_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0330_surface_index(
        entry_taskset_path=str(args.entry_taskset),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps(payload.get("summary") or {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
