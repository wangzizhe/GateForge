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


def _status_score(status: str | None) -> int:
    value = str(status or "").upper()
    if value == "PASS":
        return 2
    if value == "NEEDS_REVIEW":
        return 1
    if value == "FAIL":
        return 0
    return -1


def _delta_score(delta: str | None) -> int:
    value = str(delta or "").lower()
    if value == "improved":
        return 2
    if value == "unchanged":
        return 1
    if value == "worse":
        return -1
    return 0


def _run_profile(*, profile: str, args: argparse.Namespace, out_json: str, out_md: str) -> tuple[int, dict]:
    cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_loop",
        "--source",
        args.source,
        "--planner-backend",
        args.planner_backend,
        "--invariant-repair-profile",
        profile,
        "--baseline",
        args.baseline,
        "--baseline-index",
        args.baseline_index,
        "--runtime-threshold",
        str(args.runtime_threshold),
        "--out",
        out_json,
        "--report",
        out_md,
    ]
    if args.policy:
        cmd.extend(["--policy", args.policy])
    if args.policy_profile:
        cmd.extend(["--policy-profile", args.policy_profile])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload = {}
    p = Path(out_json)
    if p.exists():
        payload = json.loads(p.read_text(encoding="utf-8"))
    return int(proc.returncode), payload


def _score_row(row: dict, args: argparse.Namespace) -> dict:
    status_component = _status_score(row.get("status")) * int(args.score_status_weight)
    delta_component = _delta_score(row.get("delta")) * int(args.score_delta_weight)
    reason_component = -(int(row.get("reasons_count", 0)) * abs(int(args.score_reason_penalty)))
    safety_component = -abs(int(args.score_safety_penalty)) if row.get("safety_guard_triggered") else 0
    strictness_component = int(round(float(row.get("planner_change_plan_confidence_min", 0.0)) * int(args.score_strictness_scale)))
    total_score = status_component + delta_component + reason_component + safety_component + strictness_component
    return {
        "status_component": status_component,
        "delta_component": delta_component,
        "reason_component": reason_component,
        "safety_component": safety_component,
        "strictness_component": strictness_component,
        "total_score": total_score,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Invariant Repair Compare",
        "",
        f"- status: `{summary.get('status')}`",
        f"- best_profile: `{summary.get('best_profile')}`",
        f"- best_reason: `{summary.get('best_reason')}`",
        f"- best_total_score: `{summary.get('best_total_score')}`",
        "",
        "## Scoring",
        "",
        f"- score_status_weight: `{summary.get('scoring', {}).get('score_status_weight')}`",
        f"- score_delta_weight: `{summary.get('scoring', {}).get('score_delta_weight')}`",
        f"- score_reason_penalty: `{summary.get('scoring', {}).get('score_reason_penalty')}`",
        f"- score_safety_penalty: `{summary.get('scoring', {}).get('score_safety_penalty')}`",
        f"- score_strictness_scale: `{summary.get('scoring', {}).get('score_strictness_scale')}`",
        "",
        "## Ranking",
        "",
    ]
    for row in summary.get("ranking", []):
        lines.append(
            f"- rank={row.get('rank')} profile=`{row.get('profile')}` total_score=`{row.get('total_score')}` "
            f"status=`{row.get('status')}` delta=`{row.get('delta')}` reasons=`{row.get('reasons_count')}` "
            f"confidence_min=`{row.get('planner_change_plan_confidence_min')}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare invariant-repair profiles on the same repair_loop source")
    parser.add_argument("--source", required=True, help="Path to failed run/regression summary JSON")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["default", "industrial_strict"],
        help="Invariant repair profiles to compare",
    )
    parser.add_argument("--planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--baseline", default="auto")
    parser.add_argument("--baseline-index", default="baselines/index.json")
    parser.add_argument("--runtime-threshold", type=float, default=0.2)
    parser.add_argument("--policy", default=None)
    parser.add_argument("--policy-profile", default=None)
    parser.add_argument("--score-status-weight", type=int, default=100)
    parser.add_argument("--score-delta-weight", type=int, default=5)
    parser.add_argument("--score-reason-penalty", type=int, default=1)
    parser.add_argument("--score-safety-penalty", type=int, default=25)
    parser.add_argument("--score-strictness-scale", type=int, default=10)
    parser.add_argument("--out-dir", default="artifacts/invariant_repair_compare")
    parser.add_argument("--out", default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = args.out or str(out_dir / "summary.json")
    out_md = args.report or _default_md_path(out_json)

    rows: list[dict] = []
    for profile in args.profiles:
        profile_out = str(out_dir / f"{profile}.json")
        profile_report = str(out_dir / f"{profile}.md")
        exit_code, payload = _run_profile(profile=profile, args=args, out_json=profile_out, out_md=profile_report)
        row = {
            "profile": profile,
            "exit_code": exit_code,
            "status": payload.get("status", "UNKNOWN"),
            "policy_decision": payload.get("after", {}).get("policy_decision", "UNKNOWN"),
            "delta": payload.get("comparison", {}).get("delta"),
            "reasons_count": len(payload.get("after", {}).get("reasons", []) or []),
            "safety_guard_triggered": bool(payload.get("safety_guard_triggered")),
            "planner_change_plan_confidence_min": float(payload.get("planner_change_plan_confidence_min", 0.0) or 0.0),
            "json_path": profile_out,
            "report_path": profile_report,
        }
        row.update(_score_row(row, args))
        rows.append(row)

    ranking = sorted(
        rows,
        key=lambda x: (
            int(x.get("total_score", -999999)),
            _status_score(x.get("status")),
            -int(x.get("exit_code", 99)),
        ),
        reverse=True,
    )
    for i, row in enumerate(ranking, start=1):
        row["rank"] = i

    best = ranking[0] if ranking else None
    best_profile = best.get("profile") if best else None
    best_reason = "highest_total_score" if best else "no_profiles"
    best_status = str(best.get("status")) if best else "FAIL"
    summary_status = best_status if best_status in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"

    summary = {
        "status": summary_status,
        "source_path": args.source,
        "best_profile": best_profile,
        "best_reason": best_reason,
        "best_total_score": best.get("total_score") if best else None,
        "scoring": {
            "score_status_weight": args.score_status_weight,
            "score_delta_weight": args.score_delta_weight,
            "score_reason_penalty": args.score_reason_penalty,
            "score_safety_penalty": args.score_safety_penalty,
            "score_strictness_scale": args.score_strictness_scale,
        },
        "profile_results": rows,
        "ranking": ranking,
    }
    _write_json(out_json, summary)
    _write_markdown(out_md, summary)
    print(
        json.dumps(
            {
                "status": summary_status,
                "best_profile": best_profile,
                "best_total_score": summary.get("best_total_score"),
            }
        )
    )
    if summary_status == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
