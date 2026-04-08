from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_8_3"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_3_handoff_integrity_current"
)
DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_3_threshold_validation_replay_pack_current"
)
DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_3_threshold_validation_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_3_closeout_current"
)

DEFAULT_V082_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_closeout_current" / "summary.json"
)
DEFAULT_V081_REPLAY_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_profile_replay_pack_current" / "summary.json"
)


def rule_count(route_flags: dict[str, bool]) -> int:
    return sum(1 for value in route_flags.values() if bool(value))


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR",
    "DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR",
    "DEFAULT_V081_REPLAY_PACK_PATH",
    "DEFAULT_V082_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "rule_count",
    "write_json",
    "write_text",
]
