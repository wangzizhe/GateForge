from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_20_common import (
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    build_dual_task_rows,
    build_single_task_rows,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_taskset"


def build_v0320_taskset(*, out_dir: str = str(DEFAULT_TASKSET_OUT_DIR)) -> dict:
    single_tasks = build_single_task_rows()
    dual_tasks = build_dual_task_rows()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if single_tasks else "EMPTY",
        "single_task_count": len(single_tasks),
        "dual_sidecar_task_count": len(dual_tasks),
        "single_tasks": single_tasks,
        "dual_sidecar_tasks": dual_tasks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "taskset.json", payload)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.20 Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- single_task_count: `{payload.get('single_task_count')}`",
                f"- dual_sidecar_task_count: `{payload.get('dual_sidecar_task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.20 single/dual taskset.")
    parser.add_argument("--out-dir", default=str(DEFAULT_TASKSET_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0320_taskset(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "single_task_count": payload.get("single_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
