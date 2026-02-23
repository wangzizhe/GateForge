from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


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
        f"- approval_decision: `{summary.get('approval_decision')}`",
        f"- approval_reviewer: `{summary.get('approval_reviewer')}`",
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
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply policy patch proposal with human approval gate")
    parser.add_argument("--proposal", required=True, help="Policy patch proposal JSON path")
    parser.add_argument("--approval", default=None, help="Approval decision JSON path")
    parser.add_argument(
        "--apply",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled and approval is approve, write policy_after to target policy path",
    )
    parser.add_argument("--out", default="artifacts/governance_policy_patch/apply.json", help="Apply summary JSON path")
    parser.add_argument("--report", default=None, help="Apply summary markdown path")
    args = parser.parse_args()

    proposal = _load_json(args.proposal)
    reasons: list[str] = []
    final_status = "NEEDS_REVIEW"
    apply_action = "hold"
    applied = False
    approval = _load_json(args.approval) if args.approval else {}
    decision = str(approval.get("decision") or "").lower()
    reviewer = approval.get("reviewer")

    target_policy_path = str(proposal.get("target_policy_path") or "")
    if not target_policy_path:
        final_status = "FAIL"
        apply_action = "block"
        reasons.append("target_policy_path_missing")
    elif not args.approval:
        reasons.append("approval_required")
    elif decision not in {"approve", "reject"}:
        reasons.append("approval_decision_invalid")
    elif decision == "reject":
        final_status = "FAIL"
        apply_action = "block"
        reasons.append("approval_rejected")
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
        "approval_decision": decision or None,
        "approval_reviewer": reviewer,
        "target_policy_path": target_policy_path,
        "final_status": final_status,
        "apply_action": apply_action,
        "applied": applied,
        "reasons": reasons,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"proposal_id": summary.get("proposal_id"), "final_status": final_status, "applied": applied}))
    if final_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
