from __future__ import annotations


def validate_demo_bundle_summary(payload: dict) -> None:
    required = {
        "flow_exit_code",
        "checker_exit_code",
        "proposal_flow_status",
        "checker_demo_status",
        "checker_demo_policy_decision",
        "result_flags",
        "artifacts",
        "checksums",
        "bundle_status",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required demo bundle summary keys: {missing}")

    if not isinstance(payload["flow_exit_code"], int):
        raise ValueError("flow_exit_code must be integer")
    if not isinstance(payload["checker_exit_code"], int):
        raise ValueError("checker_exit_code must be integer")

    _require_enum(payload, "proposal_flow_status", {"PASS", "FAIL", "NEEDS_REVIEW"})
    _require_enum(payload, "checker_demo_status", {"PASS", "FAIL", "NEEDS_REVIEW"})
    _require_enum(payload, "checker_demo_policy_decision", {"PASS", "FAIL", "NEEDS_REVIEW"})
    _require_enum(payload, "bundle_status", {"PASS", "FAIL"})

    result_flags = payload["result_flags"]
    if not isinstance(result_flags, dict):
        raise ValueError("result_flags must be object")
    _require_flag_enum(result_flags, "proposal_flow")
    _require_flag_enum(result_flags, "checker_demo_expected_fail")

    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("artifacts must be non-empty array")
    for artifact in artifacts:
        if not isinstance(artifact, str) or not artifact.strip():
            raise ValueError("artifacts entries must be non-empty strings")

    checksums = payload["checksums"]
    if not isinstance(checksums, dict):
        raise ValueError("checksums must be object")
    for artifact in artifacts:
        digest = checksums.get(artifact)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"checksums[{artifact}] must be 64-char sha256 hex")
        if any(c not in "0123456789abcdef" for c in digest.lower()):
            raise ValueError(f"checksums[{artifact}] must be lowercase hex")


def _require_enum(payload: dict, key: str, allowed: set[str]) -> None:
    value = payload.get(key)
    if value not in allowed:
        raise ValueError(f"{key} must be one of {sorted(allowed)}")


def _require_flag_enum(flags: dict, key: str) -> None:
    value = flags.get(key)
    if value not in {"PASS", "FAIL"}:
        raise ValueError(f"result_flags.{key} must be PASS/FAIL")
