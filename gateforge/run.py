from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .change_apply import apply_change_set
from .core import OM_SOURCE_ROOT_ENV, PROJECT_ROOT
from .core import run_pipeline
from .policy import DEFAULT_POLICY_PATH, evaluate_policy, load_policy
from .proposal import EXECUTION_ACTIONS, load_proposal, validate_proposal
from .regression import compare_evidence, load_json, write_json, write_markdown

DEFAULT_BASELINE_INDEX = "baselines/index.json"


def _write_run_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Proposal Run",
        "",
        f"- proposal_id: `{summary['proposal_id']}`",
        f"- status: `{summary['status']}`",
        f"- risk_level: `{summary.get('risk_level')}`",
        f"- policy_decision: `{summary.get('policy_decision')}`",
        f"- actions: `{','.join(summary['actions'])}`",
        f"- smoke_executed: `{summary['smoke_executed']}`",
        f"- regress_executed: `{summary['regress_executed']}`",
        f"- change_set_path: `{summary.get('change_set_path')}`",
        f"- change_apply_status: `{summary.get('change_apply_status')}`",
        f"- change_set_hash: `{summary.get('change_set_hash')}`",
        "",
    ]
    if summary.get("candidate_path"):
        lines.append(f"- candidate_path: `{summary['candidate_path']}`")
    if summary.get("baseline_path"):
        lines.append(f"- baseline_path: `{summary['baseline_path']}`")
    if summary.get("regression_path"):
        lines.append(f"- regression_path: `{summary['regression_path']}`")
    lines.extend(["", "## Fail Reasons", ""])
    if summary["fail_reasons"]:
        lines.extend([f"- `{r}`" for r in summary["fail_reasons"]])
    else:
        lines.append("- `none`")
    lines.append("")
    lines.extend(["## Policy Reasons", ""])
    if summary.get("policy_reasons"):
        lines.extend([f"- `{r}`" for r in summary["policy_reasons"]])
    else:
        lines.append("- `none`")
    lines.append("")
    lines.extend(["## Human Hints", ""])
    if summary.get("human_hints"):
        lines.extend([f"- {h}" for h in summary["human_hints"]])
    else:
        lines.append("- `none`")
    lines.append("")
    lines.extend(["## Applied Changes", ""])
    if summary.get("applied_changes"):
        lines.extend([f"- `{c.get('file')}` ({c.get('op')})" for c in summary["applied_changes"]])
    else:
        lines.append("- `none`")
    lines.append("")
    lines.extend(["## Required Human Checks", ""])
    if summary.get("required_human_checks"):
        lines.extend([f"- {h}" for h in summary["required_human_checks"]])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _resolve_baseline_path(
    baseline_arg: str,
    baseline_index_path: str,
    backend: str,
    script_path: str,
) -> str:
    if baseline_arg != "auto":
        return baseline_arg
    try:
        index_payload = json.loads(Path(baseline_index_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Baseline index not found: {baseline_index_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Baseline index is not valid JSON: {baseline_index_path}") from exc
    entries = index_payload.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("baseline index must define an 'entries' list")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("backend") == backend and entry.get("model_script") == script_path:
            baseline = entry.get("baseline")
            if isinstance(baseline, str) and baseline:
                return baseline
    raise ValueError(
        f"No baseline mapping found for backend={backend}, model_script={script_path} in {baseline_index_path}"
    )


def _apply_proposal_constraints(result: dict, baseline: dict, candidate: dict, backend: str, script: str) -> None:
    if baseline.get("backend") != backend:
        result["reasons"].append("proposal_backend_mismatch_baseline")
    if candidate.get("backend") != backend:
        result["reasons"].append("proposal_backend_mismatch_candidate")
    if baseline.get("model_script") != script:
        result["reasons"].append("proposal_model_script_mismatch_baseline")
    if candidate.get("model_script") != script:
        result["reasons"].append("proposal_model_script_mismatch_candidate")
    if result["reasons"]:
        result["decision"] = "FAIL"


def _human_hints_for_candidate(candidate: dict | None, backend: str) -> list[str]:
    if not candidate:
        return []
    if candidate.get("failure_type") != "docker_error":
        return []
    hints = [
        "Docker backend execution failed. Start Docker Desktop and verify `docker ps` works.",
        f"Re-run the same proposal after Docker is healthy (backend: {backend}).",
    ]
    log_excerpt = candidate.get("artifacts", {}).get("log_excerpt", "")
    if "permission denied" in log_excerpt.lower():
        hints.append("Docker socket permission issue detected. Check current user access to Docker daemon.")
    return hints


def _required_human_checks(policy_decision: str, policy_reasons: list[str], candidate: dict | None) -> list[str]:
    checks: list[str] = []
    if policy_decision == "PASS":
        return checks

    if any("runtime_regression" in reason for reason in policy_reasons):
        checks.append("Review runtime trend and confirm the regression is acceptable for this change.")
        checks.append("Compare baseline/candidate evidence and attach justification before merge.")
    if any("proposal_model_script_mismatch" in reason or "proposal_backend_mismatch" in reason for reason in policy_reasons):
        checks.append("Verify proposal target, baseline mapping, and candidate model_script/backend alignment.")
    if "candidate_gate_not_pass" in policy_reasons:
        checks.append("Inspect candidate failure_type and log_excerpt, then classify root cause.")
    if "change_apply_failed" in policy_reasons:
        checks.append("Inspect change_set_path and confirm each replace_text old/new fragment matches target files.")
        checks.append("Regenerate or fix the change_set, then rerun proposal before merge.")
    if candidate and candidate.get("failure_type") == "docker_error":
        checks.append("Fix Docker backend availability before rerunning this proposal.")

    if not checks:
        checks.append("Human review required: inspect policy_reasons and evidence artifacts before merge.")
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GateForge pipeline from a proposal")
    parser.add_argument("--proposal", required=True, help="Path to proposal JSON")
    parser.add_argument(
        "--out",
        default="artifacts/proposal_run.json",
        help="Where to write proposal-run summary JSON",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Where to write proposal-run markdown report",
    )
    parser.add_argument(
        "--candidate-out",
        default="artifacts/candidate_from_proposal.json",
        help="Where to write candidate evidence when execution actions are present",
    )
    parser.add_argument(
        "--candidate-in",
        default=None,
        help="Existing candidate evidence path (used when proposal requests regress without execution actions)",
    )
    parser.add_argument(
        "--baseline",
        default="auto",
        help="Baseline evidence path for regress action, or 'auto' to resolve by proposal backend/model_script",
    )
    parser.add_argument(
        "--baseline-index",
        default=DEFAULT_BASELINE_INDEX,
        help="Baseline index JSON used when --baseline=auto",
    )
    parser.add_argument(
        "--regression-out",
        default="artifacts/regression_from_proposal.json",
        help="Where to write regression JSON",
    )
    parser.add_argument(
        "--runtime-threshold",
        type=float,
        default=0.2,
        help="Allowed runtime regression ratio (0.2 = +20%%)",
    )
    parser.add_argument(
        "--policy",
        default=DEFAULT_POLICY_PATH,
        help="Policy JSON path for proposal risk-based decision",
    )
    args = parser.parse_args()

    proposal = load_proposal(args.proposal)
    validate_proposal(proposal)
    actions = proposal["requested_actions"]
    action_set = set(actions)

    backend = proposal["backend"]
    script_path = proposal["model_script"]

    summary = {
        "proposal_id": proposal["proposal_id"],
        "risk_level": proposal["risk_level"],
        "actions": actions,
        "status": "PASS",
        "policy_decision": "PASS",
        "policy_reasons": [],
        "policy_path": args.policy,
        "smoke_executed": False,
        "regress_executed": False,
        "candidate_path": None,
        "baseline_path": None,
        "regression_path": None,
        "fail_reasons": [],
        "human_hints": [],
        "required_human_checks": [],
        "change_set_path": proposal.get("change_set_path"),
        "change_apply_status": "not_requested",
        "change_set_hash": None,
        "applied_changes": [],
    }

    candidate = None
    execution_requested = bool(action_set.intersection(EXECUTION_ACTIONS))
    source_override_tmp: tempfile.TemporaryDirectory[str] | None = None
    previous_source_root = os.environ.get(OM_SOURCE_ROOT_ENV)
    try:
        if execution_requested and proposal.get("change_set_path"):
            try:
                source_override_tmp = tempfile.TemporaryDirectory(prefix="gateforge-change-set-")
                tmp_root = Path(source_override_tmp.name)
                shutil.copytree(PROJECT_ROOT / "examples", tmp_root / "examples")
                change_result = apply_change_set(
                    path=proposal["change_set_path"],
                    workspace_root=tmp_root,
                )
                summary["change_apply_status"] = "applied"
                summary["change_set_hash"] = change_result["change_set_hash"]
                summary["applied_changes"] = change_result["applied_changes"]
                os.environ[OM_SOURCE_ROOT_ENV] = str(tmp_root)
            except Exception as exc:  # pragma: no cover - guarded by tests through summary behavior
                summary["change_apply_status"] = "failed"
                summary["fail_reasons"].append("change_apply_failed")
                summary["human_hints"].append(f"Change-set apply failed: {exc}")

        if execution_requested and summary["change_apply_status"] != "failed":
            candidate = run_pipeline(
                backend=backend,
                out_path=args.candidate_out,
                script_path=script_path,
                proposal_id=proposal["proposal_id"],
            )
            summary["smoke_executed"] = True
            summary["candidate_path"] = args.candidate_out
            if candidate["gate"] != "PASS":
                summary["fail_reasons"].append("candidate_gate_not_pass")

        if "regress" in action_set:
            if candidate is None:
                if summary["change_apply_status"] == "failed":
                    summary["regress_executed"] = False
                else:
                    if not args.candidate_in:
                        raise SystemExit("--candidate-in is required when regress is requested without execution actions")
                    candidate = load_json(args.candidate_in)
                    summary["candidate_path"] = args.candidate_in

            if candidate is not None:
                try:
                    baseline_path = _resolve_baseline_path(
                        baseline_arg=args.baseline,
                        baseline_index_path=args.baseline_index,
                        backend=backend,
                        script_path=script_path,
                    )
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc
                baseline = load_json(baseline_path)
                result = compare_evidence(
                    baseline=baseline,
                    candidate=candidate,
                    runtime_regression_threshold=args.runtime_threshold,
                    strict=True,
                    strict_model_script=True,
                )
                _apply_proposal_constraints(result, baseline, candidate, backend=backend, script=script_path)
                result["proposal_id"] = proposal["proposal_id"]
                result["proposal_expected_backend"] = backend
                result["proposal_expected_model_script"] = script_path
                write_json(args.regression_out, result)
                write_markdown(_default_md_path(args.regression_out), result)
                summary["regress_executed"] = True
                summary["regression_path"] = args.regression_out
                summary["baseline_path"] = baseline_path
                if result["decision"] != "PASS":
                    summary["fail_reasons"].append("regression_fail")

        combined_reasons: list[str] = []
        if summary["change_apply_status"] == "failed":
            combined_reasons.append("change_apply_failed")
        if candidate is not None and candidate["gate"] != "PASS":
            combined_reasons.append("candidate_gate_not_pass")
        if summary.get("regression_path"):
            regression_payload = load_json(summary["regression_path"])
            combined_reasons.extend(regression_payload.get("reasons", []))
        combined_reasons = list(dict.fromkeys(combined_reasons))

        policy = load_policy(args.policy)
        policy_result = evaluate_policy(
            reasons=combined_reasons,
            risk_level=proposal["risk_level"],
            policy=policy,
        )
        summary["policy_decision"] = policy_result["policy_decision"]
        summary["policy_reasons"] = policy_result["policy_reasons"]
        summary["status"] = policy_result["policy_decision"]
        summary["human_hints"].extend(_human_hints_for_candidate(candidate, backend=backend))
        summary["required_human_checks"] = _required_human_checks(
            policy_decision=summary["policy_decision"],
            policy_reasons=summary["policy_reasons"],
            candidate=candidate,
        )
    finally:
        if previous_source_root is None:
            os.environ.pop(OM_SOURCE_ROOT_ENV, None)
        else:
            os.environ[OM_SOURCE_ROOT_ENV] = previous_source_root
        if source_override_tmp is not None:
            source_override_tmp.cleanup()

    write_json(args.out, summary)
    _write_run_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"proposal_id": summary["proposal_id"], "status": summary["status"]}))

    if summary["status"] == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
