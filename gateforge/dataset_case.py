from __future__ import annotations

import json
from pathlib import Path

REQUIRED_KEYS = {
    "schema_version",
    "case_id",
    "timestamp_utc",
    "source",
    "backend",
    "actual_stage",
    "actual_failure_type",
    "actual_decision",
    "oracle_match",
    "replay_stable",
    "factors",
}

ALLOWED_SOURCE = {"benchmark", "mutation", "run", "autopilot", "manual"}
ALLOWED_BACKEND = {"mock", "openmodelica", "openmodelica_docker", "fmu_runner"}
ALLOWED_STAGE = {"none", "check", "simulate", "regress", "policy", "review"}
ALLOWED_DECISION = {"PASS", "FAIL", "NEEDS_REVIEW"}
ALLOWED_RISK_LEVEL = {"low", "medium", "high"}
ALLOWED_ROOT_CAUSE = {
    "none",
    "parse",
    "model_check",
    "solver",
    "numeric",
    "invariant",
    "performance",
    "drift",
    "governance",
    "unknown",
}
ALLOWED_TRIGGER = {"mutation_rule", "llm_plan", "human_patch", "env_change", "baseline", "unknown"}
ALLOWED_SEVERITY = {"low", "medium", "high"}
ALLOWED_DETERMINISM = {"stable", "flaky", "unknown"}


def load_dataset_case(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _require_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {key}: expected non-empty string")
    return value


def _require_bool(payload: dict, key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Invalid {key}: expected boolean")
    return value


def validate_dataset_case(case: dict) -> None:
    if not isinstance(case, dict):
        raise ValueError("dataset case must be an object")

    missing = sorted(REQUIRED_KEYS - set(case.keys()))
    if missing:
        raise ValueError(f"Missing required keys: {', '.join(missing)}")

    if case.get("schema_version") != "0.1.0":
        raise ValueError("Unsupported schema_version; expected 0.1.0")

    _require_str(case, "case_id")
    _require_str(case, "timestamp_utc")

    source = _require_str(case, "source")
    if source not in ALLOWED_SOURCE:
        raise ValueError(f"Invalid source: {source}")

    backend = _require_str(case, "backend")
    if backend not in ALLOWED_BACKEND:
        raise ValueError(f"Invalid backend: {backend}")

    actual_stage = _require_str(case, "actual_stage")
    if actual_stage not in ALLOWED_STAGE:
        raise ValueError(f"Invalid actual_stage: {actual_stage}")

    actual_failure_type = _require_str(case, "actual_failure_type")
    if not actual_failure_type:
        raise ValueError("Invalid actual_failure_type")

    actual_decision = _require_str(case, "actual_decision")
    if actual_decision not in ALLOWED_DECISION:
        raise ValueError(f"Invalid actual_decision: {actual_decision}")

    _require_bool(case, "oracle_match")
    _require_bool(case, "replay_stable")

    if "intended_stage" in case and case["intended_stage"] not in ALLOWED_STAGE:
        raise ValueError(f"Invalid intended_stage: {case['intended_stage']}")

    if "expected_decision" in case and case["expected_decision"] is not None:
        if case["expected_decision"] not in ALLOWED_DECISION:
            raise ValueError(f"Invalid expected_decision: {case['expected_decision']}")

    if "risk_level" in case and case["risk_level"] is not None:
        if case["risk_level"] not in ALLOWED_RISK_LEVEL:
            raise ValueError(f"Invalid risk_level: {case['risk_level']}")

    factors = case.get("factors")
    if not isinstance(factors, dict):
        raise ValueError("Invalid factors: expected object")
    for key in ("phase", "root_cause", "trigger", "severity", "determinism"):
        if key not in factors:
            raise ValueError(f"Missing factors.{key}")
        if not isinstance(factors[key], str):
            raise ValueError(f"Invalid factors.{key}: expected string")

    if factors["phase"] not in ALLOWED_STAGE:
        raise ValueError(f"Invalid factors.phase: {factors['phase']}")
    if factors["root_cause"] not in ALLOWED_ROOT_CAUSE:
        raise ValueError(f"Invalid factors.root_cause: {factors['root_cause']}")
    if factors["trigger"] not in ALLOWED_TRIGGER:
        raise ValueError(f"Invalid factors.trigger: {factors['trigger']}")
    if factors["severity"] not in ALLOWED_SEVERITY:
        raise ValueError(f"Invalid factors.severity: {factors['severity']}")
    if factors["determinism"] not in ALLOWED_DETERMINISM:
        raise ValueError(f"Invalid factors.determinism: {factors['determinism']}")
