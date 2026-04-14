from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text

SCHEMA_PREFIX = "agent_modelica_v0_19_2"

DEFAULT_V190_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_0_closeout_current" / "summary.json"
DEFAULT_V191_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_1_closeout_current" / "summary.json"
DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_2_handoff_integrity_current"
DEFAULT_TRAJECTORY_OUT_DIR = REPO_ROOT / "artifacts" / "trajectory_dataset_v0_19_2"
DEFAULT_METRIC_OUT_DIR = REPO_ROOT / "artifacts" / "trajectory_metrics_v0_19_2"
DEFAULT_PROFILE_OUT_DIR = REPO_ROOT / "artifacts" / "trajectory_capability_profile_v0_19_2"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_2_closeout_current"

EXPECTED_V190_VERSION_DECISION = "v0_19_0_foundation_ready"
EXPECTED_V191_VERSION_DECISION = "v0_19_1_first_benchmark_batch_ready"
EXPECTED_V191_HANDOFF_MODE = "run_first_real_multiturn_trajectory_dataset"
EXPECTED_ALIGNMENT_STATUS = "PASS"
EXPECTED_ALIGNMENT_SAMPLE_COUNT = 30
EXPECTED_BENCHMARK_MIN_CASES = 50
EXPECTED_DIFFICULTY_STATUS = "PASS"

READY_MIN_COMPLETE_CASES = 45
READY_MAX_INFRA_FAILURES = 5

PROFILE_MIN_CASES = 5
PROFILE_STRONG_THRESHOLD = 0.65
PROFILE_MIXED_THRESHOLD = 0.40

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_METRIC_OUT_DIR",
    "DEFAULT_PROFILE_OUT_DIR",
    "DEFAULT_TRAJECTORY_OUT_DIR",
    "DEFAULT_V190_CLOSEOUT_PATH",
    "DEFAULT_V191_CLOSEOUT_PATH",
    "EXPECTED_ALIGNMENT_SAMPLE_COUNT",
    "EXPECTED_ALIGNMENT_STATUS",
    "EXPECTED_BENCHMARK_MIN_CASES",
    "EXPECTED_DIFFICULTY_STATUS",
    "EXPECTED_V190_VERSION_DECISION",
    "EXPECTED_V191_HANDOFF_MODE",
    "EXPECTED_V191_VERSION_DECISION",
    "PROFILE_MIN_CASES",
    "PROFILE_MIXED_THRESHOLD",
    "PROFILE_STRONG_THRESHOLD",
    "READY_MAX_INFRA_FAILURES",
    "READY_MIN_COMPLETE_CASES",
    "REPO_ROOT",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
