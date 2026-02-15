from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

PROMOTION_PROFILE_DIR = Path("policies/promotion")
DEFAULT_PROMOTION_PROFILE = "default"


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_utc(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _resolve_profile_path(profile: str | None, profile_path: str | None) -> str:
    if profile and profile_path:
        raise ValueError("Use either --profile or --profile-path, not both")
    if profile_path:
        return profile_path
    name = profile or DEFAULT_PROMOTION_PROFILE
    filename = name if name.endswith(".json") else f"{name}.json"
    resolved = PROMOTION_PROFILE_DIR / filename
    if not resolved.exists():
        raise ValueError(f"Promotion profile not found: {resolved}")
    return str(resolved)


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _evaluate(snapshot: dict, policy: dict) -> dict:
    status = str(snapshot.get("status") or "UNKNOWN")
    risks = [r for r in snapshot.get("risks", []) if isinstance(r, str)]
    kpis = snapshot.get("kpis", {}) if isinstance(snapshot.get("kpis"), dict) else {}

    fail_reasons: list[str] = []
    review_reasons: list[str] = []

    deny_statuses = {str(x) for x in policy.get("deny_statuses", []) if isinstance(x, str)}
    review_statuses = {str(x) for x in policy.get("review_statuses", []) if isinstance(x, str)}
    block_risks = {str(x) for x in policy.get("block_risks", []) if isinstance(x, str)}

    if status in deny_statuses:
        fail_reasons.append(f"status_denied:{status}")
    elif status in review_statuses:
        review_reasons.append(f"status_requires_review:{status}")

    for risk in risks:
        if risk in block_risks:
            fail_reasons.append(f"blocked_risk:{risk}")

    strict_non_pass_rate = _to_float(kpis.get("strict_non_pass_rate"), 0.0)
    strict_downgrade_rate = _to_float(kpis.get("strict_downgrade_rate"), 0.0)
    review_recovery_rate = _to_float(kpis.get("review_recovery_rate"), 1.0)
    fail_rate = _to_float(kpis.get("fail_rate"), 0.0)

    max_strict_non_pass_rate = policy.get("max_strict_non_pass_rate")
    if isinstance(max_strict_non_pass_rate, (int, float)) and strict_non_pass_rate > float(max_strict_non_pass_rate):
        review_reasons.append(
            f"strict_non_pass_rate_high:{strict_non_pass_rate:.4f}>{float(max_strict_non_pass_rate):.4f}"
        )

    max_strict_downgrade_rate = policy.get("max_strict_downgrade_rate")
    if isinstance(max_strict_downgrade_rate, (int, float)) and strict_downgrade_rate > float(max_strict_downgrade_rate):
        review_reasons.append(
            f"strict_downgrade_rate_high:{strict_downgrade_rate:.4f}>{float(max_strict_downgrade_rate):.4f}"
        )

    min_review_recovery_rate = policy.get("min_review_recovery_rate")
    if isinstance(min_review_recovery_rate, (int, float)) and review_recovery_rate < float(min_review_recovery_rate):
        review_reasons.append(
            f"review_recovery_rate_low:{review_recovery_rate:.4f}<{float(min_review_recovery_rate):.4f}"
        )

    max_fail_rate = policy.get("max_fail_rate")
    if isinstance(max_fail_rate, (int, float)) and fail_rate > float(max_fail_rate):
        review_reasons.append(f"fail_rate_high:{fail_rate:.4f}>{float(max_fail_rate):.4f}")

    requested_profile = str(policy.get("_requested_profile") or "")
    recommended_profile = str(kpis.get("recommended_profile") or "")
    mismatch_mode = str(policy.get("recommended_profile_mismatch_decision") or "ignore").lower()
    if mismatch_mode not in {"ignore", "review", "fail"}:
        mismatch_mode = "ignore"
    if requested_profile and recommended_profile and requested_profile != recommended_profile:
        mismatch_reason = f"recommended_profile_mismatch:requested={requested_profile},recommended={recommended_profile}"
        if mismatch_mode == "fail":
            fail_reasons.append(mismatch_reason)
        elif mismatch_mode == "review":
            review_reasons.append(mismatch_reason)

    if fail_reasons:
        decision = "FAIL"
        reasons = fail_reasons
    elif review_reasons:
        decision = "FAIL" if bool(policy.get("fail_on_needs_review", False)) else "NEEDS_REVIEW"
        reasons = review_reasons
    else:
        decision = "PASS"
        reasons = []

    return {
        "decision": decision,
        "status": status,
        "reasons": reasons,
        "fail_reasons": fail_reasons,
        "review_reasons": review_reasons,
        "signals": {
            "strict_non_pass_rate": strict_non_pass_rate,
            "strict_downgrade_rate": strict_downgrade_rate,
            "review_recovery_rate": review_recovery_rate,
            "fail_rate": fail_rate,
        },
    }


def _validate_override(override: dict) -> None:
    if not isinstance(override, dict):
        raise ValueError("Override must be a JSON object")
    forced = override.get("forced_decision")
    if forced is not None and forced not in {"PASS", "NEEDS_REVIEW", "FAIL"}:
        raise ValueError("override.forced_decision must be PASS|NEEDS_REVIEW|FAIL")
    allow_promote = override.get("allow_promote")
    if allow_promote is not None and not isinstance(allow_promote, bool):
        raise ValueError("override.allow_promote must be boolean")
    expires = override.get("expires_utc")
    if isinstance(expires, str) and _parse_utc(expires) is None:
        raise ValueError("override.expires_utc must be ISO-8601 UTC timestamp")


def _apply_override(result: dict, override: dict | None) -> dict:
    if not override:
        return {
            "override_applied": False,
            "override_active": False,
            "override_reason": None,
        }

    _validate_override(override)
    now = datetime.now(timezone.utc)
    expires_utc = override.get("expires_utc")
    expires_dt = _parse_utc(expires_utc) if isinstance(expires_utc, str) else None
    if expires_dt is not None and now > expires_dt:
        return {
            "override_applied": False,
            "override_active": False,
            "override_reason": "override_expired",
            "override_expires_utc": expires_utc,
        }

    forced = override.get("forced_decision")
    allow_promote = bool(override.get("allow_promote", False))
    reason = str(override.get("reason") or "override_applied")

    if isinstance(forced, str):
        result["decision"] = forced
        result["reasons"] = [f"override_forced_decision:{reason}"]
        return {
            "override_applied": True,
            "override_active": True,
            "override_reason": reason,
            "override_mode": "forced_decision",
            "override_expires_utc": expires_utc,
        }

    if allow_promote and result.get("decision") in {"FAIL", "NEEDS_REVIEW"}:
        result["decision"] = "PASS"
        result["reasons"] = [f"override_allow_promote:{reason}"]
        return {
            "override_applied": True,
            "override_active": True,
            "override_reason": reason,
            "override_mode": "allow_promote",
            "override_expires_utc": expires_utc,
        }

    return {
        "override_applied": False,
        "override_active": True,
        "override_reason": "override_present_no_effect",
        "override_expires_utc": expires_utc,
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Promote Decision",
        "",
        f"- decision: `{payload.get('decision')}`",
        f"- snapshot_status: `{payload.get('status')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- profile_path: `{payload.get('profile_path')}`",
        f"- override_applied: `{payload.get('override_applied')}`",
        f"- override_path: `{payload.get('override_path')}`",
        "",
        "## Signals",
        "",
    ]
    for key, value in payload.get("signals", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Reasons", ""])
    reasons = payload.get("reasons", [])
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Decide promotion readiness from governance snapshot")
    parser.add_argument("--snapshot", required=True, help="Governance snapshot JSON path")
    parser.add_argument("--profile", default=DEFAULT_PROMOTION_PROFILE, help="Promotion profile name")
    parser.add_argument("--profile-path", default=None, help="Promotion profile JSON path")
    parser.add_argument("--override", default=None, help="Optional human override JSON path")
    parser.add_argument("--out", default="artifacts/governance_promote/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    profile_path = _resolve_profile_path(args.profile, args.profile_path)
    policy = _load_json(profile_path)
    requested_profile = args.profile if not args.profile_path else Path(profile_path).stem
    policy["_requested_profile"] = requested_profile
    snapshot = _load_json(args.snapshot)
    result = _evaluate(snapshot, policy)
    override_payload = _load_json(args.override) if isinstance(args.override, str) else None
    override_meta = _apply_override(result, override_payload)
    result.update(
        {
            "snapshot_path": args.snapshot,
            "profile": args.profile,
            "profile_path": profile_path,
            "override_path": args.override,
            "override": override_payload,
            **override_meta,
        }
    )

    _write_json(args.out, result)
    _write_markdown(args.report or _default_md_path(args.out), result)
    print(json.dumps({"decision": result["decision"], "reasons": result["reasons"]}))
    if result["decision"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
