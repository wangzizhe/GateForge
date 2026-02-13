from __future__ import annotations

import json
from pathlib import Path

from .checkers import available_checkers

SUPPORTED_ACTIONS = {"check", "simulate", "regress", "benchmark"}
SUPPORTED_AUTHOR_TYPES = {"human", "agent"}
SUPPORTED_BACKENDS = {"mock", "openmodelica", "openmodelica_docker", "fmu_runner"}
SUPPORTED_RISK_LEVELS = {"low", "medium", "high"}
SUPPORTED_SCRIPT_SUFFIXES = (".mos", ".fmu")
PROPOSAL_SCHEMA_VERSION = "0.1.0"
EXECUTION_ACTIONS = {"check", "simulate"}


def load_proposal(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_proposal(proposal: dict) -> None:
    required = {
        "schema_version",
        "proposal_id",
        "timestamp_utc",
        "author_type",
        "backend",
        "model_script",
        "change_summary",
        "requested_actions",
        "risk_level",
    }
    missing = sorted(required - set(proposal.keys()))
    if missing:
        raise ValueError(f"Missing required proposal keys: {missing}")

    if proposal["schema_version"] != PROPOSAL_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {PROPOSAL_SCHEMA_VERSION}")

    _require_non_empty_string(proposal, "proposal_id")
    _require_non_empty_string(proposal, "timestamp_utc")
    _require_non_empty_string(proposal, "change_summary")

    author_type = proposal["author_type"]
    if author_type not in SUPPORTED_AUTHOR_TYPES:
        raise ValueError(f"author_type must be one of {sorted(SUPPORTED_AUTHOR_TYPES)}")

    backend = proposal["backend"]
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"backend must be one of {sorted(SUPPORTED_BACKENDS)}")

    model_script = proposal["model_script"]
    _require_non_empty_string(proposal, "model_script")
    if not model_script.endswith(SUPPORTED_SCRIPT_SUFFIXES):
        raise ValueError("model_script must end with .mos or .fmu")

    actions = proposal["requested_actions"]
    if not isinstance(actions, list) or not actions:
        raise ValueError("requested_actions must be a non-empty list")
    for action in actions:
        if action not in SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported requested action: {action}")

    risk_level = proposal["risk_level"]
    if risk_level not in SUPPORTED_RISK_LEVELS:
        raise ValueError(f"risk_level must be one of {sorted(SUPPORTED_RISK_LEVELS)}")

    change_set_path = proposal.get("change_set_path")
    if change_set_path is not None:
        if not isinstance(change_set_path, str) or not change_set_path.strip():
            raise ValueError("change_set_path must be a non-empty string when provided")

    checkers = proposal.get("checkers")
    if checkers is not None:
        if not isinstance(checkers, list):
            raise ValueError("checkers must be a list when provided")
        supported_checkers = set(available_checkers())
        for checker in checkers:
            if not isinstance(checker, str) or not checker.strip():
                raise ValueError("checkers must contain non-empty strings")
            if checker not in supported_checkers:
                raise ValueError(f"unsupported checker: {checker}")

    checker_config = proposal.get("checker_config")
    if checker_config is not None:
        if not isinstance(checker_config, dict):
            raise ValueError("checker_config must be an object when provided")
        supported_checkers = set(available_checkers())
        for checker_name, cfg in checker_config.items():
            if checker_name == "_runtime":
                if not isinstance(cfg, dict):
                    raise ValueError("checker_config[_runtime] must be an object")
                for runtime_key in cfg.keys():
                    if runtime_key not in {"enable", "disable"}:
                        raise ValueError("checker_config[_runtime] supports only enable/disable")
                for runtime_key in ("enable", "disable"):
                    names = cfg.get(runtime_key)
                    if names is None:
                        continue
                    if not isinstance(names, list):
                        raise ValueError(f"checker_config[_runtime].{runtime_key} must be a list")
                    for checker in names:
                        if not isinstance(checker, str) or checker not in supported_checkers:
                            raise ValueError(
                                f"checker_config[_runtime].{runtime_key} contains unsupported checker: {checker}"
                            )
                continue
            if checker_name not in supported_checkers:
                raise ValueError(f"checker_config contains unsupported checker: {checker_name}")
            if not isinstance(cfg, dict):
                raise ValueError(f"checker_config[{checker_name}] must be an object")

        perf_cfg = checker_config.get("performance_regression")
        if perf_cfg is not None and "max_ratio" in perf_cfg:
            ratio = perf_cfg["max_ratio"]
            if not isinstance(ratio, (int, float)) or ratio <= 0:
                raise ValueError("checker_config.performance_regression.max_ratio must be > 0")

        event_cfg = checker_config.get("event_explosion")
        if event_cfg is not None:
            if "max_ratio" in event_cfg:
                ratio = event_cfg["max_ratio"]
                if not isinstance(ratio, (int, float)) or ratio <= 0:
                    raise ValueError("checker_config.event_explosion.max_ratio must be > 0")
            if "abs_threshold_if_baseline_zero" in event_cfg:
                threshold = event_cfg["abs_threshold_if_baseline_zero"]
                if not isinstance(threshold, int) or threshold < 0:
                    raise ValueError(
                        "checker_config.event_explosion.abs_threshold_if_baseline_zero must be >= 0 integer"
                    )

        steady_cfg = checker_config.get("steady_state_regression")
        if steady_cfg is not None and "max_abs_delta" in steady_cfg:
            delta = steady_cfg["max_abs_delta"]
            if not isinstance(delta, (int, float)) or delta <= 0:
                raise ValueError("checker_config.steady_state_regression.max_abs_delta must be > 0")

        control_cfg = checker_config.get("control_behavior_regression")
        if control_cfg is not None:
            if "max_overshoot_abs_delta" in control_cfg:
                value = control_cfg["max_overshoot_abs_delta"]
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(
                        "checker_config.control_behavior_regression.max_overshoot_abs_delta must be > 0"
                    )
            if "max_settling_time_ratio" in control_cfg:
                value = control_cfg["max_settling_time_ratio"]
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(
                        "checker_config.control_behavior_regression.max_settling_time_ratio must be > 0"
                    )
            if "max_steady_state_abs_delta" in control_cfg:
                value = control_cfg["max_steady_state_abs_delta"]
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(
                        "checker_config.control_behavior_regression.max_steady_state_abs_delta must be > 0"
                    )


def execution_target_from_proposal(proposal: dict) -> tuple[str, str]:
    # v0 contract: smoke execution is only valid when proposal requests check/simulate.
    validate_proposal(proposal)
    actions = set(proposal["requested_actions"])
    if not actions.intersection(EXECUTION_ACTIONS):
        raise ValueError(
            f"proposal requested_actions must include at least one of {sorted(EXECUTION_ACTIONS)}"
        )
    return proposal["backend"], proposal["model_script"]


def _require_non_empty_string(payload: dict, key: str) -> None:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
