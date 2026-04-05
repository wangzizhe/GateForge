from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_0_common import (
    DEFAULT_BENCHMARK_FREEZE_OUT_DIR,
    DEFAULT_SINGLE_TASKS_PER_FAMILY,
    DEFAULT_DUAL_TASKS_PER_FAMILY,
    FAMILY_SOURCES,
    SCHEMA_PREFIX,
    benchmark_task_payload,
    deterministic_pick,
    family_dispatch_policy,
    load_json,
    now_utc,
    task_rows,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_benchmark_freeze"


def build_v040_benchmark_freeze(
    *,
    out_dir: str = str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR),
    single_tasks_per_family: int = DEFAULT_SINGLE_TASKS_PER_FAMILY,
    dual_tasks_per_family: int = DEFAULT_DUAL_TASKS_PER_FAMILY,
    family_sources: list[dict] | None = None,
) -> dict:
    sources = family_sources or FAMILY_SOURCES
    frozen_tasks: list[dict] = []
    family_task_breakdown: dict[str, dict] = {}
    family_source_refs: dict[str, dict] = {}

    for family_order, family in enumerate(sources, start=1):
        family_id = str(family.get("family_id") or "").strip()
        taskset_path = str(family.get("taskset_path") or "")
        payload = load_json(taskset_path)
        single_rows = deterministic_pick(task_rows(payload, str(family.get("single_key") or "")), int(single_tasks_per_family))
        dual_rows = deterministic_pick(task_rows(payload, str(family.get("dual_key") or "")), int(dual_tasks_per_family))
        for row in single_rows:
            frozen_tasks.append(
                benchmark_task_payload(
                    family_id=family_id,
                    family_order=family_order,
                    task_role="single",
                    row=row,
                    source_taskset_path=taskset_path,
                )
            )
        for row in dual_rows:
            frozen_tasks.append(
                benchmark_task_payload(
                    family_id=family_id,
                    family_order=family_order,
                    task_role="dual",
                    row=row,
                    source_taskset_path=taskset_path,
                )
            )
        family_task_breakdown[family_id] = {
            "single_task_count": len(single_rows),
            "dual_task_count": len(dual_rows),
            "total_task_count": len(single_rows) + len(dual_rows),
        }
        family_source_refs[family_id] = {
            "taskset_path": str(Path(taskset_path).resolve()),
            "source_closeout_path": str(Path(str(family.get("source_closeout_path") or "")).resolve()) if str(family.get("source_closeout_path") or "") else "",
        }

    benchmark_freeze_ready = len(family_task_breakdown) == 3 and all(
        int((family_task_breakdown.get(family.get("family_id")) or {}).get("single_task_count") or 0) > 0
        and int((family_task_breakdown.get(family.get("family_id")) or {}).get("dual_task_count") or 0) > 0
        for family in sources
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if benchmark_freeze_ready else "FAIL",
        "benchmark_freeze_ready": benchmark_freeze_ready,
        "benchmark_family_count": len(family_task_breakdown),
        "benchmark_task_count": len(frozen_tasks),
        "family_task_breakdown": family_task_breakdown,
        "family_source_refs": family_source_refs,
        "family_dispatch_policy": family_dispatch_policy(),
        "single_tasks_per_family_target": int(single_tasks_per_family),
        "dual_tasks_per_family_target": int(dual_tasks_per_family),
        "tasks": frozen_tasks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "benchmark_pack.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.0 Benchmark Freeze",
                "",
                f"- status: `{payload.get('status')}`",
                f"- benchmark_family_count: `{payload.get('benchmark_family_count')}`",
                f"- benchmark_task_count: `{payload.get('benchmark_task_count')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the v0.4.0 three-family synthetic benchmark.")
    parser.add_argument("--out-dir", default=str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR))
    parser.add_argument("--single-per-family", type=int, default=DEFAULT_SINGLE_TASKS_PER_FAMILY)
    parser.add_argument("--dual-per-family", type=int, default=DEFAULT_DUAL_TASKS_PER_FAMILY)
    args = parser.parse_args()
    payload = build_v040_benchmark_freeze(
        out_dir=str(args.out_dir),
        single_tasks_per_family=int(args.single_per_family),
        dual_tasks_per_family=int(args.dual_per_family),
    )
    print(json.dumps({"status": payload.get("status"), "benchmark_task_count": payload.get("benchmark_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
