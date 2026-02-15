from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


STATUS_SCORE = {
    "PASS": 2,
    "NEEDS_REVIEW": 1,
    "FAIL": 0,
    "UNKNOWN": -1,
}


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _safe_case_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
    cleaned = cleaned.strip("_")
    return cleaned or "case"


def _load_pack(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pack must be a JSON object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("pack must contain non-empty 'cases' list")
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{i}] must be an object")
        if not isinstance(case.get("source"), str) or not case.get("source"):
            raise ValueError(f"cases[{i}].source is required")
    return payload


def _build_case_cmd(
    *,
    case: dict,
    args: argparse.Namespace,
    source: str,
    case_out_json: str,
    case_out_md: str,
    profile_override: str | None,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_loop",
        "--source",
        source,
        "--planner-backend",
        str(case.get("planner_backend") or args.planner_backend),
        "--baseline",
        str(case.get("baseline") or args.baseline),
        "--baseline-index",
        str(case.get("baseline_index") or args.baseline_index),
        "--runtime-threshold",
        str(case.get("runtime_threshold") if case.get("runtime_threshold") is not None else args.runtime_threshold),
        "--save-run-under",
        str(case.get("save_run_under") or args.save_run_under),
        "--max-retries",
        str(case.get("max_retries") if case.get("max_retries") is not None else args.max_retries),
        "--retry-fallback-planner-backend",
        str(case.get("retry_fallback_planner_backend") or args.retry_fallback_planner_backend),
        "--retry-confidence-min",
        str(case.get("retry_confidence_min") if case.get("retry_confidence_min") is not None else args.retry_confidence_min),
        "--out",
        case_out_json,
        "--report",
        case_out_md,
    ]

    if case.get("proposal_id"):
        cmd.extend(["--proposal-id", str(case["proposal_id"])])

    policy_value = case.get("policy") if case.get("policy") is not None else args.policy
    if policy_value:
        cmd.extend(["--policy", str(policy_value)])

    if profile_override is not None:
        profile_value = profile_override
    else:
        profile_value = case.get("policy_profile") if case.get("policy_profile") is not None else args.policy_profile
    if profile_value:
        cmd.extend(["--policy-profile", str(profile_value)])

    retry_enabled = case.get("retry_on_failed_attempt")
    if retry_enabled is None:
        retry_enabled = args.retry_on_failed_attempt
    cmd.append("--retry-on-failed-attempt" if retry_enabled else "--no-retry-on-failed-attempt")
    return cmd


