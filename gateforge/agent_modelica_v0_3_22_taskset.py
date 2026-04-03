from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_22_common import (
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    build_dual_task_rows,
    build_single_task_rows,
    build_surface_index_payload,
    now_utc,
    norm,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_taskset"


def build_v0322_taskset(
    *,
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"),
    out_dir: str = str(DEFAULT_TASKSET_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    surface_path = Path(surface_index_path)
    if surface_path.exists():
        surface_index = json.loads(surface_path.read_text(encoding="utf-8"))
    else:
        surface_index = build_surface_index_payload(use_fixture_only=use_fixture_only)
    if not isinstance(surface_index, dict):
        surface_index = {}
    single_rows = build_single_task_rows(surface_index)
    dual_rows = build_dual_task_rows(surface_index)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if len(single_rows) >= 12 and len(dual_rows) >= 12 else "FAIL",
        "surface_index_source_mode": norm(surface_index.get("source_mode")),
        "single_task_count": len(single_rows),
        "dual_sidecar_task_count": len(dual_rows),
        "parameter_discovery_task_count": sum(1 for row in single_rows if norm(row.get("patch_type")) == "replace_parameter_name"),
        "class_path_discovery_task_count": sum(1 for row in single_rows if norm(row.get("patch_type")) == "replace_class_path"),
        "placement_kind_counts": {
            "same_component_dual_mismatch": sum(1 for row in dual_rows if norm(row.get("placement_kind")) == "same_component_dual_mismatch"),
            "neighbor_component_dual_mismatch": sum(1 for row in dual_rows if norm(row.get("placement_kind")) == "neighbor_component_dual_mismatch"),
        },
        "component_family_counts": {
            norm(key): sum(1 for row in single_rows if norm(row.get("component_family")) == norm(key))
            for key in sorted({norm(row.get("component_family")) for row in single_rows if norm(row.get("component_family"))})
        },
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": summary.get("status"),
        "surface_index_path": str(surface_path.resolve()) if surface_path.exists() else str(surface_index_path),
        "single_tasks": single_rows,
        "dual_sidecar_tasks": dual_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "taskset.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.22 Taskset",
                "",
                f"- status: `{summary.get('status')}`",
                f"- surface_index_source_mode: `{summary.get('surface_index_source_mode')}`",
                f"- single_task_count: `{summary.get('single_task_count')}`",
                f"- dual_sidecar_task_count: `{summary.get('dual_sidecar_task_count')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "taskset": payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.22 coverage taskset.")
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_TASKSET_OUT_DIR))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0322_taskset(
        surface_index_path=str(args.surface_index),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.fixture_only),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "single_task_count": summary.get("single_task_count"), "dual_sidecar_task_count": summary.get("dual_sidecar_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
