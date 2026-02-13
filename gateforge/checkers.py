from __future__ import annotations

from typing import Callable

CheckerFn = Callable[[dict, dict], list[dict]]


def _make_finding(checker: str, reason: str, message: str, severity: str = "error") -> dict:
    return {
        "checker": checker,
        "reason": reason,
        "message": message,
        "severity": severity,
    }


def timeout_checker(_baseline: dict, candidate: dict) -> list[dict]:
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


def nan_inf_checker(_baseline: dict, candidate: dict) -> list[dict]:
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


BUILTIN_CHECKERS: dict[str, CheckerFn] = {
    "timeout": timeout_checker,
    "nan_inf": nan_inf_checker,
}


def available_checkers() -> list[str]:
    return sorted(BUILTIN_CHECKERS.keys())


def run_checkers(
    baseline: dict,
    candidate: dict,
    checker_names: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    names = checker_names or available_checkers()
    findings: list[dict] = []

    for name in names:
        checker = BUILTIN_CHECKERS.get(name)
        if checker is None:
            raise ValueError(f"Unknown checker: {name}")
        findings.extend(checker(baseline, candidate))

    reasons: list[str] = []
    seen = set()
    for finding in findings:
        reason = finding.get("reason")
        if isinstance(reason, str) and reason not in seen:
            reasons.append(reason)
            seen.add(reason)

    return findings, reasons