def _run_cases(
    *,
    cases: list[dict],
    args: argparse.Namespace,
    out_dir: Path,
    profile_override: str | None,
    tag: str,
) -> tuple[list[dict], dict]:
    results: list[dict] = []
    fail_count = 0
    needs_review_count = 0
    unknown_count = 0
    improved_count = 0
    unchanged_count = 0
    worse_count = 0
    safety_block_count = 0

    for idx, case in enumerate(cases):
        source = str(case["source"])
        name = str(case.get("name") or f"case_{idx+1}")
        safe_name = _safe_case_name(name)

        suffix = f"_{tag}" if tag else ""
        case_out_json = str(out_dir / f"{safe_name}{suffix}.json")
        case_out_md = str(out_dir / f"{safe_name}{suffix}.md")

        cmd = _build_case_cmd(
            case=case,
            args=args,
            source=source,
            case_out_json=case_out_json,
            case_out_md=case_out_md,
            profile_override=profile_override,
        )

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

        payload = {}
        if Path(case_out_json).exists():
            payload = json.loads(Path(case_out_json).read_text(encoding="utf-8"))

        status = str(payload.get("status") or "UNKNOWN").upper()
        reasons = payload.get("after", {}).get("reasons")
        if not isinstance(reasons, list):
            reasons = []

        row = {
            "name": name,
            "source": source,
            "status": status,
            "delta": payload.get("comparison", {}).get("delta"),
            "safety_guard_triggered": bool(payload.get("safety_guard_triggered")),
            "retry_used": bool(payload.get("retry_used")),
            "selected_attempt": payload.get("selected_attempt"),
            "planner_backend": payload.get("planner_backend"),
            "exit_code": int(proc.returncode),
            "reasons": [str(r) for r in reasons if isinstance(r, str)],
            "json_path": case_out_json,
            "report_path": case_out_md,
            "policy_profile": profile_override,
        }
        results.append(row)
        if row["delta"] == "improved":
            improved_count += 1
        elif row["delta"] == "worse":
            worse_count += 1
        else:
            unchanged_count += 1
        if row["safety_guard_triggered"]:
            safety_block_count += 1

        if status == "FAIL":
            fail_count += 1
        elif status == "NEEDS_REVIEW":
            needs_review_count += 1
        elif status not in {"PASS"}:
            unknown_count += 1

        if proc.returncode != 0 and not args.continue_on_fail:
            break

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    summary = {
        "total_cases": len(results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "needs_review_count": needs_review_count,
        "unknown_count": unknown_count,
        "improved_count": improved_count,
        "unchanged_count": unchanged_count,
        "worse_count": worse_count,
        "safety_block_count": safety_block_count,
    }
    return results, summary


def _compare_profiles(primary_results: list[dict], strict_results: list[dict], from_profile: str, to_profile: str) -> dict:
    by_name_primary = {r["name"]: r for r in primary_results}
    by_name_strict = {r["name"]: r for r in strict_results}

    transitions = []
    downgrade = 0
    upgrade = 0
    unchanged = 0

    for name in sorted(set(by_name_primary.keys()) & set(by_name_strict.keys())):
        src = by_name_primary[name]
        dst = by_name_strict[name]
        s1 = str(src.get("status") or "UNKNOWN").upper()
        s2 = str(dst.get("status") or "UNKNOWN").upper()
        sc1 = STATUS_SCORE.get(s1, -1)
        sc2 = STATUS_SCORE.get(s2, -1)
        if sc2 < sc1:
            relation = "downgraded"
            downgrade += 1
        elif sc2 > sc1:
            relation = "upgraded"
            upgrade += 1
        else:
            relation = "unchanged"
            unchanged += 1
        transitions.append(
            {
                "name": name,
                "from_status": s1,
                "to_status": s2,
                "relation": relation,
            }
        )

    total = len(transitions)
    strict_downgrade_rate = round(downgrade / total, 4) if total else 0.0
    from_reason_counts = Counter()
    for row in primary_results:
        for reason in row.get("reasons", []) or []:
            if isinstance(reason, str):
                from_reason_counts[reason] += 1
    to_reason_counts = Counter()
    for row in strict_results:
        for reason in row.get("reasons", []) or []:
            if isinstance(reason, str):
                to_reason_counts[reason] += 1
    all_reasons = sorted(set(from_reason_counts.keys()) | set(to_reason_counts.keys()))
    delta_reason_counts = {
        reason: int(to_reason_counts.get(reason, 0) - from_reason_counts.get(reason, 0))
        for reason in all_reasons
    }
    return {
        "from_policy_profile": from_profile,
        "to_policy_profile": to_profile,
        "total_compared_cases": total,
        "downgrade_count": downgrade,
        "upgrade_count": upgrade,
        "unchanged_count": unchanged,
        "strict_downgrade_rate": strict_downgrade_rate,
        "transitions": transitions,
        "reason_distribution": {
            "from_counts": dict(from_reason_counts),
            "to_counts": dict(to_reason_counts),
            "delta_counts": delta_reason_counts,
            "new_reasons_in_to": sorted(set(to_reason_counts.keys()) - set(from_reason_counts.keys())),
            "resolved_reasons_in_to": sorted(set(from_reason_counts.keys()) - set(to_reason_counts.keys())),
        },
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Repair Batch Summary",
        "",
        f"- pack_id: `{summary.get('pack_id')}`",
        f"- planner_backend_default: `{summary.get('planner_backend_default')}`",
        f"- total_cases: `{summary.get('total_cases')}`",
        f"- pass_count: `{summary.get('pass_count')}`",
        f"- fail_count: `{summary.get('fail_count')}`",
        f"- needs_review_count: `{summary.get('needs_review_count')}`",
        f"- unknown_count: `{summary.get('unknown_count')}`",
        f"- improved_count: `{summary.get('improved_count')}`",
        f"- unchanged_count: `{summary.get('unchanged_count')}`",
        f"- worse_count: `{summary.get('worse_count')}`",
        f"- safety_block_count: `{summary.get('safety_block_count')}`",
        "",
        "## Cases",
        "",
    ]

    cases = summary.get("cases", [])
    if not cases:
        lines.append("- `none`")
    else:
        for case in cases:
            lines.append(
                f"- `{case.get('name')}`: status=`{case.get('status')}` delta=`{case.get('delta')}` "
                f"retry_used=`{case.get('retry_used')}` exit_code=`{case.get('exit_code')}`"
            )

    lines.extend(["", "## Failed Cases", ""])
    failed = [c for c in cases if c.get("status") in {"FAIL", "UNKNOWN"}]
    if failed:
        for case in failed:
            lines.append(f"- `{case.get('name')}` reasons=`{','.join(case.get('reasons', [])) or 'none'}`")
    else:
        lines.append("- `none`")

    compare = summary.get("profile_compare")
    if isinstance(compare, dict):
        lines.extend(
            [
                "",
                "## Policy Profile Comparison",
                "",
                f"- from_policy_profile: `{compare.get('from_policy_profile')}`",
                f"- to_policy_profile: `{compare.get('to_policy_profile')}`",
                f"- total_compared_cases: `{compare.get('total_compared_cases')}`",
                f"- downgrade_count: `{compare.get('downgrade_count')}`",
                f"- upgrade_count: `{compare.get('upgrade_count')}`",
                f"- unchanged_count: `{compare.get('unchanged_count')}`",
                f"- strict_downgrade_rate: `{compare.get('strict_downgrade_rate')}`",
                "",
                "### Transitions",
                "",
            ]
        )
        transitions = compare.get("transitions", [])
        if transitions:
            for t in transitions:
                lines.append(
                    f"- `{t.get('name')}`: `{t.get('from_status')}` -> `{t.get('to_status')}` ({t.get('relation')})"
                )
        else:
            lines.append("- `none`")
        lines.extend(["", "### Reason Distribution Delta", ""])
        reason_dist = compare.get("reason_distribution", {})
        delta_counts = reason_dist.get("delta_counts", {})
        if isinstance(delta_counts, dict) and delta_counts:
            for reason in sorted(delta_counts.keys()):
                lines.append(f"- `{reason}`: `{delta_counts[reason]}`")
        else:
            lines.append("- `none`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repair_loop over a batch pack")
    parser.add_argument("--pack", required=True, help="Path to repair batch pack JSON")
    parser.add_argument("--out-dir", default="artifacts/repair_batch", help="Where to write per-case outputs")
    parser.add_argument("--summary-out", default="artifacts/repair_batch/summary.json", help="Summary JSON path")
    parser.add_argument("--report-out", default=None, help="Summary markdown path")
    parser.add_argument("--planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--baseline", default="auto")
    parser.add_argument("--baseline-index", default="baselines/index.json")
    parser.add_argument("--runtime-threshold", type=float, default=0.2)
    parser.add_argument("--policy", default=None)
    parser.add_argument("--policy-profile", default=None)
    parser.add_argument(
        "--compare-policy-profiles",
        nargs=2,
        default=None,
        metavar=("FROM_PROFILE", "TO_PROFILE"),
        help="Run pack twice and compute status transitions between two policy profiles",
    )
    parser.add_argument("--save-run-under", default="autopilot", choices=["autopilot", "agent"])
    parser.add_argument("--retry-on-failed-attempt", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--retry-fallback-planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--retry-confidence-min", type=float, default=0.8)
    parser.add_argument("--continue-on-fail", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    pack = _load_pack(args.pack)
    pack_id = pack.get("pack_id", "repair_pack")
    cases = pack["cases"]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    primary_profile = args.policy_profile
    if args.compare_policy_profiles:
        primary_profile = args.compare_policy_profiles[0]

    primary_results, primary_counts = _run_cases(
        cases=cases,
        args=args,
        out_dir=out_dir,
        profile_override=primary_profile,
        tag="primary",
    )

    summary = {
        "pack_id": str(pack_id),
        "planner_backend_default": args.planner_backend,
        "total_cases": primary_counts["total_cases"],
        "pass_count": primary_counts["pass_count"],
        "fail_count": primary_counts["fail_count"],
        "needs_review_count": primary_counts["needs_review_count"],
        "unknown_count": primary_counts["unknown_count"],
        "improved_count": primary_counts["improved_count"],
        "unchanged_count": primary_counts["unchanged_count"],
        "worse_count": primary_counts["worse_count"],
        "safety_block_count": primary_counts["safety_block_count"],
        "cases": primary_results,
        "policy_profile": primary_profile,
    }

    if args.compare_policy_profiles:
        to_profile = args.compare_policy_profiles[1]
        compare_results, _ = _run_cases(
            cases=cases,
            args=args,
            out_dir=out_dir,
            profile_override=to_profile,
            tag="compare",
        )
        summary["profile_compare"] = _compare_profiles(
            primary_results,
            compare_results,
            from_profile=args.compare_policy_profiles[0],
            to_profile=to_profile,
        )

    _write_json(args.summary_out, summary)
    _write_markdown(args.report_out or _default_md_path(args.summary_out), summary)

    print(
        json.dumps(
            {
                "pack_id": summary["pack_id"],
                "total_cases": summary["total_cases"],
                "fail_count": summary["fail_count"],
            }
        )
    )
    if summary["fail_count"] > 0 or summary["unknown_count"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
