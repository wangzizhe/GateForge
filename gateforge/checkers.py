from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

CheckerFn = Callable[[dict, dict, dict], list[dict]]


@dataclass(frozen=True)
class Finding:
    checker: str
    reason: str
    message: str
    severity: str = "error"
    evidence: dict | None = None

    def to_dict(self) -> dict:
        payload = {
            "checker": self.checker,
            "reason": self.reason,
            "message": self.message,
            "severity": self.severity,
        }
        if self.evidence:
            payload["evidence"] = self.evidence
        return payload


def _make_finding(checker: str, reason: str, message: str, severity: str = "error", evidence: dict | None = None) -> dict:
    return Finding(
        checker=checker,
        reason=reason,
        message=message,
        severity=severity,
        evidence=evidence,
    ).to_dict()


def timeout_checker(_baseline: dict, candidate: dict, _checker_config: dict) -> list[dict]:
    failure_type = str(candidate.get("failure_type", ""))
    if failure_type == "timeout":
        return [
            _make_finding(
                checker="timeout",
                reason="timeout_detected",
                message="Candidate execution hit timeout.",
            )
        ]
    return []


def nan_inf_checker(_baseline: dict, candidate: dict, _checker_config: dict) -> list[dict]:
    failure_type = str(candidate.get("failure_type", ""))
    log_excerpt = str(candidate.get("artifacts", {}).get("log_excerpt", "")).lower()
    if failure_type == "nan_inf" or "nan" in log_excerpt or "inf" in log_excerpt:
        return [
            _make_finding(
                checker="nan_inf",
                reason="nan_inf_detected",
                message="Candidate output indicates NaN/Inf instability.",
            )
        ]
    return []


def performance_regression_checker(baseline: dict, candidate: dict, checker_config: dict) -> list[dict]:
    base_runtime = float(baseline.get("metrics", {}).get("runtime_seconds", 0.0))
    cand_runtime = float(candidate.get("metrics", {}).get("runtime_seconds", 0.0))
    cfg = checker_config.get("performance_regression", {})
    ratio = float(cfg.get("max_ratio", 2.0))
    if base_runtime <= 0:
        return []
    if cand_runtime > (base_runtime * ratio):
        return [
            _make_finding(
                checker="performance_regression",
                reason="performance_regression_detected",
                message=(
                    f"Candidate runtime {cand_runtime:.4f}s exceeds {ratio:.2f}x baseline "
                    f"{base_runtime:.4f}s."
                ),
            )
        ]
    return []


def event_explosion_checker(baseline: dict, candidate: dict, checker_config: dict) -> list[dict]:
    base_events = int(baseline.get("metrics", {}).get("events", 0))
    cand_events = int(candidate.get("metrics", {}).get("events", 0))
    cfg = checker_config.get("event_explosion", {})
    ratio = float(cfg.get("max_ratio", 2.0))
    abs_zero = int(cfg.get("abs_threshold_if_baseline_zero", 100))
    if base_events > 0:
        if cand_events > (base_events * ratio):
            return [
                _make_finding(
                    checker="event_explosion",
                    reason="event_explosion_detected",
                    message=(
                        f"Candidate events {cand_events} exceeds {ratio:.2f}x baseline {base_events}."
                    ),
                )
            ]
        return []
    if cand_events >= abs_zero:
        return [
            _make_finding(
                checker="event_explosion",
                reason="event_explosion_detected",
                message=(
                    f"Candidate events {cand_events} unexpectedly high from zero baseline "
                    f"(threshold {abs_zero})."
                ),
            )
        ]
    return []


def steady_state_regression_checker(baseline: dict, candidate: dict, checker_config: dict) -> list[dict]:
    cfg = checker_config.get("steady_state_regression", {})
    max_abs_delta = float(cfg.get("max_abs_delta", 0.05))
    b = baseline.get("metrics", {}).get("steady_state_error")
    c = candidate.get("metrics", {}).get("steady_state_error")
    if b is None or c is None:
        return []
    base_error = float(b)
    cand_error = float(c)
    delta = abs(cand_error - base_error)
    if delta > max_abs_delta:
        return [
            _make_finding(
                checker="steady_state_regression",
                reason="steady_state_regression_detected",
                message=(
                    f"Steady-state error delta {delta:.4f} exceeds threshold {max_abs_delta:.4f} "
                    f"(baseline={base_error:.4f}, candidate={cand_error:.4f})."
                ),
                evidence={
                    "baseline.metrics.steady_state_error": base_error,
                    "candidate.metrics.steady_state_error": cand_error,
                    "max_abs_delta": max_abs_delta,
                },
            )
        ]
    return []


