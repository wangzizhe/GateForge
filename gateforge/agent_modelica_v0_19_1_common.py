from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text

SCHEMA_PREFIX = "agent_modelica_v0_19_1"

DEFAULT_V190_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_0_closeout_current" / "summary.json"
DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_1_handoff_integrity_current"
DEFAULT_GENERATOR_OUT_DIR = REPO_ROOT / "artifacts" / "composite_mutation_generator_v0_19_1_current"
DEFAULT_PREVIEW_OUT_DIR = REPO_ROOT / "artifacts" / "trajectory_preview_filter_v0_19_1_current"
DEFAULT_EMPIRICAL_OUT_DIR = REPO_ROOT / "artifacts" / "empirical_difficulty_filter_v0_19_1_current"
DEFAULT_BENCHMARK_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_v0_19_1"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_1_closeout_current"

EXPECTED_V190_VERSION_DECISION = "v0_19_0_foundation_ready"
EXPECTED_DISTRIBUTION_ALIGNMENT_STATUS = "PASS"
EXPECTED_ALIGNMENT_SAMPLE_COUNT = 30

FRONTIER_AGENT_ID = "gateforge_frontier_agent_v0_19_1_reference"
KNOWN_AGENT_READABLE_SIGNAL_FAMILIES = frozenset({"T1", "T2", "T3", "T4", "T5", "T6"})

BENCHMARK_MIN_CASES = 50
TURN1_SUCCESS_RATE_MIN = 0.15
TURN1_SUCCESS_RATE_MAX = 0.40
TURNN_SUCCESS_RATE_MIN = 0.50
TURNN_SUCCESS_RATE_MAX = 0.75
TARGET_MAX_TURNS = 8

__all__ = [
    "BENCHMARK_MIN_CASES",
    "DEFAULT_BENCHMARK_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_EMPIRICAL_OUT_DIR",
    "DEFAULT_GENERATOR_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PREVIEW_OUT_DIR",
    "DEFAULT_V190_CLOSEOUT_PATH",
    "EXPECTED_ALIGNMENT_SAMPLE_COUNT",
    "EXPECTED_DISTRIBUTION_ALIGNMENT_STATUS",
    "EXPECTED_V190_VERSION_DECISION",
    "FRONTIER_AGENT_ID",
    "KNOWN_AGENT_READABLE_SIGNAL_FAMILIES",
    "REPO_ROOT",
    "SCHEMA_PREFIX",
    "TARGET_MAX_TURNS",
    "TURN1_SUCCESS_RATE_MAX",
    "TURN1_SUCCESS_RATE_MIN",
    "TURNN_SUCCESS_RATE_MAX",
    "TURNN_SUCCESS_RATE_MIN",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
