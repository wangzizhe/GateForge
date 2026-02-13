from __future__ import annotations

import json
from pathlib import Path

REVIEW_SCHEMA_VERSION = "0.1.0"
SUPPORTED_DECISIONS = {"approve", "reject"}


def load_review_decision(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_review_decision(payload: dict) -> None:
    required = {
        "schema_version",
        "review_id",
        "proposal_id",
        "reviewer",
        "decision",
        "rationale",
        "all_required_checks_completed",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required review decision keys: {missing}")

    if payload["schema_version"] != REVIEW_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {REVIEW_SCHEMA_VERSION}")

    _require_non_empty_string(payload, "review_id")
    _require_non_empty_string(payload, "proposal_id")
    _require_non_empty_string(payload, "reviewer")
    _require_non_empty_string(payload, "rationale")

    decision = payload["decision"]
    if decision not in SUPPORTED_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(SUPPORTED_DECISIONS)}")

    if not isinstance(payload["all_required_checks_completed"], bool):
        raise ValueError("all_required_checks_completed must be a boolean")

    confirmed_checks = payload.get("confirmed_checks")
    if confirmed_checks is not None:
        if not isinstance(confirmed_checks, list):
            raise ValueError("confirmed_checks must be a list when provided")
        for idx, item in enumerate(confirmed_checks):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"confirmed_checks[{idx}] must be a non-empty string")

    second_reviewer = payload.get("second_reviewer")
    if second_reviewer is not None and (not isinstance(second_reviewer, str) or not second_reviewer.strip()):
        raise ValueError("second_reviewer must be a non-empty string when provided")

    second_decision = payload.get("second_decision")
    if second_decision is not None and second_decision not in SUPPORTED_DECISIONS:
        raise ValueError(f"second_decision must be one of {sorted(SUPPORTED_DECISIONS)} when provided")


def _require_non_empty_string(payload: dict, key: str) -> None:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
