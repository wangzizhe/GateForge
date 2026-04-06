from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_PREFIX = "agent_modelica_v0_6_4"

ARTIFACT_ROOT = Path("artifacts")
DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_4_handoff_integrity_current"
DEFAULT_PROFILE_REFINEMENT_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_4_profile_refinement_current"
DEFAULT_CANDIDATE_PRESSURE_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_4_candidate_pressure_current"
DEFAULT_DECISION_MATURITY_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_4_decision_maturity_current"
DEFAULT_CLOSEOUT_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_4_closeout_current"

DEFAULT_V060_CLOSEOUT_PATH = ARTIFACT_ROOT / "agent_modelica_v0_6_0_closeout_current" / "summary.json"
DEFAULT_V062_CLOSEOUT_PATH = ARTIFACT_ROOT / "agent_modelica_v0_6_2_closeout_current" / "summary.json"
DEFAULT_V062_LIVE_RUN_PATH = ARTIFACT_ROOT / "agent_modelica_v0_6_2_live_run_current" / "summary.json"
DEFAULT_V063_CLOSEOUT_PATH = ARTIFACT_ROOT / "agent_modelica_v0_6_3_closeout_current" / "summary.json"

OPEN_WORLD_READY_STABLE_COVERAGE_MIN = 50.0
OPEN_WORLD_NEAR_MISS_STABLE_COVERAGE_MIN = 45.0
OPEN_WORLD_SPILLOVER_MAX = 10.0
TARGETED_EXPANSION_READY_BOUNDED_UNCOVERED_MIN = 15.0
TARGETED_EXPANSION_NEAR_MISS_BOUNDED_UNCOVERED_MIN = 12.0
DOMINANT_PRESSURE_SHARE_MIN = 50.0
FLUID_NETWORK_BLOCKING_CASE_MIN = 3


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_text(path: str | Path, text: str) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(text, encoding="utf-8")


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, 1)


def count_rows(rows: list[dict[str, Any]], *, key: str, value: str) -> int:
    return sum(1 for row in rows if str(row.get(key) or "") == value)
