from __future__ import annotations

from typing import Callable

CheckerFn = Callable[[dict, dict, dict], list[dict]]


def _make_finding(checker: str, reason: str, message: str, severity: str = "error") -> dict:
    return {
        "checker": checker,
        "reason": reason,
        "message": message,
        "severity": severity,
    }


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


BUILTIN_CHECKERS: dict[str, CheckerFn] = {
    "timeout": timeout_checker,
    "nan_inf": nan_inf_checker,
    "performance_regression": performance_regression_checker,
    "event_explosion": event_explosion_checker,
}


def available_checkers() -> list[str]:
    return sorted(BUILTIN_CHECKERS.keys())


def run_checkers(
    baseline: dict,
    candidate: dict,
    checker_names: list[str] | None = None,
    checker_config: dict | None = None,
) -> tuple[list[dict], list[str]]:
    names = checker_names or available_checkers()
    config = checker_config or {}
    findings: list[dict] = []

    for name in names:
        checker = BUILTIN_CHECKERS.get(name)
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
