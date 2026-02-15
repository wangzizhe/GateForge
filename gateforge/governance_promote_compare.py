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


def _decision_score(decision: str | None) -> int:
    value = str(decision or "").upper()
    if value == "PASS":
        return 2
    if value == "NEEDS_REVIEW":
        return 1
    if value == "FAIL":
        return 0
    return -1


def _run_promote(snapshot: str, profile: str, out_path: str) -> tuple[int, dict]:
    cmd = [
        sys.executable,
        "-m",
        "gateforge.governance_promote",
        "--snapshot",
        snapshot,
        "--profile",
        profile,
        "--out",
        out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload = {}
    path = Path(out_path)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    return int(proc.returncode), payload


def _select_best_profile(results: list[dict], recommended_profile: str | None) -> tuple[str | None, str]:
    if not results:
        return None, "no_profiles"
    sorted_results = sorted(results, key=lambda x: (_decision_score(x.get("decision")), -int(x.get("exit_code", 99))), reverse=True)
    top_score = _decision_score(sorted_results[0].get("decision"))
    top = [r for r in sorted_results if _decision_score(r.get("decision")) == top_score]
    if recommended_profile:
        for row in top:
            if row.get("profile") == recommended_profile:
                return str(row.get("profile")), "recommended_profile_preferred_within_top_score"
    return str(top[0].get("profile")), "best_decision_score"


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Promote Compare",
        "",
        f"- status: `{summary.get('status')}`",
        f"- best_profile: `{summary.get('best_profile')}`",
        f"- best_reason: `{summary.get('best_reason')}`",
        f"- recommended_profile: `{summary.get('recommended_profile')}`",
        f"- recommended_profile_decision: `{summary.get('recommended_profile_decision')}`",
        f"- require_recommended_eligible: `{summary.get('require_recommended_eligible')}`",
        f"- constraint_reason: `{summary.get('constraint_reason')}`",
        "",
        "## Profile Results",
        "",
    ]
    for row in summary.get("profile_results", []):
        lines.append(
            f"- {row.get('profile')}: decision=`{row.get('decision')}` exit_code=`{row.get('exit_code')}` "
            f"is_recommended=`{row.get('is_recommended')}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare governance promote decisions across multiple profiles")
    parser.add_argument("--snapshot", required=True, help="Governance snapshot JSON path")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["default", "industrial_strict"],
        help="Promotion profiles to compare",
    )
    parser.add_argument(
        "--require-recommended-eligible",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When enabled, recommended profile must exist and not be FAIL",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/governance_promote_compare",
        help="Directory for per-profile outputs",
    )
    parser.add_argument("--out", default=None, help="Summary JSON path")
    parser.add_argument("--report", default=None, help="Summary markdown path")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_out = args.out or str(out_dir / "summary.json")
    report_out = args.report or _default_md_path(summary_out)

    snapshot_payload = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    kpis = snapshot_payload.get("kpis", {}) if isinstance(snapshot_payload.get("kpis"), dict) else {}
    recommended_profile = kpis.get("recommended_profile") if isinstance(kpis.get("recommended_profile"), str) else None

    results = []
    for profile in args.profiles:
        profile_out = out_dir / f"{profile}.json"
        exit_code, payload = _run_promote(args.snapshot, profile, str(profile_out))
        results.append(
            {
                "profile": profile,
                "decision": payload.get("decision"),
                "exit_code": exit_code,
                "out_path": str(profile_out),
                "is_recommended": bool(recommended_profile and profile == recommended_profile),
                "reasons": payload.get("reasons", []),
            }
        )

    best_profile, best_reason = _select_best_profile(results, recommended_profile)
    best_row = next((r for r in results if r.get("profile") == best_profile), None)
    best_decision = str(best_row.get("decision") if isinstance(best_row, dict) else "UNKNOWN")

    status = "PASS"
    if all(str(r.get("decision")).upper() == "FAIL" for r in results):
        status = "FAIL"
    elif best_decision.upper() == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"

    recommended_row = next((r for r in results if r.get("profile") == recommended_profile), None)
    recommended_decision = str(recommended_row.get("decision")) if isinstance(recommended_row, dict) else None
    constraint_reason = None
    if args.require_recommended_eligible and recommended_profile:
        if recommended_row is None:
            status = "FAIL"
            constraint_reason = "recommended_profile_not_in_profiles"
        elif str(recommended_decision).upper() == "FAIL":
            status = "FAIL"
            constraint_reason = "recommended_profile_failed"
        elif str(recommended_decision).upper() == "NEEDS_REVIEW" and status == "PASS":
            status = "NEEDS_REVIEW"
            constraint_reason = "recommended_profile_needs_review"

    summary = {
        "status": status,
        "snapshot_path": args.snapshot,
        "recommended_profile": recommended_profile,
        "recommended_profile_decision": recommended_decision,
        "require_recommended_eligible": bool(args.require_recommended_eligible),
        "constraint_reason": constraint_reason,
        "best_profile": best_profile,
        "best_decision": best_decision,
        "best_reason": best_reason,
        "profile_results": results,
    }
    _write_json(summary_out, summary)
    _write_markdown(report_out, summary)
    print(json.dumps({"status": status, "best_profile": best_profile, "best_decision": best_decision}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
