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


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Repair Orchestrate Summary",
        "",
        f"- status: `{summary.get('status')}`",
        f"- planner_backend: `{summary.get('planner_backend')}`",
        f"- strategy_profile: `{summary.get('strategy_profile')}`",
        f"- batch_status: `{summary.get('batch_status')}`",
        "",
        "## Step Exit Codes",
        "",
    ]
    for step, code in (summary.get("step_exit_codes") or {}).items():
        lines.append(f"- {step}: `{code}`")

    compare = summary.get("compare")
    if isinstance(compare, dict):
        lines.extend(
            [
                "",
                "## Compare",
                "",
                f"- compare_strategy_profile: `{compare.get('strategy_profile')}`",
                f"- compare_status: `{compare.get('status')}`",
                f"- compare_batch_status: `{compare.get('batch_status')}`",
            ]
        )
    strategy_compare = summary.get("strategy_compare")
    if isinstance(strategy_compare, dict):
        lines.extend(
            [
                "",
                "## Strategy Compare",
                "",
                f"- relation: `{strategy_compare.get('relation')}`",
                f"- from_profile: `{strategy_compare.get('from_profile')}`",
                f"- to_profile: `{strategy_compare.get('to_profile')}`",
                f"- recommended_profile: `{strategy_compare.get('recommended_profile')}`",
                f"- recommendation_reason: `{strategy_compare.get('recommendation_reason')}`",
                f"- fail_count_delta: `{strategy_compare.get('fail_count_delta')}`",
                f"- safety_block_count_delta: `{strategy_compare.get('safety_block_count_delta')}`",
            ]
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def _status_score(status: str | None) -> int:
    value = str(status or "").upper()
    if value == "PASS":
        return 2
    if value == "NEEDS_REVIEW":
        return 1
    if value == "FAIL":
        return 0
    return -1


def _recommend_profile(
    *,
    from_profile: str,
    to_profile: str,
    relation: str,
    fail_count_delta: int,
    safety_block_count_delta: int,
) -> tuple[str, str]:
    if relation == "upgraded":
        return to_profile, "to_profile_upgraded_batch_status"
    if relation == "downgraded":
        return from_profile, "to_profile_downgraded_batch_status"
    if fail_count_delta < 0:
        return to_profile, "to_profile_reduced_fail_count"
    if fail_count_delta > 0:
        return from_profile, "to_profile_increased_fail_count"
    if safety_block_count_delta < 0:
        return to_profile, "to_profile_reduced_safety_blocks"
    if safety_block_count_delta > 0:
        return from_profile, "to_profile_increased_safety_blocks"
    return from_profile, "unchanged_keep_from_profile"


def _pipeline_public_summary(payload: dict) -> dict:
    return {
        "status": payload.get("status"),
        "batch_status": payload.get("batch_status"),
        "tasks_path": payload.get("tasks_path"),
        "pack_path": payload.get("pack_path"),
        "batch_summary_path": payload.get("batch_summary_path"),
        "step_exit_codes": payload.get("step_exit_codes"),
        "step_stderr_tail": payload.get("step_stderr_tail"),
    }


def _derive_batch_status(batch_summary: dict | None) -> str:
    if not isinstance(batch_summary, dict):
        return "UNKNOWN"
    fail_count = int(batch_summary.get("fail_count", 0) or 0)
    unknown_count = int(batch_summary.get("unknown_count", 0) or 0)
    needs_review_count = int(batch_summary.get("needs_review_count", 0) or 0)
    if fail_count > 0 or unknown_count > 0:
        return "FAIL"
    if needs_review_count > 0:
        return "NEEDS_REVIEW"
    return "PASS"


def _run_pipeline(
    *,
    source: str,
    out_dir: Path,
    planner_backend: str,
    strategy_profile: str,
    policy_profile: str | None,
    baseline: str,
    continue_on_fail: bool,
    max_cases: int,
    pack_id: str,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_out = str(out_dir / "tasks.json")
    tasks_md = str(out_dir / "tasks.md")
    pack_out = str(out_dir / "pack.json")
    batch_out = str(out_dir / "batch_summary.json")
    batch_md = str(out_dir / "batch_summary.md")

    tasks_cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_tasks",
        "--source",
        source,
        "--out",
        tasks_out,
        "--report",
        tasks_md,
    ]
    if policy_profile:
        tasks_cmd.extend(["--policy-profile", policy_profile])
    tasks_code, _tasks_stdout, tasks_stderr = _run_cmd(tasks_cmd)

    pack_cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_pack",
        "--tasks-summary",
        tasks_out,
        "--pack-id",
        pack_id,
        "--planner-backend",
        planner_backend,
        "--strategy-profile",
        strategy_profile,
        "--max-cases",
        str(max_cases),
        "--out",
        pack_out,
    ]
    if policy_profile:
        pack_cmd.extend(["--policy-profile", policy_profile])
    pack_code, _pack_stdout, pack_stderr = _run_cmd(pack_cmd) if tasks_code == 0 else (99, "", "tasks step failed")

    batch_cmd = [
        sys.executable,
        "-m",
        "gateforge.repair_batch",
        "--pack",
        pack_out,
        "--planner-backend",
        planner_backend,
        "--baseline",
        baseline,
        "--summary-out",
        batch_out,
        "--report-out",
        batch_md,
    ]
    if continue_on_fail:
        batch_cmd.append("--continue-on-fail")
    else:
        batch_cmd.append("--no-continue-on-fail")
    if policy_profile:
        batch_cmd.extend(["--policy-profile", policy_profile])
    batch_code, _batch_stdout, batch_stderr = _run_cmd(batch_cmd) if pack_code == 0 else (99, "", "pack step failed")

    batch_payload = {}
    batch_path = Path(batch_out)
    if batch_path.exists():
        batch_payload = json.loads(batch_path.read_text(encoding="utf-8"))

    pipeline_status = "PASS" if tasks_code == 0 and pack_code == 0 and batch_code == 0 else "FAIL"
    return {
        "status": pipeline_status,
        "source": source,
        "planner_backend": planner_backend,
        "strategy_profile": strategy_profile,
        "policy_profile": policy_profile,
        "tasks_path": tasks_out,
        "pack_path": pack_out,
        "batch_summary_path": batch_out,
        "step_exit_codes": {
            "repair_tasks": tasks_code,
            "repair_pack": pack_code,
            "repair_batch": batch_code,
        },
        "step_stderr_tail": {
            "repair_tasks": tasks_stderr[-400:],
            "repair_pack": pack_stderr[-400:],
            "repair_batch": batch_stderr[-400:],
        },
        "batch_status": _derive_batch_status(batch_payload),
        "batch_summary": batch_payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repair pipeline: tasks -> pack -> batch")
    parser.add_argument("--source", required=True, help="Failing run/regression summary JSON path")
    parser.add_argument("--out-dir", default="artifacts/repair_orchestrate", help="Output directory")
    parser.add_argument("--planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--strategy-profile", default="default", help="repair_pack strategy profile")
    parser.add_argument(
        "--compare-strategy-profiles",
        nargs=2,
        default=None,
        metavar=("FROM_PROFILE", "TO_PROFILE"),
        help="Optional strategy profile comparison for the same source",
    )
    parser.add_argument("--policy-profile", default=None, help="Optional policy profile for generated cases")
    parser.add_argument("--baseline", default="auto", help="Baseline path for repair_batch")
    parser.add_argument("--continue-on-fail", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-cases", type=int, default=5, help="Maximum fix_plan tasks to convert")
    parser.add_argument("--pack-id", default="repair_orchestrate_pack_v0", help="Generated pack id")
    parser.add_argument("--out", default=None, help="Optional summary JSON path")
    parser.add_argument("--report", default=None, help="Optional summary markdown path")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    summary_out = args.out or str(out_dir / "summary.json")
    report_out = args.report or str(Path(summary_out).with_suffix(".md"))
    base_profile = args.strategy_profile
    if args.compare_strategy_profiles:
        base_profile = args.compare_strategy_profiles[0]
        compare_profile = args.compare_strategy_profiles[1]
        if base_profile == compare_profile:
            raise SystemExit("compare profiles must be different")

    primary = _run_pipeline(
        source=args.source,
        out_dir=out_dir,
        planner_backend=args.planner_backend,
        strategy_profile=base_profile,
        policy_profile=args.policy_profile,
        baseline=args.baseline,
        continue_on_fail=bool(args.continue_on_fail),
        max_cases=int(args.max_cases),
        pack_id=args.pack_id,
    )
    summary = dict(primary)
    summary["strategy_profile"] = base_profile
    summary["primary"] = _pipeline_public_summary(primary)

    compare = None
    if args.compare_strategy_profiles:
        compare_profile = args.compare_strategy_profiles[1]
        compare_out_dir = out_dir / f"compare_{compare_profile}"
        compare = _run_pipeline(
            source=args.source,
            out_dir=compare_out_dir,
            planner_backend=args.planner_backend,
            strategy_profile=compare_profile,
            policy_profile=args.policy_profile,
            baseline=args.baseline,
            continue_on_fail=bool(args.continue_on_fail),
            max_cases=int(args.max_cases),
            pack_id=f"{args.pack_id}_{compare_profile}",
        )
        summary["compare"] = {"strategy_profile": compare_profile, **_pipeline_public_summary(compare)}

        primary_batch_status = primary.get("batch_status")
        compare_batch_status = compare.get("batch_status")
        s1 = _status_score(primary_batch_status)
        s2 = _status_score(compare_batch_status)
        if s2 > s1:
            relation = "upgraded"
        elif s2 < s1:
            relation = "downgraded"
        else:
            relation = "unchanged"
        fail_count_delta = int(compare.get("batch_summary", {}).get("fail_count", 0)) - int(
            primary.get("batch_summary", {}).get("fail_count", 0)
        )
        safety_block_count_delta = int(compare.get("batch_summary", {}).get("safety_block_count", 0)) - int(
            primary.get("batch_summary", {}).get("safety_block_count", 0)
        )
        recommended_profile, recommendation_reason = _recommend_profile(
            from_profile=base_profile,
            to_profile=compare_profile,
            relation=relation,
            fail_count_delta=fail_count_delta,
            safety_block_count_delta=safety_block_count_delta,
        )
        summary["strategy_compare"] = {
            "from_profile": base_profile,
            "to_profile": compare_profile,
            "from_batch_status": primary_batch_status,
            "to_batch_status": compare_batch_status,
            "from_score": s1,
            "to_score": s2,
            "relation": relation,
            "pass_count_delta": int(compare.get("batch_summary", {}).get("pass_count", 0))
            - int(primary.get("batch_summary", {}).get("pass_count", 0)),
            "fail_count_delta": fail_count_delta,
            "safety_block_count_delta": safety_block_count_delta,
            "recommended_profile": recommended_profile,
            "recommendation_reason": recommendation_reason,
        }

    status = "PASS"
    if primary.get("status") != "PASS":
        status = "FAIL"
    if compare is not None and compare.get("status") != "PASS":
        status = "FAIL"
    summary["status"] = status
    _write_json(summary_out, summary)
    _write_markdown(report_out, summary)
    print(json.dumps({"status": status, "summary": summary_out}))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
