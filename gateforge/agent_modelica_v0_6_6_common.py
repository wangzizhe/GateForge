from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_PREFIX = "agent_modelica_v0_6_6"

ARTIFACT_ROOT = Path("artifacts")
DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_6_handoff_integrity_current"
DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_6_complex_gap_recheck_current"
DEFAULT_TERMINAL_DECISION_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_6_terminal_decision_current"
DEFAULT_CLOSEOUT_OUT_DIR = ARTIFACT_ROOT / "agent_modelica_v0_6_6_closeout_current"

DEFAULT_V062_CLOSEOUT_PATH = ARTIFACT_ROOT / "agent_modelica_v0_6_2_closeout_current" / "summary.json"
DEFAULT_V064_CLOSEOUT_PATH = ARTIFACT_ROOT / "agent_modelica_v0_6_4_closeout_current" / "summary.json"
DEFAULT_V065_CLOSEOUT_PATH = ARTIFACT_ROOT / "agent_modelica_v0_6_5_closeout_current" / "summary.json"

OPEN_WORLD_READY_STABLE_COVERAGE_MIN = 50.0
OPEN_WORLD_MEANINGFUL_IMPROVEMENT_MIN = 1.5


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
