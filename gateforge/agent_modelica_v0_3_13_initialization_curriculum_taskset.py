from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_dual_layer_mutation_v0_3_5 import build_dual_layer_task
from .agent_modelica_v0_3_13_initialization_curriculum_sources import SOURCE_SPECS


SCHEMA_VERSION = "agent_modelica_v0_3_13_initialization_curriculum_taskset"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_initialization_curriculum_taskset"
FAMILY_ID = "surface_cleanup_then_initialization_parameter_recovery"
COURSE_STAGE = "three_step_initialization_curriculum"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _task_id(source_id: str, lhs: str) -> str:
    return f"{source_id}__lhs_{lhs.lower()}__preview"


def build_initialization_curriculum_taskset(*, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    tasks = []
    out_root = Path(out_dir)
    for spec in SOURCE_SPECS:
        for lhs in [str(x) for x in (spec.get("target_lhs_names") or [])]:
            task = build_dual_layer_task(
                task_id=_task_id(str(spec["source_id"]), lhs),
                clean_source_text=str(spec["model_text"]),
                source_model_path=str(spec["source_model_path"]),
                source_library=str(spec["source_library"]),
                model_hint=str(spec["model_name"]),
                hidden_base_operator="init_equation_sign_flip",
                hidden_base_kwargs={"target_lhs_names": [lhs]},
            )
            task["v0_3_13_family_id"] = FAMILY_ID
            task["course_stage"] = COURSE_STAGE
            task["curriculum_source"] = "v0_3_13_initialization_multi_target_sources"
            task["v0_3_13_source_id"] = str(spec["source_id"])
            task["v0_3_13_initialization_target_lhs"] = lhs
            task["v0_3_13_initialization_target_pool"] = [str(x) for x in (spec.get("target_lhs_names") or [])]
            tasks.append(task)
            _write_json(out_root / "tasks" / f"{task['task_id']}.json", task)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if tasks else "EMPTY",
        "family_id": FAMILY_ID,
        "course_stage": COURSE_STAGE,
        "source_count": len(SOURCE_SPECS),
        "task_count": len(tasks),
        "task_ids": [row["task_id"] for row in tasks],
        "tasks": tasks,
    }
    _write_json(out_root / "taskset.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Initialization Curriculum Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- source_count: `{payload.get('source_count')}`",
                f"- task_count: `{payload.get('task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 initialization curriculum taskset.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_initialization_curriculum_taskset(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
