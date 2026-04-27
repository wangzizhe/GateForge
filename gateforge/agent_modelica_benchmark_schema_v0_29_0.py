from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_schema_v0_29_0"

SCHEMA_VERSION = "gateforge_benchmark_task_v1"

ALLOWED_TASK_TYPES = {"repair", "generation", "extension", "refactor"}
ALLOWED_DIFFICULTIES = {"simple", "medium", "complex"}
ALLOWED_BEHAVIORAL_TYPES = {"pass_through", "time_constant", "spec_assertions"}

REQUIRED_TOP_FIELDS = (
    "case_id",
    "task_type",
    "title",
    "difficulty",
    "source_backed",
    "description",
    "initial_model",
    "verification",
)

_RE_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_benchmark_task(task: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    # Required fields
    for field in REQUIRED_TOP_FIELDS:
        if field not in task:
            errors.append(f"missing_required:{field}")

    if errors:
        return errors

    # case_id format
    case_id = str(task.get("case_id") or "")
    if not _RE_ID.match(case_id):
        errors.append(f"invalid_case_id:{case_id}")

    # task_type
    task_type = str(task.get("task_type") or "").lower()
    if task_type not in ALLOWED_TASK_TYPES:
        errors.append(f"invalid_task_type:{task_type}")

    # difficulty
    difficulty = str(task.get("difficulty") or "").lower()
    if difficulty not in ALLOWED_DIFFICULTIES:
        errors.append(f"invalid_difficulty:{difficulty}")

    # source_backed
    if not isinstance(task.get("source_backed"), bool):
        errors.append("source_backed_must_be_bool")

    # description
    desc = str(task.get("description") or "")
    if len(desc.strip()) < 10:
        errors.append("description_too_short")

    # initial_model: must be string (empty for generation is OK)
    if not isinstance(task.get("initial_model"), str):
        errors.append("initial_model_must_be_string")
    else:
        init_model = str(task["initial_model"])
        if task_type == "generation":
            if init_model.strip():
                model_match = re.search(r"\bmodel\s+(\w+)", init_model)
                if model_match:
                    errors.append("generation_task_should_not_have_full_model_as_initial")

    # constraints (optional)
    constraints = task.get("constraints")
    if constraints is not None and not isinstance(constraints, list):
        errors.append("constraints_must_be_list")

    # verification
    ver = task.get("verification")
    if not isinstance(ver, dict):
        errors.append("verification_must_be_dict")
        return errors

    # check_model
    if not isinstance(ver.get("check_model"), bool):
        errors.append("verification.check_model_must_be_bool")

    # simulate (required if check_model is true)
    sim = ver.get("simulate")
    if isinstance(sim, dict):
        if not isinstance(sim.get("stop_time"), (int, float)):
            errors.append("simulate.stop_time_must_be_number")
        if not isinstance(sim.get("intervals"), int) or int(sim["intervals"]) < 1:
            errors.append("simulate.intervals_must_be_positive_int")

    # behavioral (optional)
    behav = ver.get("behavioral")
    if isinstance(behav, dict):
        btype = str(behav.get("type") or "").lower()
        if btype not in ALLOWED_BEHAVIORAL_TYPES:
            errors.append(f"invalid_behavioral_type:{btype}")
        if btype == "time_constant":
            for key in ("expected_tau", "tolerance"):
                if key not in behav:
                    errors.append(f"behavioral_missing_{key}_for_time_constant")
        elif btype == "spec_assertions":
            assertions = behav.get("assertions")
            if not isinstance(assertions, list) or len(assertions) < 1:
                errors.append("behavioral_assertions_must_be_nonempty_list")

    return errors


def build_schema_summary(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    canonical_tasks = {
        "repair": {
            "case_id": "repair_test_001",
            "task_type": "repair",
            "title": "Fix missing equation in RC circuit",
            "difficulty": "simple",
            "source_backed": True,
            "description": "The model has an under-determined system. Fix it so checkModel and simulate pass.",
            "initial_model": "model Test\n  Real x;\nend Test;\n",
            "constraints": ["Keep model name unchanged."],
            "verification": {
                "check_model": True,
                "simulate": {"stop_time": 0.05, "intervals": 100},
            },
        },
        "generation": {
            "case_id": "gen_test_001",
            "task_type": "generation",
            "title": "Create an RC circuit model",
            "difficulty": "simple",
            "source_backed": True,
            "description": "Create a Modelica model of an RC circuit with R=100ohm, C=0.01F, powered by a 10V constant voltage source.",
            "initial_model": "",
            "verification": {
                "check_model": True,
                "simulate": {"stop_time": 1.0, "intervals": 500},
                "behavioral": {"type": "time_constant", "expected_tau": 1.0, "tolerance": 0.08},
            },
        },
    }

    validation_errors: dict[str, list[str]] = {}
    for name, task in canonical_tasks.items():
        errs = validate_benchmark_task(task)
        if errs:
            validation_errors[name] = errs

    summary = {
        "version": "v0.29.0",
        "status": "PASS" if not validation_errors else "REVIEW",
        "schema_version": SCHEMA_VERSION,
        "allowed_task_types": sorted(ALLOWED_TASK_TYPES),
        "allowed_difficulties": sorted(ALLOWED_DIFFICULTIES),
        "allowed_behavioral_types": sorted(ALLOWED_BEHAVIORAL_TYPES),
        "required_fields": list(REQUIRED_TOP_FIELDS),
        "validation_errors": validation_errors,
        "decision": (
            "benchmark_schema_ready"
            if not validation_errors
            else "benchmark_schema_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "schema.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
