from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .agent import _build_proposal
from .proposal import validate_proposal

SUPPORTED_INTENTS = {
    "demo_mock_pass",
    "demo_openmodelica_pass",
    "medium_openmodelica_pass",
    "runtime_regress_low_risk",
    "runtime_regress_high_risk",
}


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_intent_file(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("intent file must be a JSON object")
    intent = payload.get("intent")
    if intent not in SUPPORTED_INTENTS:
        raise ValueError(f"intent in intent file must be one of {sorted(SUPPORTED_INTENTS)}")
    proposal_id = payload.get("proposal_id")
    if proposal_id is not None and (not isinstance(proposal_id, str) or not proposal_id.strip()):
        raise ValueError("proposal_id in intent file must be a non-empty string when provided")
    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("overrides in intent file must be a JSON object")
    return {
        "intent": intent,
        "proposal_id": proposal_id,
        "overrides": overrides,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate agent proposal and execute GateForge run in one command")
    parser.add_argument(
        "--intent",
        default=None,
        choices=sorted(SUPPORTED_INTENTS),
        help="Agent intent template",
    )
    parser.add_argument(
        "--intent-file",
        default=None,
        help="Path to intent request JSON (for LLM/external planner output)",
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
        default=None,
        help="Policy JSON path (default: policies/default_policy.json)",
    )
    parser.add_argument(
        "--policy-profile",
        default=None,
        help="Policy profile name under policies/profiles (e.g. industrial_strict_v0)",
    )
    parser.add_argument(
        "--out",
        default="artifacts/agent/agent_run.json",
        help="Where to write agent-run orchestration summary JSON",
    )
    args = parser.parse_args()

    if bool(args.intent) == bool(args.intent_file):
        raise SystemExit("Exactly one of --intent or --intent-file must be provided")

    resolved_intent = args.intent
    resolved_proposal_id = args.proposal_id
    proposal_overrides: dict = {}
    if args.intent_file:
        intent_request = _load_intent_file(args.intent_file)
        resolved_intent = intent_request["intent"]
        resolved_proposal_id = intent_request["proposal_id"] or resolved_proposal_id
        proposal_overrides = intent_request["overrides"]

    proposal = _build_proposal(intent=resolved_intent, proposal_id=resolved_proposal_id)
    if proposal_overrides:
        proposal.update(proposal_overrides)
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
    ]
    if args.policy:
        cmd.extend(["--policy", args.policy])
    if args.policy_profile:
        cmd.extend(["--policy-profile", args.policy_profile])
    run_proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    run_summary = {}
    run_status = "UNKNOWN"
    if Path(args.run_out).exists():
        run_summary = json.loads(Path(args.run_out).read_text(encoding="utf-8"))
        run_status = run_summary.get("status", "UNKNOWN")

    orchestration = {
        "intent": resolved_intent,
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
        orchestration["policy_version"] = run_summary.get("policy_version")
        orchestration["policy_decision"] = run_summary.get("policy_decision")
        orchestration["fail_reasons"] = run_summary.get("fail_reasons", [])
        orchestration["policy_reasons"] = run_summary.get("policy_reasons", [])
        orchestration["human_hints"] = run_summary.get("human_hints", [])
        orchestration["required_human_checks"] = run_summary.get("required_human_checks", [])
        orchestration["change_apply_status"] = run_summary.get("change_apply_status")
        orchestration["change_set_hash"] = run_summary.get("change_set_hash")
        orchestration["applied_changes_count"] = len(run_summary.get("applied_changes") or [])
    if run_proc.returncode != 0:
        orchestration["run_stderr_tail"] = (run_proc.stderr or run_proc.stdout)[-500:]

    _write_json(args.out, orchestration)
    print(json.dumps({"proposal_id": proposal["proposal_id"], "status": run_status, "intent": resolved_intent}))

    if run_proc.returncode != 0:
        sys.exit(run_proc.returncode)


if __name__ == "__main__":
    main()
