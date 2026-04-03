from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_PREFIX = "agent_modelica_v0_3_18"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PROMPT_PACK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_prompt_pack_current" / "prompt_pack.json"
DEFAULT_GENERATION_CENSUS_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current" / "summary.json"
DEFAULT_REPAIR_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current" / "repair_taskset.json"
DEFAULT_ONE_STEP_REPAIR_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_one_step_live_repair_current" / "summary.json"

DEFAULT_SAMPLE_MANIFEST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_18_stage2_sample_manifest_current"
DEFAULT_DIAGNOSIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_18_stage2_diagnosis_current"
DEFAULT_CHARACTERIZATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_18_stage2_characterization_current"
DEFAULT_TARGETING_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_18_stage2_family_targeting_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_18_closeout_current"

FROZEN_STAGE2_SAMPLE_TASK_IDS = (
    "gen_simple_rc_lowpass_filter",
    "gen_simple_thermal_heated_mass",
    "gen_simple_two_inertia_shaft",
    "gen_simple_sine_driven_mass",
    "gen_medium_dc_motor_pi_speed",
    "gen_medium_pump_tank_pipe_loop",
    "gen_complex_liquid_cooling_loop",
    "gen_complex_coupled_motor_drive_cooling",
)

FROZEN_SAMPLE_STRATEGY = {
    "simple": {
        "selection_mode": "all_stage2_failures",
        "task_ids": [
            "gen_simple_rc_lowpass_filter",
            "gen_simple_thermal_heated_mass",
            "gen_simple_two_inertia_shaft",
            "gen_simple_sine_driven_mass",
        ],
    },
    "medium": {
        "selection_mode": "freeze_two_for_error_subtype_coverage",
        "target_error_subtypes": [
            "undefined_symbol",
            "compile_failure_unknown",
        ],
        "task_ids": [
            "gen_medium_dc_motor_pi_speed",
            "gen_medium_pump_tank_pipe_loop",
        ],
    },
    "complex": {
        "selection_mode": "freeze_two_for_error_subtype_coverage",
        "target_error_subtypes": [
            "undefined_symbol",
            "compile_failure_unknown",
        ],
        "task_ids": [
            "gen_complex_liquid_cooling_loop",
            "gen_complex_coupled_motor_drive_cooling",
        ],
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(value: object) -> str:
    return str(value or "").strip()


def load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def task_id_map(rows: list[dict]) -> dict[str, dict]:
    return {
        norm(row.get("task_id")): row
        for row in rows
        if isinstance(row, dict) and norm(row.get("task_id"))
    }
