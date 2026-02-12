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
    args = parser.parse_args()

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
    agent_proc = subprocess.run(agent_cmd, capture_output=True, text=True, check=False)

    intent_payload = {}
    if Path(args.intent_out).exists():
        intent_payload = json.loads(Path(args.intent_out).read_text(encoding="utf-8"))
    agent_payload = {}
    if Path(args.agent_run_out).exists():
        agent_payload = json.loads(Path(args.agent_run_out).read_text(encoding="utf-8"))

    summary = {
        "intent_path": args.intent_out,
        "agent_run_path": args.agent_run_out,
        "planner_exit_code": planner_proc.returncode,
        "agent_run_exit_code": agent_proc.returncode,
        "intent": intent_payload.get("intent"),
        "proposal_id": agent_payload.get("proposal_id"),
        "status": agent_payload.get("status", "UNKNOWN"),
    }
    if planner_proc.returncode != 0:
        summary["planner_stderr_tail"] = (planner_proc.stderr or planner_proc.stdout)[-500:]
    if agent_proc.returncode != 0:
        summary["agent_run_stderr_tail"] = (agent_proc.stderr or agent_proc.stdout)[-500:]
    if agent_payload:
        summary["policy_decision"] = agent_payload.get("policy_decision")
        summary["fail_reasons"] = agent_payload.get("fail_reasons", [])
        summary["human_hints"] = agent_payload.get("human_hints", [])

    _write_json(args.out, summary)
    print(json.dumps({"status": summary["status"], "proposal_id": summary["proposal_id"], "intent": summary["intent"]}))

    if planner_proc.returncode != 0 or agent_proc.returncode != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
