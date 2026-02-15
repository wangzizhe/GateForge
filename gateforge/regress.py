from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checkers import available_checkers
from .policy import DEFAULT_POLICY_PATH, evaluate_policy, load_policy
from .proposal import execution_target_from_proposal, load_proposal
from .regression import compare_evidence, load_json, write_json, write_markdown


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _inject_invariants_into_checker_config(checker_config: dict, proposal: dict) -> dict:
    physical_invariants = proposal.get("physical_invariants")
    if not isinstance(physical_invariants, list) or not physical_invariants:
        return checker_config
    merged = dict(checker_config)
    guard_cfg = merged.get("invariant_guard")
    if not isinstance(guard_cfg, dict):
        guard_cfg = {}
    guard_cfg = dict(guard_cfg)
    guard_cfg["invariants"] = physical_invariants
    merged["invariant_guard"] = guard_cfg
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate evidence")
    parser.add_argument("--baseline", required=True, help="Path to baseline evidence.json")
    parser.add_argument("--candidate", required=True, help="Path to candidate evidence.json")
    parser.add_argument(
        "--runtime-threshold",
        type=float,
        default=0.2,
        help="Allowed runtime regression ratio (0.2 = +20%%)",
    )
    parser.add_argument(
        "--out",
        default="artifacts/regression.json",
        help="Where to write regression decision JSON",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict comparability checks (schema_version/backend)",
    )
    parser.add_argument(
        "--strict-model-script",
        action="store_true",
        help="When strict mode is enabled, also require model_script to match",
    )
    parser.add_argument(
        "--strict-policy-version",
        action="store_true",
        help="When strict mode is enabled, also fail on policy_version mismatch (otherwise warning only)",
    )
    parser.add_argument(
        "--proposal",
        default=None,
        help="Optional proposal JSON path; enables strict comparability and proposal alignment checks",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Where to write regression markdown report",
    )
    parser.add_argument(
        "--policy",
        default=DEFAULT_POLICY_PATH,
        help="Policy JSON path used when --proposal is provided",
    )
    parser.add_argument(
        "--checker",
        action="append",
        dest="checkers",
        default=None,
        help=f"Enable specific checker by name (repeatable). Available: {', '.join(available_checkers())}",
    )
    parser.add_argument(
        "--checker-config",
        default=None,
        help="Optional checker config JSON path",
    )
    args = parser.parse_args()

    baseline = load_json(args.baseline)
    candidate = load_json(args.candidate)
    strict = args.strict
    strict_model_script = args.strict_model_script
    expected_backend = None
    expected_script = None
    effective_checkers = args.checkers
    checker_config = {}
    if args.checker_config:
        checker_config = load_json(args.checker_config)
        if not isinstance(checker_config, dict):
            raise SystemExit("--checker-config must point to a JSON object")
    if args.proposal:
        proposal = load_proposal(args.proposal)
        expected_backend, expected_script = execution_target_from_proposal(proposal)
        expected_proposal_id = proposal.get("proposal_id")
        expected_risk_level = proposal.get("risk_level")
        if effective_checkers is None:
            effective_checkers = proposal.get("checkers")
        if not checker_config:
            checker_config = proposal.get("checker_config", {})
        checker_config = _inject_invariants_into_checker_config(checker_config, proposal)
        strict = True
        strict_model_script = True
    else:
        expected_proposal_id = None
        expected_risk_level = None

    result = compare_evidence(
        baseline=baseline,
        candidate=candidate,
        runtime_regression_threshold=args.runtime_threshold,
        strict=strict,
        strict_model_script=strict_model_script,
        strict_policy_version=args.strict_policy_version,
        checker_names=effective_checkers,
        checker_config=checker_config,
    )
    if expected_backend is not None:
        if baseline.get("backend") != expected_backend:
            result["reasons"].append("proposal_backend_mismatch_baseline")
        if candidate.get("backend") != expected_backend:
            result["reasons"].append("proposal_backend_mismatch_candidate")
    if expected_script is not None:
        if baseline.get("model_script") != expected_script:
            result["reasons"].append("proposal_model_script_mismatch_baseline")
        if candidate.get("model_script") != expected_script:
            result["reasons"].append("proposal_model_script_mismatch_candidate")
    if result["reasons"]:
        result["decision"] = "FAIL"
    result["strict"] = strict
    result["strict_model_script"] = strict_model_script
    result["strict_policy_version"] = args.strict_policy_version
    result["checkers"] = effective_checkers or []
    result["checker_config"] = checker_config
    if args.proposal:
        policy = load_policy(args.policy)
        policy_result = evaluate_policy(
            reasons=result["reasons"],
            risk_level=expected_risk_level or "medium",
            policy=policy,
        )
        result["decision"] = policy_result["policy_decision"]
        result["policy_decision"] = policy_result["policy_decision"]
        result["policy_reasons"] = policy_result["policy_reasons"]
        result["risk_level"] = expected_risk_level
        result["policy_path"] = args.policy
        result["proposal_id"] = expected_proposal_id
        result["proposal_expected_backend"] = expected_backend
        result["proposal_expected_model_script"] = expected_script

    write_json(args.out, result)
    write_markdown(args.report or _default_md_path(args.out), result)
    print(json.dumps({"decision": result["decision"], "reasons": result["reasons"]}))

    if result["decision"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
