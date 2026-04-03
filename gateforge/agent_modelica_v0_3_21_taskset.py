from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_21_common import (
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    build_v0321_dual_task_rows,
    build_v0321_single_task_rows,
    load_surface_index,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_21_surface_index import build_v0321_surface_index


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_taskset"


def build_v0321_taskset(
    *,
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"),
    out_dir: str = str(DEFAULT_TASKSET_OUT_DIR),
) -> dict:
    if not Path(surface_index_path).exists():
        build_v0321_surface_index(out_dir=str(Path(surface_index_path).parent))
    payload = load_surface_index(surface_index_path)
    surface_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    single_rows = build_v0321_single_task_rows(payload)
    dual_rows = build_v0321_dual_task_rows(payload)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if single_rows and dual_rows else "FAIL",
        "surface_index_status": norm(surface_summary.get("status")),
        "surface_index_source_mode": norm(surface_summary.get("source_mode")),
        "single_task_count": len(single_rows),
        "dual_sidecar_task_count": len(dual_rows),
        "parameter_discovery_task_count": sum(1 for row in single_rows if norm(row.get("patch_type")) == "replace_parameter_name"),
        "class_path_discovery_task_count": sum(1 for row in single_rows if norm(row.get("patch_type")) == "replace_class_path"),
        "placement_kind_counts": {
            "same_component_dual_mismatch": sum(1 for row in dual_rows if norm(row.get("placement_kind")) == "same_component_dual_mismatch"),
            "neighbor_component_dual_mismatch": sum(1 for row in dual_rows if norm(row.get("placement_kind")) == "neighbor_component_dual_mismatch"),
        },
    }
    taskset_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": summary.get("status"),
        "surface_index_path": str(Path(surface_index_path).resolve()) if Path(surface_index_path).exists() else str(surface_index_path),
        "single_tasks": single_rows,
        "dual_sidecar_tasks": dual_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "taskset.json", taskset_payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.21 Taskset",
                "",
                f"- status: `{summary.get('status')}`",
                f"- surface_index_source_mode: `{summary.get('surface_index_source_mode')}`",
                f"- single_task_count: `{summary.get('single_task_count')}`",
                f"- dual_sidecar_task_count: `{summary.get('dual_sidecar_task_count')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "taskset": taskset_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.21 discovery taskset.")
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_TASKSET_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0321_taskset(surface_index_path=str(args.surface_index), out_dir=str(args.out_dir))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "single_task_count": summary.get("single_task_count"), "dual_sidecar_task_count": summary.get("dual_sidecar_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
