from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .agent import _build_proposal
from .proposal import validate_proposal


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate agent proposal and execute GateForge run in one command")
    parser.add_argument(
        "--intent",
        required=True,
        choices=[
            "demo_mock_pass",
            "demo_openmodelica_pass",
            "medium_openmodelica_pass",
            "runtime_regress_low_risk",
            "runtime_regress_high_risk",
        ],
        help="Agent intent template",
    )
    parser.add_argument(
        "--proposal-id",
        default=None,
        help="Optional explicit proposal_id",
    )
    parser.add_argument(
        "--proposal-out",
        default="artifacts/agent/proposal.json",
        help="Where to write generated proposal JSON",
    )
    parser.add_argument(
        "--run-out",
        default="artifacts/agent/run_summary.json",
        help="Where to write run summary JSON",
    )
    parser.add_argument(
        "--run-report",
        default="artifacts/agent/run_summary.md",
        help="Where to write run markdown summary",
    )
    parser.add_argument(
        "--candidate-out",
        default="artifacts/agent/candidate.json",
        help="Where to write candidate evidence",
    )
    parser.add_argument(
        "--regression-out",
        default="artifacts/agent/regression.json",
        help="Where to write regression JSON",
    )
    parser.add_argument(
        "--baseline",
        default="auto",
        help="Baseline evidence path for run (or 'auto')",
    )
    parser.add_argument(
        "--baseline-index",
        default="baselines/index.json",
        help="Baseline index JSON used when --baseline=auto",
    )
    parser.add_argument(
        "--runtime-threshold",
        type=float,
        default=0.2,
        help="Allowed runtime regression ratio (0.2 = +20%%)",
    )
    parser.add_argument(
        "--policy",
        default="policies/default_policy.json",
        help="Policy JSON path",
    )
    parser.add_argument(
        "--out",
        default="artifacts/agent/agent_run.json",
        help="Where to write agent-run orchestration summary JSON",
    )
    args = parser.parse_args()

    proposal = _build_proposal(intent=args.intent, proposal_id=args.proposal_id)
    validate_proposal(proposal)
    _write_json(args.proposal_out, proposal)

    cmd = [
        sys.executable,
        "-m",
        "gateforge.run",
        "--proposal",
        args.proposal_out,
        "--out",
        args.run_out,
        "--report",
        args.run_report,
        "--candidate-out",
        args.candidate_out,
        "--regression-out",
        args.regression_out,
        "--baseline",
        args.baseline,
        "--baseline-index",
        args.baseline_index,
        "--runtime-threshold",
        str(args.runtime_threshold),
        "--policy",
        args.policy,
    ]
    run_proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    run_summary = {}
    run_status = "UNKNOWN"
    if Path(args.run_out).exists():
        run_summary = json.loads(Path(args.run_out).read_text(encoding="utf-8"))
        run_status = run_summary.get("status", "UNKNOWN")

    orchestration = {
        "intent": args.intent,
        "proposal_id": proposal["proposal_id"],
        "proposal_path": args.proposal_out,
        "run_path": args.run_out,
        "run_report_path": args.run_report,
        "candidate_path": args.candidate_out,
        "regression_path": args.regression_out,
        "status": run_status,
        "run_exit_code": run_proc.returncode,
    }
    if run_summary:
        orchestration["policy_decision"] = run_summary.get("policy_decision")
        orchestration["fail_reasons"] = run_summary.get("fail_reasons", [])
        orchestration["policy_reasons"] = run_summary.get("policy_reasons", [])
        orchestration["human_hints"] = run_summary.get("human_hints", [])
    if run_proc.returncode != 0:
        orchestration["run_stderr_tail"] = (run_proc.stderr or run_proc.stdout)[-500:]

    _write_json(args.out, orchestration)
    print(json.dumps({"proposal_id": proposal["proposal_id"], "status": run_status, "intent": args.intent}))

    if run_proc.returncode != 0:
        sys.exit(run_proc.returncode)


if __name__ == "__main__":
    main()
