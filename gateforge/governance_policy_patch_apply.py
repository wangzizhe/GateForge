from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_PROFILE_DIR = Path("policies/patch_apply")


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


def _resolve_approval_policy_path(profile: str | None, policy_path: str | None) -> str:
    if profile and policy_path:
        raise ValueError("Use either --approval-profile or --approval-policy-path, not both")
    if policy_path:
        return policy_path
    if profile:
        p = profile if profile.endswith(".json") else f"{profile}.json"
        return str(APPROVAL_PROFILE_DIR / p)
    return str(APPROVAL_PROFILE_DIR / "default.json")


def _normalize_approvals(approval_payload: dict) -> list[dict]:
    approvals = approval_payload.get("approvals")
    if isinstance(approvals, list):
        out = []
        for row in approvals:
            if isinstance(row, dict):
                out.append(
                    {
                        "decision": str(row.get("decision") or "").lower(),
                        "reviewer": row.get("reviewer"),
                    }
                )
        return out
    decision = str(approval_payload.get("decision") or "").lower()
    reviewer = approval_payload.get("reviewer")
    if decision:
        return [{"decision": decision, "reviewer": reviewer}]
    return []


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Policy Patch Apply",
        "",
        f"- proposal_id: `{summary.get('proposal_id')}`",
        f"- final_status: `{summary.get('final_status')}`",
        f"- apply_action: `{summary.get('apply_action')}`",
        f"- target_policy_path: `{summary.get('target_policy_path')}`",
        f"- applied: `{summary.get('applied')}`",
        f"- approval_profile: `{summary.get('approval_profile')}`",
        f"- approval_policy_path: `{summary.get('approval_policy_path')}`",
        f"- approvals_count: `{summary.get('approvals_count')}`",
        f"- unique_reviewers_count: `{summary.get('unique_reviewers_count')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = summary.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Impact Preview", ""])
    preview = summary.get("impact_preview", [])
    if isinstance(preview, list) and preview:
        for row in preview:
            if isinstance(row, dict):
                lines.append(
                    f"- `{row.get('key')}`: `{row.get('old')}` -> `{row.get('new')}` "
                    f"(scope=`{row.get('scope')}`, expected_effect=`{row.get('expected_effect')}`, "
                    f"affected_checks=`{','.join(row.get('affected_checks') or [])}`)"
                )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _build_impact_preview(changes: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for row in changes:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "")
        scope = "governance"
        expected_effect = "policy_behavior_change"
        if key == "require_min_top_score_margin":
            expected_effect = "stricter_compare_margin_gate"
            affected_checks = ["governance_promote_compare.top_score_margin"]
        elif key == "require_min_pairwise_net_margin":
            expected_effect = "stricter_pairwise_stability_gate"
            affected_checks = ["governance_promote_apply.pairwise_net_margin"]
        elif key == "require_min_explanation_quality":
            expected_effect = "stricter_explanation_quality_gate"
            affected_checks = ["governance_promote_compare.explanation_completeness"]
        else:
            affected_checks = ["policy_generic"]
        rows.append(
            {
                "key": key,
                "old": row.get("old"),
                "new": row.get("new"),
                "scope": scope,
                "expected_effect": expected_effect,
                "affected_checks": affected_checks,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply policy patch proposal with human approval gate")
    parser.add_argument("--proposal", required=True, help="Policy patch proposal JSON path")
    parser.add_argument("--approval", default=None, help="Approval decision JSON path")
    parser.add_argument(
        "--approval-profile",
        default=None,
        help="Approval profile name under policies/patch_apply (e.g. default, dual_reviewer)",
    )
    parser.add_argument("--approval-policy-path", default=None, help="Approval policy JSON path override")
    parser.add_argument(
        "--apply",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled and approval is approve, write policy_after to target policy path",
    )
    parser.add_argument(
        "--preview-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Generate impact preview only; do not evaluate approvals or write policy",
    )
    parser.add_argument("--out", default="artifacts/governance_policy_patch/apply.json", help="Apply summary JSON path")
    parser.add_argument("--report", default=None, help="Apply summary markdown path")
    args = parser.parse_args()

    proposal = _load_json(args.proposal)
    impact_preview = _build_impact_preview(proposal.get("changes") if isinstance(proposal.get("changes"), list) else [])
    approval_policy_path = _resolve_approval_policy_path(args.approval_profile, args.approval_policy_path)
    approval_policy = _load_json(approval_policy_path)
    required_approvals = int(approval_policy.get("required_approvals", 1))
    require_unique_reviewers = bool(approval_policy.get("require_unique_reviewers", True))
    allow_reject_short_circuit = bool(approval_policy.get("allow_reject_short_circuit", True))
    profile_name = str(
        approval_policy.get("profile")
        or args.approval_profile
        or Path(approval_policy_path).stem
    )

    reasons: list[str] = []
    final_status = "NEEDS_REVIEW"
    apply_action = "hold"
    applied = False
    approval = _load_json(args.approval) if args.approval else {}
    normalized_approvals = _normalize_approvals(approval)
    approvals_count = len(normalized_approvals)
    unique_reviewers = {str(x.get("reviewer") or "").strip() for x in normalized_approvals if x.get("reviewer")}
    unique_reviewers_count = len(unique_reviewers)
    decisions = [str(x.get("decision") or "").lower() for x in normalized_approvals]

    target_policy_path = str(proposal.get("target_policy_path") or "")
    if args.preview_only:
        final_status = "PREVIEW"
        apply_action = "preview_only"
        reasons.append("preview_only_no_apply")
    elif not target_policy_path:
        final_status = "FAIL"
        apply_action = "block"
        reasons.append("target_policy_path_missing")
    elif not args.approval:
        reasons.append("approval_required")
    elif any(d not in {"approve", "reject"} for d in decisions):
        reasons.append("approval_decision_invalid")
    elif allow_reject_short_circuit and any(d == "reject" for d in decisions):
        final_status = "FAIL"
        apply_action = "block"
        reasons.append("approval_rejected")
    elif approvals_count < required_approvals:
        reasons.append("approval_count_insufficient")
    elif require_unique_reviewers and unique_reviewers_count < required_approvals:
        reasons.append("approval_unique_reviewer_insufficient")
    elif not args.apply:
        reasons.append("approval_granted_apply_flag_required")
    else:
        policy_after = proposal.get("policy_after")
        if not isinstance(policy_after, dict):
            final_status = "FAIL"
            apply_action = "block"
            reasons.append("policy_after_missing")
        else:
            Path(target_policy_path).write_text(json.dumps(policy_after, indent=2), encoding="utf-8")
            final_status = "PASS"
            apply_action = "applied"
            applied = True

    summary = {
        "proposal_id": proposal.get("proposal_id"),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "proposal_path": args.proposal,
        "approval_path": args.approval,
        "approval_profile": profile_name,
        "approval_policy_path": approval_policy_path,
        "approval_policy_required_approvals": required_approvals,
        "approval_policy_require_unique_reviewers": require_unique_reviewers,
        "approval_decisions": decisions,
        "approval_reviewers": sorted(unique_reviewers),
        "approvals_count": approvals_count,
        "unique_reviewers_count": unique_reviewers_count,
        "target_policy_path": target_policy_path,
        "final_status": final_status,
        "apply_action": apply_action,
        "applied": applied,
        "reasons": reasons,
        "impact_preview": impact_preview,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"proposal_id": summary.get("proposal_id"), "final_status": final_status, "applied": applied}))
    if final_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
