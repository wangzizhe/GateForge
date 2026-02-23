from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def _decision_score(value: str | None) -> int:
    status = str(value or "UNKNOWN").upper()
    if status == "PASS":
        return 2
    if status == "NEEDS_REVIEW":
        return 1
    if status == "FAIL":
        return 0
    return -1


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def _select_best(rows: list[dict], recommended_profile: str | None) -> tuple[str | None, str]:
    if not rows:
        return None, "no_profiles"
    ranked = sorted(
        rows,
        key=lambda row: (
            int(row.get("decision_score", -1)),
            -int(row.get("reason_count", 999)),
            -int(row.get("exit_code", 99)),
        ),
        reverse=True,
    )
    top = ranked[0]
    top_score = int(top.get("decision_score", -1))
    tied = [row for row in ranked if int(row.get("decision_score", -1)) == top_score]
    if isinstance(recommended_profile, str) and recommended_profile:
        for row in tied:
            if row.get("profile") == recommended_profile:
                return str(row.get("profile")), "recommended_profile_tiebreak"
    return str(top.get("profile")), "highest_decision_score"


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Replay Compare",
        "",
        f"- status: `{summary.get('status')}`",
        f"- best_profile: `{summary.get('best_profile')}`",
        f"- best_reason: `{summary.get('best_reason')}`",
        f"- recommended_profile: `{summary.get('recommended_profile')}`",
        f"- strict: `{summary.get('strict')}`",
        "",
        "## Profiles",
        "",
    ]
    rows = summary.get("profile_results", [])
    if isinstance(rows, list) and rows:
        for row in rows:
            lines.append(
                f"- profile=`{row.get('profile')}` final_status=`{row.get('final_status')}` "
                f"decision_score=`{row.get('decision_score')}` reason_count=`{row.get('reason_count')}` "
                f"exit_code=`{row.get('exit_code')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare replay/apply stability across governance policy profiles")
    parser.add_argument("--compare-summary", required=True, help="Source governance_promote_compare summary JSON")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["default", "industrial_strict"],
        help="Policy profiles to compare",
    )
    parser.add_argument("--review-ticket-id", default=None, help="Optional review ticket for NEEDS_REVIEW flows")
    parser.add_argument("--actor", default="governance.bot", help="Actor identity")
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled, any FAIL profile makes compare status FAIL",
    )
    parser.add_argument("--out-dir", default="artifacts/governance_replay_compare", help="Per-profile output directory")
    parser.add_argument("--out", default=None, help="Summary output JSON path")
    parser.add_argument("--report", default=None, help="Summary markdown path")
    args = parser.parse_args()

    compare_payload = json.loads(Path(args.compare_summary).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_out = args.out or str(out_dir / "summary.json")
    report_out = args.report or _default_md_path(summary_out)

    rows: list[dict] = []
    for profile in args.profiles:
        profile_out = out_dir / f"apply_{profile}.json"
        cmd = [
            sys.executable,
            "-m",
            "gateforge.governance_promote_apply",
            "--compare-summary",
            args.compare_summary,
            "--policy-profile",
            str(profile),
            "--actor",
            str(args.actor),
            "--out",
            str(profile_out),
        ]
        if args.review_ticket_id:
            cmd.extend(["--review-ticket-id", str(args.review_ticket_id)])
        rc, _, _ = _run(cmd)
        payload = json.loads(profile_out.read_text(encoding="utf-8")) if profile_out.exists() else {}
        reasons = payload.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = []
        row = {
            "profile": profile,
            "final_status": payload.get("final_status"),
            "apply_action": payload.get("apply_action"),
            "decision_score": _decision_score(payload.get("final_status")),
            "reason_count": len(reasons),
            "reasons": [str(r) for r in reasons if isinstance(r, str)],
            "exit_code": rc,
            "out_path": str(profile_out),
            "policy_hash": payload.get("policy_hash"),
            "effective_guardrails_hash": payload.get("effective_guardrails_hash"),
        }
        rows.append(row)

    recommended_profile = compare_payload.get("recommended_profile") if isinstance(
        compare_payload.get("recommended_profile"), str
    ) else None
    best_profile, best_reason = _select_best(rows, recommended_profile)
    status = "PASS"
    if any(str(row.get("final_status")).upper() == "FAIL" for row in rows):
        status = "FAIL" if args.strict else "NEEDS_REVIEW"
    elif any(str(row.get("final_status")).upper() == "NEEDS_REVIEW" for row in rows):
        status = "NEEDS_REVIEW"

    summary = {
        "status": status,
        "strict": bool(args.strict),
        "compare_summary_path": args.compare_summary,
        "recommended_profile": recommended_profile,
        "best_profile": best_profile,
        "best_reason": best_reason,
        "profile_results": rows,
    }
    _write_json(summary_out, summary)
    _write_markdown(report_out, summary)
    print(json.dumps({"status": status, "best_profile": best_profile}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
