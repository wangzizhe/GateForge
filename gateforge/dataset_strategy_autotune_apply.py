from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_POLICY_DIR = Path("policies/dataset_strategy_apply")


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _resolve_policy_path(profile: str | None, policy_path: str | None) -> str:
    if profile and policy_path:
        raise ValueError("Use either --approval-profile or --approval-policy-path, not both")
    if policy_path:
        return policy_path
    if profile:
        p = profile if profile.endswith(".json") else f"{profile}.json"
        return str(APPROVAL_POLICY_DIR / p)
    return str(APPROVAL_POLICY_DIR / "default.json")


def _normalize_approvals(payload: dict) -> list[dict]:
    approvals = payload.get("approvals")
    if isinstance(approvals, list):
        rows = []
        for item in approvals:
            if isinstance(item, dict):
                rows.append(
                    {
                        "decision": str(item.get("decision") or "").lower(),
                        "reviewer": str(item.get("reviewer") or ""),
                    }
                )
        return rows
    decision = str(payload.get("decision") or "").lower()
    reviewer = str(payload.get("reviewer") or "")
    if decision:
        return [{"decision": decision, "reviewer": reviewer}]
    return []


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Dataset Strategy Auto-Tune Apply",
        "",
        f"- final_status: `{summary.get('final_status')}`",
        f"- apply_action: `{summary.get('apply_action')}`",
        f"- target_state_path: `{summary.get('target_state_path')}`",
        f"- suggested_policy_profile: `{summary.get('suggested_policy_profile')}`",
        f"- suggested_action: `{summary.get('suggested_action')}`",
        f"- confidence: `{summary.get('confidence')}`",
        f"- confidence_min_to_apply: `{summary.get('confidence_min_to_apply')}`",
        f"- approvals_count: `{summary.get('approvals_count')}`",
        f"- unique_reviewers_count: `{summary.get('unique_reviewers_count')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = summary.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        lines.extend([f"- `{r}`" for r in reasons])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply dataset strategy autotune advisor recommendation with approval")
    parser.add_argument("--advisor-summary", required=True, help="Path to dataset strategy autotune advisor summary JSON")
    parser.add_argument("--approval", default=None, help="Approval decision JSON path")
    parser.add_argument("--approval-profile", default=None, help="Approval policy profile under policies/dataset_strategy_apply")
    parser.add_argument("--approval-policy-path", default=None, help="Approval policy path override")
    parser.add_argument("--target-state", default="artifacts/dataset_strategy_autotune/active_strategy.json")
    parser.add_argument("--apply", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--out", default="artifacts/dataset_strategy_autotune/apply_summary.json")
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    advisor_payload = _load_json(args.advisor_summary)
    advice = advisor_payload.get("advice") if isinstance(advisor_payload.get("advice"), dict) else {}
    confidence = _to_float(advice.get("confidence"))
    suggested_profile = str(advice.get("suggested_policy_profile") or "")
    suggested_action = str(advice.get("suggested_action") or "")

    policy_path = _resolve_policy_path(args.approval_profile, args.approval_policy_path)
    policy_payload = _load_json(policy_path)
    required_approvals = int(policy_payload.get("required_approvals", 1))
    require_unique_reviewers = bool(policy_payload.get("require_unique_reviewers", True))
    confidence_min = _to_float(policy_payload.get("min_confidence_to_apply", 0.75))
    profile_name = str(policy_payload.get("profile") or Path(policy_path).stem)

    approval_payload = _load_json(args.approval) if args.approval else {}
    approvals = _normalize_approvals(approval_payload)
    decisions = [row.get("decision") or "" for row in approvals]
    unique_reviewers = {str(row.get("reviewer") or "").strip() for row in approvals if row.get("reviewer")}

    reasons: list[str] = []
    final_status = "NEEDS_REVIEW"
    apply_action = "hold"
    applied = False

    if not suggested_profile or not suggested_action:
        final_status = "FAIL"
        apply_action = "block"
        reasons.append("advisor_payload_missing_recommendation")
    elif confidence < confidence_min:
        reasons.append("advisor_confidence_below_apply_threshold")
    elif not args.approval:
        reasons.append("approval_required")
    elif any(d not in {"approve", "reject"} for d in decisions):
        final_status = "FAIL"
        apply_action = "block"
        reasons.append("approval_decision_invalid")
    elif any(d == "reject" for d in decisions):
        final_status = "FAIL"
        apply_action = "block"
        reasons.append("approval_rejected")
    elif len(approvals) < required_approvals:
        reasons.append("approval_count_insufficient")
    elif require_unique_reviewers and len(unique_reviewers) < required_approvals:
        reasons.append("approval_unique_reviewer_insufficient")
    elif not args.apply:
        reasons.append("approval_granted_apply_flag_required")
    else:
        state_payload = {
            "active_dataset_strategy_profile": suggested_profile,
            "active_dataset_strategy_action": suggested_action,
            "source": "dataset_strategy_autotune_apply",
            "source_advisor_summary": args.advisor_summary,
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(args.target_state, state_payload)
        final_status = "PASS"
        apply_action = "applied"
        applied = True

    summary = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "advisor_summary_path": args.advisor_summary,
        "approval_path": args.approval,
        "approval_profile": profile_name,
        "approval_policy_path": policy_path,
        "target_state_path": args.target_state,
        "suggested_policy_profile": suggested_profile,
        "suggested_action": suggested_action,
        "confidence": confidence,
        "confidence_min_to_apply": confidence_min,
        "required_approvals": required_approvals,
        "approvals_count": len(approvals),
        "unique_reviewers_count": len(unique_reviewers),
        "approval_decisions": decisions,
        "final_status": final_status,
        "apply_action": apply_action,
        "applied": applied,
        "reasons": reasons,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"final_status": final_status, "apply_action": apply_action, "suggested_policy_profile": suggested_profile}))
    if final_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
