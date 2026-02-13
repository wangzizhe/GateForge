from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .review import load_review_decision, validate_review_decision


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Human Review Resolution",
        "",
        f"- proposal_id: `{summary.get('proposal_id')}`",
        f"- source_status: `{summary.get('source_status')}`",
        f"- source_policy_decision: `{summary.get('source_policy_decision')}`",
        f"- final_status: `{summary.get('final_status')}`",
        f"- review_id: `{summary.get('review_id')}`",
        f"- reviewer: `{summary.get('reviewer')}`",
        f"- human_decision: `{summary.get('human_decision')}`",
        f"- all_required_checks_completed: `{summary.get('all_required_checks_completed')}`",
        "",
        "## Final Reasons",
        "",
    ]
    reasons = summary.get("final_reasons", [])
    if reasons:
        lines.extend([f"- `{reason}`" for reason in reasons])
    else:
        lines.append("- `none`")

    lines.extend(["", "## Unresolved Required Checks", ""])
    unresolved = summary.get("unresolved_required_human_checks", [])
    if unresolved:
        lines.extend([f"- {item}" for item in unresolved])
    else:
        lines.append("- `none`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _load_source_summary(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("run_path"):
        run_path = payload.get("run_path")
        run_file = Path(run_path)
        if run_file.exists():
            return json.loads(run_file.read_text(encoding="utf-8"))
    return payload


def _resolve(source: dict, review: dict) -> dict:
    proposal_id = source.get("proposal_id")
    source_status = source.get("status")
    source_policy_decision = source.get("policy_decision")
    required_checks = source.get("required_human_checks", [])
    if not isinstance(required_checks, list):
        required_checks = []

    summary = {
        "proposal_id": proposal_id,
        "source_status": source_status,
        "source_policy_decision": source_policy_decision,
        "review_id": review.get("review_id"),
        "reviewer": review.get("reviewer"),
        "human_decision": review.get("decision"),
        "all_required_checks_completed": review.get("all_required_checks_completed"),
        "source_required_human_checks": required_checks,
        "final_status": "FAIL",
        "final_reasons": [],
        "unresolved_required_human_checks": [],
    }

    if review.get("proposal_id") != proposal_id:
        summary["final_reasons"].append("review_proposal_id_mismatch")
        summary["final_status"] = "FAIL"
        return summary

    decision = review["decision"]

    # If source is already final, keep it unless reviewer explicitly rejects.
    if source_status in {"PASS", "FAIL"}:
        if decision == "reject":
            summary["final_status"] = "FAIL"
            summary["final_reasons"].append("human_rejected")
        else:
            summary["final_status"] = source_status
            if source_status == "FAIL":
                summary["final_reasons"].append("source_already_fail")
        return summary

    if source_status != "NEEDS_REVIEW":
        summary["final_status"] = "FAIL"
        summary["final_reasons"].append("source_not_reviewable")
        return summary

    if decision == "reject":
        summary["final_status"] = "FAIL"
        summary["final_reasons"].append("human_rejected")
        return summary

    if not review.get("all_required_checks_completed"):
        summary["final_status"] = "FAIL"
        summary["final_reasons"].append("required_human_checks_not_completed")
        summary["unresolved_required_human_checks"] = required_checks
        return summary

    summary["final_status"] = "PASS"
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve NEEDS_REVIEW into final PASS/FAIL using human decision")
    parser.add_argument("--summary", required=True, help="Path to run/autopilot summary JSON")
    parser.add_argument("--review", required=True, help="Path to human review decision JSON")
    parser.add_argument("--out", default="artifacts/review/final_summary.json", help="Where to write resolution summary")
    parser.add_argument("--report", default=None, help="Where to write markdown report")
    args = parser.parse_args()

    source = _load_source_summary(args.summary)
    review = load_review_decision(args.review)
    validate_review_decision(review)

    resolved = _resolve(source=source, review=review)
    _write_json(args.out, resolved)
    _write_markdown(args.report or _default_md_path(args.out), resolved)

    print(json.dumps({"proposal_id": resolved.get("proposal_id"), "final_status": resolved["final_status"]}))
    if resolved["final_status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
