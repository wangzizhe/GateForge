from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PROMOTE_APPLY_POLICY_DIR = Path("policies/promote_apply")


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


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolve_policy_path(policy_path: str | None, policy_profile: str | None) -> str:
    if policy_path and policy_profile:
        raise ValueError("Use either --policy-path or --policy-profile, not both")
    if policy_profile:
        profile = policy_profile if policy_profile.endswith(".json") else f"{policy_profile}.json"
        resolved = PROMOTE_APPLY_POLICY_DIR / profile
        if not resolved.exists():
            raise ValueError(f"Promote-apply policy profile not found: {resolved}")
        return str(resolved)
    if policy_path:
        return policy_path
    return str(PROMOTE_APPLY_POLICY_DIR / "default.json")


def _build_changes(before: dict, after: dict) -> list[dict]:
    keys = sorted(set(before.keys()) | set(after.keys()))
    changes: list[dict] = []
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changes.append({"key": key, "old": old, "new": new})
    return changes


def _build_approval_recommendation(advice: dict, changes: list[dict]) -> dict:
    scorecard = advice.get("recommendation_scorecard") if isinstance(advice.get("recommendation_scorecard"), dict) else {}
    priority = str(scorecard.get("priority") or "normal")
    execution_risk = str(scorecard.get("execution_risk") or "low")
    impact = str(scorecard.get("impact") or "low")
    patch_keys = [str(row.get("key") or "") for row in changes if isinstance(row, dict)]
    needs_dual = (
        priority == "urgent"
        or execution_risk == "high"
        or impact == "high"
        or len(patch_keys) >= 2
        or "require_min_pairwise_net_margin" in patch_keys
    )
    profile = "dual_reviewer" if needs_dual else "default"
    rationale = (
        "High-impact or high-risk policy change; require dual reviewer approval."
        if needs_dual
        else "Low-risk policy change; default single-reviewer approval is acceptable."
    )
    return {
        "approval_profile": profile,
        "required_approvals": 2 if needs_dual else 1,
        "require_unique_reviewers": bool(needs_dual),
        "rationale": rationale,
    }


def _write_markdown(path: str, proposal: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Policy Patch Proposal",
        "",
        f"- proposal_id: `{proposal.get('proposal_id')}`",
        f"- source_advisor_path: `{proposal.get('source_advisor_path')}`",
        f"- target_policy_path: `{proposal.get('target_policy_path')}`",
        f"- target_policy_profile: `{proposal.get('target_policy_profile')}`",
        f"- before_hash: `{proposal.get('before_hash')}`",
        f"- after_hash: `{proposal.get('after_hash')}`",
        f"- change_count: `{proposal.get('change_count')}`",
        f"- requires_human_approval: `{proposal.get('requires_human_approval')}`",
        f"- recommended_approval_profile: `{(proposal.get('approval_recommendation') or {}).get('approval_profile')}`",
        "",
        "## Changes",
        "",
    ]
    changes = proposal.get("changes", [])
    if isinstance(changes, list) and changes:
        for row in changes:
            lines.append(f"- `{row.get('key')}`: `{row.get('old')}` -> `{row.get('new')}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create governance policy patch proposal from advisor output")
    parser.add_argument("--advisor-summary", required=True, help="Path to governance_policy_advisor summary JSON")
    parser.add_argument("--policy-path", default=None, help="Target policy path")
    parser.add_argument("--policy-profile", default=None, help="Target promote_apply profile name")
    parser.add_argument("--proposal-id", default=None, help="Optional proposal id")
    parser.add_argument("--out", default="artifacts/governance_policy_patch/proposal.json", help="Proposal JSON path")
    parser.add_argument("--report", default=None, help="Proposal markdown path")
    args = parser.parse_args()

    advisor = _load_json(args.advisor_summary)
    advice = advisor.get("advice", {}) if isinstance(advisor.get("advice"), dict) else {}
    patch = advice.get("threshold_patch", {}) if isinstance(advice.get("threshold_patch"), dict) else {}

    policy_path = _resolve_policy_path(args.policy_path, args.policy_profile)
    before_policy = _load_json(policy_path)
    after_policy = dict(before_policy)

    if "require_min_top_score_margin" in patch and patch.get("require_min_top_score_margin") is not None:
        after_policy["require_min_top_score_margin"] = int(patch["require_min_top_score_margin"])
    if "require_min_pairwise_net_margin" in patch and patch.get("require_min_pairwise_net_margin") is not None:
        after_policy["require_min_pairwise_net_margin"] = int(patch["require_min_pairwise_net_margin"])
    if "require_min_explanation_quality" in patch and patch.get("require_min_explanation_quality") is not None:
        after_policy["require_min_explanation_quality"] = int(patch["require_min_explanation_quality"])

    changes = _build_changes(before_policy, after_policy)
    recorded_at = datetime.now(timezone.utc).isoformat()
    proposal_id = args.proposal_id or f"policy-patch-{int(datetime.now(timezone.utc).timestamp())}"
    proposal = {
        "proposal_id": proposal_id,
        "recorded_at_utc": recorded_at,
        "source_advisor_path": args.advisor_summary,
        "target_policy_path": policy_path,
        "target_policy_profile": args.policy_profile,
        "advisor_suggested_policy_profile": advice.get("suggested_policy_profile"),
        "advisor_confidence": advice.get("confidence"),
        "advisor_reasons": advice.get("reasons", []),
        "advisor_why_now": advice.get("why_now", {}),
        "advisor_recommendation_scorecard": advice.get("recommendation_scorecard", {}),
        "before_hash": _stable_hash(before_policy),
        "after_hash": _stable_hash(after_policy),
        "change_count": len(changes),
        "changes": changes,
        "policy_before": before_policy,
        "policy_after": after_policy,
        "requires_human_approval": True,
        "approval_status": "PENDING",
        "approval_recommendation": _build_approval_recommendation(advice, changes),
    }
    _write_json(args.out, proposal)
    _write_markdown(args.report or _default_md_path(args.out), proposal)
    print(json.dumps({"proposal_id": proposal_id, "change_count": len(changes)}))


if __name__ == "__main__":
    main()