def control_behavior_regression_checker(baseline: dict, candidate: dict, checker_config: dict) -> list[dict]:
    cfg = checker_config.get("control_behavior_regression", {})
    max_overshoot_abs_delta = float(cfg.get("max_overshoot_abs_delta", 0.1))
    max_settling_time_ratio = float(cfg.get("max_settling_time_ratio", 1.5))
    max_steady_state_abs_delta = float(cfg.get("max_steady_state_abs_delta", 0.05))

    findings: list[dict] = []

    b_overshoot = baseline.get("metrics", {}).get("overshoot")
    c_overshoot = candidate.get("metrics", {}).get("overshoot")
    if b_overshoot is not None and c_overshoot is not None:
        base_overshoot = float(b_overshoot)
        cand_overshoot = float(c_overshoot)
        overshoot_delta = abs(cand_overshoot - base_overshoot)
        if overshoot_delta > max_overshoot_abs_delta:
            findings.append(
                _make_finding(
                    checker="control_behavior_regression",
                    reason="overshoot_regression_detected",
                    message=(
                        f"Overshoot delta {overshoot_delta:.4f} exceeds threshold "
                        f"{max_overshoot_abs_delta:.4f} (baseline={base_overshoot:.4f}, "
                        f"candidate={cand_overshoot:.4f})."
                    ),
                    evidence={
                        "baseline.metrics.overshoot": base_overshoot,
                        "candidate.metrics.overshoot": cand_overshoot,
                        "max_overshoot_abs_delta": max_overshoot_abs_delta,
                    },
                )
            )

    b_settling = baseline.get("metrics", {}).get("settling_time")
    c_settling = candidate.get("metrics", {}).get("settling_time")
    if b_settling is not None and c_settling is not None:
        base_settling = float(b_settling)
        cand_settling = float(c_settling)
        if base_settling > 0:
            max_allowed = base_settling * max_settling_time_ratio
            if cand_settling > max_allowed:
                findings.append(
                    _make_finding(
                        checker="control_behavior_regression",
                        reason="settling_time_regression_detected",
                        message=(
                            f"Settling time {cand_settling:.4f}s exceeds {max_settling_time_ratio:.2f}x "
                            f"baseline {base_settling:.4f}s."
                        ),
                        evidence={
                            "baseline.metrics.settling_time": base_settling,
                            "candidate.metrics.settling_time": cand_settling,
                            "max_settling_time_ratio": max_settling_time_ratio,
                        },
                    )
                )

    b_steady = baseline.get("metrics", {}).get("steady_state_error")
    c_steady = candidate.get("metrics", {}).get("steady_state_error")
    if b_steady is not None and c_steady is not None:
        base_steady = float(b_steady)
        cand_steady = float(c_steady)
        steady_delta = abs(cand_steady - base_steady)
        if steady_delta > max_steady_state_abs_delta:
            findings.append(
                _make_finding(
                    checker="control_behavior_regression",
                    reason="steady_state_regression_detected",
                    message=(
                        f"Steady-state error delta {steady_delta:.4f} exceeds threshold "
                        f"{max_steady_state_abs_delta:.4f} (baseline={base_steady:.4f}, "
                        f"candidate={cand_steady:.4f})."
                    ),
                    evidence={
                        "baseline.metrics.steady_state_error": base_steady,
                        "candidate.metrics.steady_state_error": cand_steady,
                        "max_steady_state_abs_delta": max_steady_state_abs_delta,
                    },
                )
            )

    return findings


BUILTIN_CHECKERS: dict[str, CheckerFn] = {
    "timeout": timeout_checker,
    "nan_inf": nan_inf_checker,
    "performance_regression": performance_regression_checker,
    "event_explosion": event_explosion_checker,
    "steady_state_regression": steady_state_regression_checker,
    "control_behavior_regression": control_behavior_regression_checker,
}

CHECKER_REGISTRY: dict[str, CheckerFn] = dict(BUILTIN_CHECKERS)

CHECKER_DEFAULT_CONFIG: dict[str, dict] = {
    "performance_regression": {"max_ratio": 2.0},
    "event_explosion": {"max_ratio": 2.0, "abs_threshold_if_baseline_zero": 100},
    "steady_state_regression": {"max_abs_delta": 0.05},
    "control_behavior_regression": {
        "max_overshoot_abs_delta": 0.1,
        "max_settling_time_ratio": 1.5,
        "max_steady_state_abs_delta": 0.05,
    },
}


def register_checker(name: str, checker: CheckerFn) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("checker name must be non-empty string")
    CHECKER_REGISTRY[name] = checker


def unregister_checker(name: str) -> None:
    if name in BUILTIN_CHECKERS:
        raise ValueError(f"Cannot unregister builtin checker: {name}")
    CHECKER_REGISTRY.pop(name, None)


def available_checkers() -> list[str]:
    return sorted(CHECKER_REGISTRY.keys())


def checker_config_template(checker_names: list[str] | None = None, include_runtime: bool = True) -> dict:
    resolved_names = list(checker_names) if checker_names is not None else available_checkers()
    template: dict = {}
    for name in resolved_names:
        defaults = CHECKER_DEFAULT_CONFIG.get(name)
        if defaults is not None:
            template[name] = deepcopy(defaults)
    if include_runtime:
        template["_runtime"] = {"enable": [], "disable": []}
    return template


def _resolve_checker_names(checker_names: list[str] | None, checker_config: dict) -> list[str]:
    names = list(checker_names) if checker_names is not None else available_checkers()
    runtime_cfg = checker_config.get("_runtime", {})
    if not isinstance(runtime_cfg, dict):
        return names
    enable = runtime_cfg.get("enable", [])
    disable = set(runtime_cfg.get("disable", []))
    if isinstance(enable, list):
        for checker_name in enable:
            if isinstance(checker_name, str) and checker_name not in names:
                names.append(checker_name)
    names = [name for name in names if name not in disable]
    return names


def run_checkers(
    baseline: dict,
    candidate: dict,
    checker_names: list[str] | None = None,
    checker_config: dict | None = None,
) -> tuple[list[dict], list[str]]:
    config = checker_config or {}
    names = _resolve_checker_names(checker_names, config)
    config = checker_config or {}
    findings: list[dict] = []

    for name in names:
        checker = CHECKER_REGISTRY.get(name)
        if checker is None:
            raise ValueError(f"Unknown checker: {name}")
        findings.extend(checker(baseline, candidate, config))

    reasons: list[str] = []
    seen = set()
    for finding in findings:
        reason = finding.get("reason")
        if isinstance(reason, str) and reason not in seen:
            reasons.append(reason)
            seen.add(reason)

    return findings, reasons
