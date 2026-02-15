from __future__ import annotations

import argparse
import json
import sys
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


def _append_jsonl(path: str, record: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Promote Apply",
        "",
        f"- final_status: `{summary.get('final_status')}`",
        f"- apply_action: `{summary.get('apply_action')}`",
        f"- actor: `{summary.get('actor')}`",
        f"- compare_status: `{summary.get('compare_status')}`",
        f"- best_profile: `{summary.get('best_profile')}`",
        f"- best_decision: `{summary.get('best_decision')}`",
        f"- recommended_profile: `{summary.get('recommended_profile')}`",
        f"- review_ticket_id: `{summary.get('review_ticket_id')}`",
        f"- audit_path: `{summary.get('audit_path')}`",
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


def _evaluate(compare_payload: dict, review_ticket_id: str | None) -> dict:
    compare_status = str(compare_payload.get("status") or "UNKNOWN").upper()
    best_profile = compare_payload.get("best_profile")
    best_decision = str(compare_payload.get("best_decision") or "UNKNOWN").upper()
    recommended_profile = compare_payload.get("recommended_profile")
    reasons: list[str] = []

    if compare_status == "FAIL":
        return {
            "final_status": "FAIL",
            "apply_action": "block",
            "reasons": ["compare_status_fail"],
            "compare_status": compare_status,
            "best_profile": best_profile,
            "best_decision": best_decision,
            "recommended_profile": recommended_profile,
        }

    if compare_status == "NEEDS_REVIEW":
        if not isinstance(review_ticket_id, str) or not review_ticket_id.strip():
            return {
                "final_status": "FAIL",
                "apply_action": "block",
                "reasons": ["needs_review_ticket_required"],
                "compare_status": compare_status,
                "best_profile": best_profile,
                "best_decision": best_decision,
                "recommended_profile": recommended_profile,
            }
        return {
            "final_status": "NEEDS_REVIEW",
            "apply_action": "hold_for_review",
            "reasons": [],
            "compare_status": compare_status,
            "best_profile": best_profile,
            "best_decision": best_decision,
            "recommended_profile": recommended_profile,
        }

    if compare_status == "PASS":
        if not isinstance(best_profile, str) or not best_profile.strip():
            reasons.append("best_profile_missing")
        if best_decision not in {"PASS", "NEEDS_REVIEW", "FAIL"}:
            reasons.append("best_decision_invalid")
        if reasons:
            return {
                "final_status": "FAIL",
                "apply_action": "block",
                "reasons": reasons,
                "compare_status": compare_status,
                "best_profile": best_profile,
                "best_decision": best_decision,
                "recommended_profile": recommended_profile,
            }
        return {
            "final_status": "PASS",
            "apply_action": "promote",
            "reasons": [],
            "compare_status": compare_status,
            "best_profile": best_profile,
            "best_decision": best_decision,
            "recommended_profile": recommended_profile,
        }

    return {
        "final_status": "FAIL",
        "apply_action": "block",
        "reasons": ["compare_status_unknown"],
        "compare_status": compare_status,
        "best_profile": best_profile,
        "best_decision": best_decision,
        "recommended_profile": recommended_profile,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply governance promotion decision from promote-compare summary")
    parser.add_argument("--compare-summary", required=True, help="Path to governance_promote_compare summary JSON")
    parser.add_argument("--review-ticket-id", default=None, help="Required when compare summary status is NEEDS_REVIEW")
    parser.add_argument("--actor", default="governance.bot", help="Actor identity for audit record")
    parser.add_argument("--out", default="artifacts/governance_promote_apply/summary.json", help="Output summary JSON")
    parser.add_argument("--report", default=None, help="Output markdown path")
    parser.add_argument(
        "--audit",
        default="artifacts/governance_promote_apply/decision_audit.jsonl",
        help="Append-only JSONL audit log path",
    )
    args = parser.parse_args()

    compare_payload = _load_json(args.compare_summary)
    evaluated = _evaluate(compare_payload, args.review_ticket_id)
    recorded_at = datetime.now(timezone.utc).isoformat()

    summary = {
        **evaluated,
        "actor": args.actor,
        "review_ticket_id": args.review_ticket_id,
        "compare_summary_path": args.compare_summary,
        "constraint_reason": compare_payload.get("constraint_reason"),
        "top_score_margin": compare_payload.get("top_score_margin"),
        "min_top_score_margin": compare_payload.get("min_top_score_margin"),
        "best_total_score": compare_payload.get("best_total_score"),
        "best_reason": compare_payload.get("best_reason"),
        "recorded_at_utc": recorded_at,
        "audit_path": args.audit,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)

    audit_record = {
        "recorded_at_utc": recorded_at,
        "actor": args.actor,
        "final_status": summary["final_status"],
        "apply_action": summary["apply_action"],
        "reasons": summary.get("reasons", []),
        "compare_summary_path": args.compare_summary,
        "compare_status": summary.get("compare_status"),
        "best_profile": summary.get("best_profile"),
        "best_decision": summary.get("best_decision"),
        "recommended_profile": summary.get("recommended_profile"),
        "review_ticket_id": summary.get("review_ticket_id"),
        "constraint_reason": summary.get("constraint_reason"),
        "top_score_margin": summary.get("top_score_margin"),
        "min_top_score_margin": summary.get("min_top_score_margin"),
    }
    _append_jsonl(args.audit, audit_record)

    print(
        json.dumps(
            {
                "final_status": summary["final_status"],
                "apply_action": summary["apply_action"],
                "best_profile": summary.get("best_profile"),
            }
        )
    )
    if summary["final_status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
