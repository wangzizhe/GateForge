from __future__ import annotations

import json
from pathlib import Path

DEFAULT_POLICY_PATH = "policies/default_policy.json"


def load_policy(path: str = DEFAULT_POLICY_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_policy(reasons: list[str], risk_level: str, policy: dict) -> dict:
    critical_prefixes = tuple(policy.get("critical_reason_prefixes", []))
    review_prefixes = tuple(policy.get("needs_review_reason_prefixes", []))
    fail_on_review_risks = set(policy.get("fail_on_needs_review_risk_levels", []))
    fail_on_unknown = bool(policy.get("fail_on_unknown_reasons", True))

    critical: list[str] = []
    review: list[str] = []
    unknown: list[str] = []

    for reason in reasons:
        if _matches_any_prefix(reason, critical_prefixes):
            critical.append(reason)
        elif _matches_any_prefix(reason, review_prefixes):
            review.append(reason)
        else:
            unknown.append(reason)

    if not reasons:
        return {
            "policy_decision": "PASS",
            "policy_reasons": [],
            "critical_reasons": [],
            "review_reasons": [],
            "unknown_reasons": [],
        }

    if critical:
        return {
            "policy_decision": "FAIL",
            "policy_reasons": critical,
            "critical_reasons": critical,
            "review_reasons": review,
            "unknown_reasons": unknown,
        }

    if unknown and fail_on_unknown:
        return {
            "policy_decision": "FAIL",
            "policy_reasons": unknown,
            "critical_reasons": critical,
            "review_reasons": review,
            "unknown_reasons": unknown,
        }

    if review:
        if risk_level in fail_on_review_risks:
            return {
                "policy_decision": "FAIL",
                "policy_reasons": review,
                "critical_reasons": critical,
                "review_reasons": review,
                "unknown_reasons": unknown,
            }
        return {
            "policy_decision": "NEEDS_REVIEW",
            "policy_reasons": review,
            "critical_reasons": critical,
            "review_reasons": review,
            "unknown_reasons": unknown,
        }

    return {
        "policy_decision": "PASS",
        "policy_reasons": [],
        "critical_reasons": critical,
        "review_reasons": review,
        "unknown_reasons": unknown,
    }


def dry_run_human_checks(policy: dict, risk_level: str, has_change_set: bool) -> list[str]:
    templates = policy.get("dry_run_human_checks", {})
    if not isinstance(templates, dict):
        templates = {}

    checks = _as_str_list(
        templates.get(
            "base",
            [
                "Confirm proposal backend/model_script mapping before execution.",
                "Review baseline selection strategy (auto/index or explicit path).",
            ],
        )
    )

    normalized_risk = risk_level if risk_level in {"low", "medium", "high"} else "low"
    if normalized_risk in {"medium", "high"}:
        checks.extend(
            _as_str_list(
                templates.get(
                    "medium_extra",
                    ["Confirm regression thresholds and checker_config reflect intended risk posture."],
                )
            )
        )
    if normalized_risk == "high":
        checks.extend(
            _as_str_list(
                templates.get(
                    "high_extra",
                    ["Pre-approve rollback path if gate returns FAIL after candidate execution."],
                )
            )
        )
    if has_change_set:
        checks.extend(
            _as_str_list(
                templates.get(
                    "changeset_extra",
                    ["Review change-set diff against target files before execution."],
                )
            )
        )

    # Keep order stable but deduplicate.
    dedup: list[str] = []
    for item in checks:
        if item not in dedup:
            dedup.append(item)
    return dedup


def _matches_any_prefix(reason: str, prefixes: tuple[str, ...]) -> bool:
    return any(reason.startswith(prefix) for prefix in prefixes)


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item)
    return out
