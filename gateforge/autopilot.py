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


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Autopilot Summary",
        "",
        f"- status: `{summary.get('status')}`",
        f"- intent: `{summary.get('intent')}`",
        f"- proposal_id: `{summary.get('proposal_id')}`",
        f"- policy_decision: `{summary.get('policy_decision')}`",
        f"- planner_exit_code: `{summary.get('planner_exit_code')}`",
        f"- agent_run_exit_code: `{summary.get('agent_run_exit_code')}`",
        "",
        "## Paths",
        "",
        f"- intent_path: `{summary.get('intent_path')}`",
        f"- agent_run_path: `{summary.get('agent_run_path')}`",
        f"- run_path: `{summary.get('run_path')}`",
        f"- run_report_path: `{summary.get('run_report_path')}`",
        "",
        "## Policy Reasons",
        "",
    ]
    policy_reasons = summary.get("policy_reasons", [])
    if policy_reasons:
        lines.extend([f"- `{reason}`" for reason in policy_reasons])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Required Human Checks", ""])
    required_checks = summary.get("required_human_checks", [])
    if required_checks:
        lines.extend([f"- {check}" for check in required_checks])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Human Hints", ""])
    human_hints = summary.get("human_hints", [])
    if human_hints:
        lines.extend([f"- {hint}" for hint in human_hints])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command goal -> planner -> agent_run pipeline")
    parser.add_argument("--goal", default=None, help="Natural-language planner goal")
    parser.add_argument("--goal-file", default=None, help="Path to file containing goal text")
    parser.add_argument(
        "--context-json",
        default=None,
        help="Optional context JSON path passed to planner",
    )
    parser.add_argument(
        "--prefer-backend",
        default="auto",
        choices=["auto", "mock", "openmodelica_docker"],
        help="Optional backend preference for planner",
    )
    parser.add_argument("--proposal-id", default=None, help="Optional explicit proposal_id")
    parser.add_argument(
        "--intent-out",
        default="artifacts/autopilot/intent.json",
        help="Where to write planner intent JSON",
    )
    parser.add_argument(
        "--agent-run-out",
        default="artifacts/autopilot/agent_run.json",
        help="Where to write agent_run orchestration JSON",
    )
    parser.add_argument(
        "--save-run-under",
        default="autopilot",
        choices=["autopilot", "agent"],
        help="Which artifacts namespace to use for proposal/run/candidate/regression outputs",
    )
    parser.add_argument(
        "--baseline",
        default="auto",
        help="Baseline evidence path for agent_run (or 'auto')",
    )
    parser.add_argument(
        "--baseline-index",
        default="baselines/index.json",
        help="Baseline index JSON path",
    )
    parser.add_argument(
        "--runtime-threshold",
        type=float,
        default=0.2,
        help="Allowed runtime regression ratio",
    )
    parser.add_argument(
        "--policy",
        default="policies/default_policy.json",
        help="Policy JSON path for run",
    )
    parser.add_argument(
        "--out",
        default="artifacts/autopilot/autopilot_summary.json",
        help="Where to write autopilot summary JSON",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Where to write autopilot markdown summary",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only: run planner and write execution plan without executing agent_run",
    )
    args = parser.parse_args()

    run_root = Path("artifacts") / args.save_run_under
    proposal_out = str(run_root / "proposal.json")
    run_out = str(run_root / "run_summary.json")
    run_report = str(run_root / "run_summary.md")
    candidate_out = str(run_root / "candidate.json")
    regression_out = str(run_root / "regression.json")

    planner_cmd = [
        sys.executable,
        "-m",
        "gateforge.llm_planner",
        "--out",
        args.intent_out,
        "--prefer-backend",
        args.prefer_backend,
    ]
    if args.goal:
        planner_cmd.extend(["--goal", args.goal])
    if args.goal_file:
        planner_cmd.extend(["--goal-file", args.goal_file])
    if args.context_json:
        planner_cmd.extend(["--context-json", args.context_json])
    if args.proposal_id:
        planner_cmd.extend(["--proposal-id", args.proposal_id])

    planner_proc = subprocess.run(planner_cmd, capture_output=True, text=True, check=False)

    agent_cmd = [
        sys.executable,
        "-m",
        "gateforge.agent_run",
        "--intent-file",
        args.intent_out,
        "--proposal-out",
        proposal_out,
        "--run-out",
        run_out,
        "--run-report",
        run_report,
        "--candidate-out",
        candidate_out,
        "--regression-out",
        regression_out,
        "--baseline",
        args.baseline,
        "--baseline-index",
        args.baseline_index,
        "--runtime-threshold",
        str(args.runtime_threshold),
        "--policy",
        args.policy,
        "--out",
        args.agent_run_out,
    ]
    agent_proc = None
    if not args.dry_run:
        agent_proc = subprocess.run(agent_cmd, capture_output=True, text=True, check=False)

    intent_payload = {}
    if Path(args.intent_out).exists():
        intent_payload = json.loads(Path(args.intent_out).read_text(encoding="utf-8"))
    agent_payload = {}
    if not args.dry_run and Path(args.agent_run_out).exists():
        agent_payload = json.loads(Path(args.agent_run_out).read_text(encoding="utf-8"))

    agent_run_exit_code = None if args.dry_run else agent_proc.returncode
    status = "PLANNED" if args.dry_run else agent_payload.get("status", "UNKNOWN")
    summary = {
        "intent_path": args.intent_out,
        "agent_run_path": args.agent_run_out,
        "save_run_under": args.save_run_under,
        "dry_run": args.dry_run,
        "planner_exit_code": planner_proc.returncode,
        "agent_run_exit_code": agent_run_exit_code,
        "intent": intent_payload.get("intent"),
        "proposal_id": agent_payload.get("proposal_id") or intent_payload.get("proposal_id"),
        "status": status,
        "planned_run": {
            "proposal_out": proposal_out,
            "run_out": run_out,
            "run_report": run_report,
            "candidate_out": candidate_out,
            "regression_out": regression_out,
            "baseline": args.baseline,
            "baseline_index": args.baseline_index,
            "runtime_threshold": args.runtime_threshold,
            "policy": args.policy,
        },
    }
    if planner_proc.returncode != 0:
        summary["planner_stderr_tail"] = (planner_proc.stderr or planner_proc.stdout)[-500:]
    if agent_proc is not None and agent_proc.returncode != 0:
        summary["agent_run_stderr_tail"] = (agent_proc.stderr or agent_proc.stdout)[-500:]
    if agent_payload:
        summary["policy_decision"] = agent_payload.get("policy_decision")
        summary["fail_reasons"] = agent_payload.get("fail_reasons", [])
        summary["policy_reasons"] = agent_payload.get("policy_reasons", [])
        summary["human_hints"] = agent_payload.get("human_hints", [])
        summary["required_human_checks"] = agent_payload.get("required_human_checks", [])
        summary["run_path"] = agent_payload.get("run_path")
        summary["run_report_path"] = agent_payload.get("run_report_path")

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "proposal_id": summary["proposal_id"],
                "intent": summary["intent"],
                "dry_run": summary["dry_run"],
            }
        )
    )

    if planner_proc.returncode != 0:
        sys.exit(1)
    if not args.dry_run and agent_proc and agent_proc.returncode != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
