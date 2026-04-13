from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_15_1"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_1_handoff_integrity_current"
DEFAULT_VIABILITY_RESOLUTION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_1_viability_resolution_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_1_closeout_current"

DEFAULT_V150_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_0_closeout_current" / "summary.json"

EXPECTED_V150_VERSION_DECISION = "v0_15_0_even_broader_change_governance_partial"
EXPECTED_V150_GOVERNANCE_STATUS = "governance_partial"
EXPECTED_V150_VIABILITY_STATUS = "not_justified"
EXPECTED_V150_HANDOFF_MODE = "resolve_v0_15_0_governance_or_viability_gaps_first"
EXPECTED_V150_BLOCKER = "admitted_broader_change_set_covers_available_scope_and_residual_gap_requires_broader_than_governed_change"

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V150_CLOSEOUT_PATH",
    "DEFAULT_VIABILITY_RESOLUTION_OUT_DIR",
    "EXPECTED_V150_BLOCKER",
    "EXPECTED_V150_GOVERNANCE_STATUS",
    "EXPECTED_V150_HANDOFF_MODE",
    "EXPECTED_V150_VERSION_DECISION",
    "EXPECTED_V150_VIABILITY_STATUS",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
