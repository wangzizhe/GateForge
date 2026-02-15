from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .change_apply import apply_change_set, load_change_set
from .checkers import checker_config_template
from .core import OM_SOURCE_ROOT_ENV, PROJECT_ROOT
from .core import run_pipeline
from .policy import (
    DEFAULT_POLICY_PATH,
    evaluate_policy,
    load_policy,
    resolve_policy_path,
    run_required_human_checks,
)
from .preflight import preflight_change_set
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
        f"- policy_profile: `{summary.get('policy_profile')}`",
        f"- policy_version: `{summary.get('policy_version')}`",
        f"- checkers: `{','.join(summary.get('checkers', []))}`",
        f"- checker_config: `{json.dumps(summary.get('checker_config', {}), separators=(',', ':'))}`",
        f"- checker_template_path: `{summary.get('checker_template_path')}`",
        f"- actions: `{','.join(summary['actions'])}`",
        f"- smoke_executed: `{summary['smoke_executed']}`",
        f"- regress_executed: `{summary['regress_executed']}`",
        f"- change_set_path: `{summary.get('change_set_path')}`",
        f"- change_auto_apply_allowed: `{summary.get('change_auto_apply_allowed')}`",
        f"- change_preflight_status: `{summary.get('change_preflight_status')}`",
        f"- change_apply_status: `{summary.get('change_apply_status')}`",
        f"- change_set_hash: `{summary.get('change_set_hash')}`",
        f"- change_ops_count: `{summary.get('change_ops_count')}`",
        f"- change_plan_confidence_min: `{summary.get('change_plan_confidence_min')}`",
        f"- change_plan_confidence_avg: `{summary.get('change_plan_confidence_avg')}`",
        f"- change_plan_confidence_max: `{summary.get('change_plan_confidence_max')}`",
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
    lines.extend(["## Change Preflight", ""])
    preflight_reasons = summary.get("change_preflight_reasons", [])
    if preflight_reasons:
        lines.extend([f"- `{r}`" for r in preflight_reasons])
    else:
        lines.append("- `none`")
    lines.append("")
    lines.extend(["## Change Targets", ""])
    if summary.get("change_targets"):
        lines.extend([f"- `{p}`" for p in summary["change_targets"]])
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
        "--emit-checker-template",
        default=None,
        help="Optional path to write checker_config template inferred from proposal checkers",
    )
    parser.add_argument(
        "--policy",
        default=None,
        help=f"Policy JSON path for proposal risk-based decision (default: {DEFAULT_POLICY_PATH})",
    )
    parser.add_argument(
        "--policy-profile",
        default=None,
        help="Policy profile name under policies/profiles (e.g. industrial_strict_v0)",
    )
    args = parser.parse_args()

    proposal = load_proposal(args.proposal)
    validate_proposal(proposal)
    actions = proposal["requested_actions"]
    action_set = set(actions)

    backend = proposal["backend"]
    script_path = proposal["model_script"]

    try:
        policy_path = resolve_policy_path(policy_path=args.policy, policy_profile=args.policy_profile)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    summary = {
        "proposal_id": proposal["proposal_id"],
        "proposal_author": proposal.get("author"),
        "risk_level": proposal["risk_level"],
        "actions": actions,
        "status": "PASS",
        "policy_decision": "PASS",
        "policy_reasons": [],
        "policy_path": policy_path,
        "policy_version": None,
        "policy_profile": args.policy_profile or "default",
        "checkers": proposal.get("checkers", []),
        "checker_config": _inject_invariants_into_checker_config(proposal.get("checker_config", {}), proposal),
        "checker_template_path": None,
        "smoke_executed": False,
        "regress_executed": False,
        "candidate_path": None,
        "candidate_toolchain": None,
        "baseline_path": None,
        "regression_path": None,
        "fail_reasons": [],
        "human_hints": [],
        "required_human_checks": [],
        "change_set_path": proposal.get("change_set_path"),
        "change_auto_apply_allowed": True,
        "change_preflight_status": "not_requested",
        "change_preflight_reasons": [],
        "change_preflight_hints": [],
        "change_targets": [],
        "change_apply_status": "not_requested",
        "change_set_hash": None,
        "change_ops_count": 0,
        "change_plan_confidence_min": None,
        "change_plan_confidence_avg": None,
        "change_plan_confidence_max": None,
        "applied_changes": [],
        "review_resolution_policy": {},
    }

    candidate = None
    execution_requested = bool(action_set.intersection(EXECUTION_ACTIONS))
    source_override_tmp: tempfile.TemporaryDirectory[str] | None = None
    previous_source_root = os.environ.get(OM_SOURCE_ROOT_ENV)
    try:
        policy = load_policy(policy_path)
        summary["policy_version"] = policy.get("version")
        review_policy = policy.get("review_resolution", {})
        if isinstance(review_policy, dict):
            summary["review_resolution_policy"] = review_policy

        if args.emit_checker_template:
            template_payload = checker_config_template(
                checker_names=proposal.get("checkers"),
                include_runtime=True,
            )
            write_json(args.emit_checker_template, template_payload)
            summary["checker_template_path"] = args.emit_checker_template

        if execution_requested and proposal.get("change_set_path"):
            try:
                allowed_risks = set(policy.get("allow_auto_apply_risk_levels", ["low", "medium"]))
                if proposal["risk_level"] not in allowed_risks:
                    summary["change_auto_apply_allowed"] = False
                    summary["change_apply_status"] = "requires_review"
                    summary["fail_reasons"].append("change_requires_human_review")
                else:
                    summary["change_auto_apply_allowed"] = True

                if summary["change_apply_status"] != "requires_review":
                    source_override_tmp = tempfile.TemporaryDirectory(prefix="gateforge-change-set-")
                    tmp_root = Path(source_override_tmp.name)
                    shutil.copytree(PROJECT_ROOT / "examples", tmp_root / "examples")
                    change_set_payload = load_change_set(proposal["change_set_path"])
                    metadata = change_set_payload.get("metadata", {})
                    summary["change_ops_count"] = len(change_set_payload.get("changes", []))
                    if isinstance(metadata, dict):
                        summary["change_plan_confidence_min"] = metadata.get("plan_confidence_min")
                        summary["change_plan_confidence_avg"] = metadata.get("plan_confidence_avg")
                        summary["change_plan_confidence_max"] = metadata.get("plan_confidence_max")

                    min_conf_auto_apply = float(policy.get("min_confidence_auto_apply", 0.6))
                    min_conf_accept = float(policy.get("min_confidence_accept", 0.3))
                    conf_min = summary["change_plan_confidence_min"]
                    if isinstance(conf_min, (int, float)):
                        if float(conf_min) < min_conf_accept:
                            summary["change_apply_status"] = "rejected_low_confidence"
                            summary["fail_reasons"].append("change_plan_confidence_below_accept")
                        elif float(conf_min) < min_conf_auto_apply:
                            summary["change_apply_status"] = "requires_review"
                            summary["fail_reasons"].append("change_plan_confidence_below_auto_apply")
                            summary["fail_reasons"].append("change_requires_human_review")

                    if summary["change_apply_status"] not in {"requires_review", "rejected_low_confidence"}:
                        preflight = preflight_change_set(
                            change_set=change_set_payload,
                            workspace_root=tmp_root,
                            allowed_roots=policy.get("change_set_allowed_roots", ["examples/openmodelica"]),
                            max_changes=int(policy.get("change_set_max_changes", 20)),
                        )
                        summary["change_preflight_status"] = preflight["status"]
                        summary["change_preflight_reasons"] = preflight["reasons"]
                        summary["change_preflight_hints"] = preflight["hints"]
                        summary["change_targets"] = preflight["targets"]
                        if not preflight["ok"]:
                            summary["change_apply_status"] = "preflight_failed"
                            summary["fail_reasons"].append("change_preflight_failed")
                            summary["human_hints"].extend(preflight["hints"])
                        else:
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

        if execution_requested and summary["change_apply_status"] in {"not_requested", "applied"}:
            candidate = run_pipeline(
                backend=backend,
                out_path=args.candidate_out,
                script_path=script_path,
                proposal_id=proposal["proposal_id"],
                policy_profile=summary["policy_profile"],
                policy_version=summary["policy_version"],
            )
            summary["smoke_executed"] = True
            summary["candidate_path"] = args.candidate_out
            summary["candidate_toolchain"] = candidate.get("toolchain")
            if candidate["gate"] != "PASS":
                summary["fail_reasons"].append("candidate_gate_not_pass")

        if "regress" in action_set:
            if candidate is None:
                if summary["change_apply_status"] in {
                    "failed",
                    "preflight_failed",
                    "requires_review",
                    "rejected_low_confidence",
                }:
                    summary["regress_executed"] = False
                else:
                    if not args.candidate_in:
                        raise SystemExit("--candidate-in is required when regress is requested without execution actions")
                    candidate = load_json(args.candidate_in)
                    summary["candidate_path"] = args.candidate_in
                    summary["candidate_toolchain"] = candidate.get("toolchain")

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
                    checker_names=proposal.get("checkers"),
                    checker_config=_inject_invariants_into_checker_config(
                        proposal.get("checker_config", {}),
                        proposal,
                    ),
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
        if summary["change_apply_status"] == "preflight_failed":
            combined_reasons.append("change_preflight_failed")
        if summary["change_apply_status"] == "requires_review":
            combined_reasons.append("change_requires_human_review")
            if "change_plan_confidence_below_auto_apply" in summary["fail_reasons"]:
                combined_reasons.append("change_plan_confidence_below_auto_apply")
        if summary["change_apply_status"] == "rejected_low_confidence":
            combined_reasons.append("change_plan_confidence_below_accept")
        if candidate is not None and candidate["gate"] != "PASS":
            combined_reasons.append("candidate_gate_not_pass")
        if summary.get("regression_path"):
            regression_payload = load_json(summary["regression_path"])
            combined_reasons.extend(regression_payload.get("reasons", []))
        combined_reasons = list(dict.fromkeys(combined_reasons))

        policy_result = evaluate_policy(
            reasons=combined_reasons,
            risk_level=proposal["risk_level"],
            policy=policy,
        )
        summary["policy_decision"] = policy_result["policy_decision"]
        summary["policy_reasons"] = policy_result["policy_reasons"]
        summary["policy_version"] = policy.get("version")
        summary["status"] = policy_result["policy_decision"]
        summary["human_hints"].extend(_human_hints_for_candidate(candidate, backend=backend))
        summary["required_human_checks"] = run_required_human_checks(
            policy=policy,
            policy_decision=summary["policy_decision"],
            policy_reasons=summary["policy_reasons"],
            candidate_failure_type=(candidate or {}).get("failure_type"),
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
