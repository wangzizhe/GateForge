from __future__ import annotations

import json
from pathlib import Path

DEFAULT_POLICY_PATH = "policies/default_policy.json"
PROFILE_DIR = Path("policies/profiles")


def load_policy(path: str = DEFAULT_POLICY_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_policy_path(policy_path: str | None = None, policy_profile: str | None = None) -> str:
    if policy_path and policy_profile:
        raise ValueError("Use either policy_path or policy_profile, not both")
    if policy_profile:
        profile_name = policy_profile if policy_profile.endswith(".json") else f"{policy_profile}.json"
        resolved = PROFILE_DIR / profile_name
        if not resolved.exists():
            raise ValueError(f"Policy profile not found: {resolved}")
        return str(resolved)
    if policy_path:
        return policy_path
    return DEFAULT_POLICY_PATH


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


def run_required_human_checks(
    policy: dict,
    policy_decision: str,
    policy_reasons: list[str],
    candidate_failure_type: str | None,
) -> list[str]:
    if policy_decision == "PASS":
        return []

    templates = policy.get("required_human_checks", {})
    if not isinstance(templates, dict):
        templates = {}

    by_reason_prefix = templates.get("by_reason_prefix", {})
    if not isinstance(by_reason_prefix, dict):
        by_reason_prefix = {}

    by_failure_type = templates.get("by_failure_type", {})
    if not isinstance(by_failure_type, dict):
        by_failure_type = {}

    fallback = _as_str_list(
        templates.get(
            "fallback",
            ["Human review required: inspect policy_reasons and evidence artifacts before merge."],
        )
    )

    checks: list[str] = []
    for reason in policy_reasons:
        for prefix, items in by_reason_prefix.items():
            if reason.startswith(prefix):
                checks.extend(_as_str_list(items))

    if candidate_failure_type and candidate_failure_type in by_failure_type:
        checks.extend(_as_str_list(by_failure_type[candidate_failure_type]))

    if not checks:
        checks.extend(fallback)

    dedup: list[str] = []
    for item in checks:
        if item not in dedup:
            dedup.append(item)
    return dedup


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
