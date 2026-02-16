from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .change_plan import materialize_change_set_from_plan
from .policy import DEFAULT_POLICY_PATH, dry_run_human_checks, load_policy, resolve_policy_path


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
        f"- policy_version: `{summary.get('policy_version')}`",
        f"- policy_profile: `{summary.get('policy_profile')}`",
        f"- checkers: `{','.join(summary.get('checkers', []))}`",
        f"- checker_config: `{json.dumps(summary.get('checker_config', {}), separators=(',', ':'))}`",
        f"- checker_template_path: `{summary.get('checker_template_path')}`",
        f"- generated_change_set_path: `{summary.get('generated_change_set_path')}`",
        f"- generated_change_set_source: `{summary.get('generated_change_set_source')}`",
        f"- planner_guardrail_decision: `{summary.get('planner_guardrail_decision')}`",
        f"- planner_guardrail_report_path: `{summary.get('planner_guardrail_report_path')}`",
        f"- change_apply_status: `{summary.get('change_apply_status')}`",
        f"- applied_changes_count: `{summary.get('applied_changes_count')}`",
        f"- change_set_hash: `{summary.get('change_set_hash')}`",
        f"- change_plan_confidence_min: `{summary.get('change_plan_confidence_min')}`",
        f"- change_plan_confidence_avg: `{summary.get('change_plan_confidence_avg')}`",
        f"- change_plan_confidence_max: `{summary.get('change_plan_confidence_max')}`",
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
    if summary.get("dry_run"):
        lines.extend(["", "## Planned Human Checks (Dry Run)", ""])
        planned_checks = summary.get("planned_required_human_checks", [])
        if planned_checks:
            lines.extend([f"- {check}" for check in planned_checks])
        else:
            lines.append("- `none`")
    lines.extend(["", "## Human Hints", ""])
    human_hints = summary.get("human_hints", [])
    if human_hints:
        lines.extend([f"- {hint}" for hint in human_hints])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Planner Guardrail Violations", ""])
    guardrail_violations = summary.get("planner_guardrail_violations", [])
    if guardrail_violations:
        lines.extend([f"- `{item}`" for item in guardrail_violations])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Governance Guardrails", ""])
    governance_guardrails = summary.get("governance_guardrails", {})
    if isinstance(governance_guardrails, dict) and governance_guardrails:
        lines.append(
            f"- promote_apply_require_ranking_explanation: "
            f"`{governance_guardrails.get('promote_apply_require_ranking_explanation')}`"
        )
        lines.append(
            f"- promote_apply_required_min_top_score_margin: "
            f"`{governance_guardrails.get('promote_apply_required_min_top_score_margin')}`"
        )
        lines.append(
            f"- run_policy_decision: `{governance_guardrails.get('run_policy_decision')}`"
        )
        lines.append(
            f"- run_policy_reasons_count: `{governance_guardrails.get('run_policy_reasons_count')}`"
        )
        lines.append(
            f"- run_required_human_checks_count: `{governance_guardrails.get('run_required_human_checks_count')}`"
        )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _compute_planned_required_checks(intent_payload: dict, policy: dict) -> list[str]:
    overrides = intent_payload.get("overrides") if isinstance(intent_payload, dict) else {}
    if not isinstance(overrides, dict):
        overrides = {}
    risk_level = overrides.get("risk_level", "low")
    has_change_set = bool(overrides.get("change_set_path") or intent_payload.get("change_set_draft"))
    return dry_run_human_checks(policy=policy, risk_level=risk_level, has_change_set=has_change_set)


def _normalize_guardrail_violations(payload: dict) -> tuple[list[str], list[dict]]:
    raw = payload.get("violations", [])
    messages: list[str] = []
    objects: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                msg = item.get("message")
                rid = item.get("rule_id")
                if isinstance(msg, str):
                    messages.append(msg)
                if isinstance(rid, str) or isinstance(msg, str):
                    objects.append({"rule_id": rid, "message": msg})
            elif isinstance(item, str):
                messages.append(item)
                objects.append({"rule_id": None, "message": item})
    explicit = payload.get("violation_messages")
    if isinstance(explicit, list) and explicit:
        messages = [str(x) for x in explicit if isinstance(x, str)]
    return messages, objects


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
    parser.add_argument(
        "--planner-backend",
        default="rule",
        choices=["rule", "openai", "gemini"],
        help="Planner backend passed to llm_planner",
    )
    parser.add_argument(
        "--materialize-change-set",
        action="store_true",
        help="If planner returns change_set_draft, write it and inject change_set_path into intent overrides",
    )
    parser.add_argument(
        "--planner-change-plan-allowed-root",
        action="append",
        default=None,
        help="Allowed root prefix for planner-generated change files (repeatable)",
    )
    parser.add_argument(
        "--planner-change-plan-allowed-suffix",
        action="append",
        default=None,
        help="Allowed file suffix for planner-generated change files (repeatable)",
    )
    parser.add_argument(
        "--planner-change-plan-allowed-file",
        action="append",
        default=None,
        help="Allowed file whitelist for planner-generated change files (repeatable)",
    )
    parser.add_argument(
        "--planner-change-plan-confidence-min",
        type=float,
        default=None,
        help="Reject planner change_plan if min confidence is below this value (default: policy min_confidence_accept)",
    )
    parser.add_argument(
        "--planner-change-plan-confidence-max",
        type=float,
        default=None,
        help="Reject planner change_plan if max confidence is above this value (default: 1.0)",
    )
    parser.add_argument(
        "--emit-checker-template",
        action="store_true",
        help="Emit checker template artifact during run execution",
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
        default=None,
        help=f"Policy JSON path for run (default: {DEFAULT_POLICY_PATH})",
    )
    parser.add_argument(
        "--policy-profile",
        default=None,
        help="Policy profile name under policies/profiles (e.g. industrial_strict_v0)",
    )
    parser.add_argument(
        "--promote-apply-require-ranking-explanation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Record governance guardrail intent: require ranking explanation at promote-apply stage",
    )
    parser.add_argument(
        "--promote-apply-required-min-top-score-margin",
        type=int,
        default=None,
        help="Record governance guardrail intent: minimum top score margin for promote-apply stage",
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
    checker_template_out = str(run_root / "checker_template.json")

    try:
        policy_path = resolve_policy_path(policy_path=args.policy, policy_profile=args.policy_profile)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    policy_payload = load_policy(policy_path)
    resolved_planner_conf_min = (
        float(args.planner_change_plan_confidence_min)
        if args.planner_change_plan_confidence_min is not None
        else float(policy_payload.get("min_confidence_accept", 0.0))
    )
    resolved_planner_conf_max = (
        float(args.planner_change_plan_confidence_max)
        if args.planner_change_plan_confidence_max is not None
        else 1.0
    )
    if resolved_planner_conf_min > resolved_planner_conf_max:
        raise SystemExit("Resolved planner confidence guardrails are invalid: min > max")
    resolved_planner_allowed_roots = (
        list(args.planner_change_plan_allowed_root)
        if args.planner_change_plan_allowed_root
        else list(policy_payload.get("change_set_allowed_roots", []))
    )
    resolved_planner_allowed_suffixes = (
        list(args.planner_change_plan_allowed_suffix)
        if args.planner_change_plan_allowed_suffix
        else list(policy_payload.get("change_set_allowed_suffixes", []))
    )
    resolved_planner_allowed_files = (
        list(args.planner_change_plan_allowed_file)
        if args.planner_change_plan_allowed_file
        else list(policy_payload.get("change_set_allowed_files", []))
    )

    planner_cmd = [
        sys.executable,
        "-m",
        "gateforge.llm_planner",
        "--out",
        args.intent_out,
        "--planner-backend",
        args.planner_backend,
        "--prefer-backend",
        args.prefer_backend,
    ]
    if args.materialize_change_set:
        planner_cmd.append("--emit-change-set-draft")
    if args.goal:
        planner_cmd.extend(["--goal", args.goal])
    if args.goal_file:
        planner_cmd.extend(["--goal-file", args.goal_file])
    if args.context_json:
        planner_cmd.extend(["--context-json", args.context_json])
    if args.proposal_id:
        planner_cmd.extend(["--proposal-id", args.proposal_id])
    planner_cmd.extend(["--change-plan-confidence-min", str(resolved_planner_conf_min)])
    planner_cmd.extend(["--change-plan-confidence-max", str(resolved_planner_conf_max)])
    for root in resolved_planner_allowed_roots:
        planner_cmd.extend(["--change-plan-allowed-root", root])
    guardrail_report_path = str(run_root / "planner_guardrails.json")
    planner_cmd.extend(["--guardrail-report-out", guardrail_report_path])
    for suffix in resolved_planner_allowed_suffixes:
        planner_cmd.extend(["--change-plan-allowed-suffix", suffix])
    for file_path in resolved_planner_allowed_files:
        planner_cmd.extend(["--change-plan-allowed-file", file_path])

    intent_path = Path(args.intent_out)
    intent_pre_exists = intent_path.exists()
    intent_pre_mtime_ns = intent_path.stat().st_mtime_ns if intent_pre_exists else None
    planner_proc = subprocess.run(planner_cmd, capture_output=True, text=True, check=False)

    intent_payload = {}
    planner_succeeded = planner_proc.returncode == 0
    intent_written_this_run = False
    if intent_path.exists():
        if not intent_pre_exists:
            intent_written_this_run = True
        elif intent_pre_mtime_ns is not None and intent_path.stat().st_mtime_ns > intent_pre_mtime_ns:
            intent_written_this_run = True
    if planner_succeeded and intent_path.exists():
        intent_payload = json.loads(intent_path.read_text(encoding="utf-8"))

    generated_change_set_path = None
    generated_change_set_source = None
    if planner_succeeded and args.materialize_change_set:
        generated = None
        if isinstance(intent_payload.get("change_plan"), dict):
            generated = materialize_change_set_from_plan(intent_payload["change_plan"])
            generated_change_set_source = "change_plan"
        elif isinstance(intent_payload.get("change_set_draft"), dict):
            generated = intent_payload["change_set_draft"]
            generated_change_set_source = "change_set_draft"
        if generated is not None:
            generated_change_set_path = str(run_root / "change_set.generated.json")
            _write_json(generated_change_set_path, generated)
            overrides = intent_payload.get("overrides", {})
            if not isinstance(overrides, dict):
                overrides = {}
            overrides["change_set_path"] = generated_change_set_path
            intent_payload["overrides"] = overrides
            _write_json(args.intent_out, intent_payload)

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
        policy_path,
        "--out",
        args.agent_run_out,
    ]
    if args.emit_checker_template:
        agent_cmd.extend(["--emit-checker-template", checker_template_out])
    agent_proc = None
    if planner_succeeded and not args.dry_run:
        agent_proc = subprocess.run(agent_cmd, capture_output=True, text=True, check=False)

    if planner_succeeded and not intent_payload and intent_path.exists():
        intent_payload = json.loads(intent_path.read_text(encoding="utf-8"))
    guardrail_payload = {}
    guardrail_report_file = Path(guardrail_report_path)
    if guardrail_report_file.exists():
        guardrail_payload = json.loads(guardrail_report_file.read_text(encoding="utf-8"))
    guardrail_messages, guardrail_objects = _normalize_guardrail_violations(guardrail_payload)
    agent_payload = {}
    if planner_succeeded and not args.dry_run and Path(args.agent_run_out).exists():
        agent_payload = json.loads(Path(args.agent_run_out).read_text(encoding="utf-8"))

    if args.dry_run or agent_proc is None:
        agent_run_exit_code = None
    else:
        agent_run_exit_code = agent_proc.returncode
    if not planner_succeeded:
        status = "UNKNOWN"
    else:
        status = "PLANNED" if args.dry_run else agent_payload.get("status", "UNKNOWN")
    summary = {
        "intent_path": args.intent_out,
        "agent_run_path": args.agent_run_out,
        "save_run_under": args.save_run_under,
        "dry_run": args.dry_run,
        "planner_exit_code": planner_proc.returncode,
        "planner_succeeded": planner_succeeded,
        "intent_written_this_run": intent_written_this_run,
        "agent_run_exit_code": agent_run_exit_code,
        "planner_backend": args.planner_backend,
        "materialize_change_set": args.materialize_change_set,
        "planner_change_plan_confidence_min": resolved_planner_conf_min,
        "planner_change_plan_confidence_max": resolved_planner_conf_max,
        "planner_change_plan_allowed_roots": resolved_planner_allowed_roots,
        "planner_change_plan_allowed_suffixes": resolved_planner_allowed_suffixes,
        "planner_change_plan_allowed_files": resolved_planner_allowed_files,
        "planner_guardrail_report_path": guardrail_report_path,
        "planner_guardrail_decision": guardrail_payload.get("decision"),
        "planner_guardrail_violations": guardrail_messages,
        "planner_guardrail_violation_objects": guardrail_objects,
        "emit_checker_template": args.emit_checker_template,
        "generated_change_set_path": generated_change_set_path,
        "generated_change_set_source": generated_change_set_source,
        "policy_version": None,
        "policy_profile": args.policy_profile or "default",
        "intent": intent_payload.get("intent"),
        "planner_guardrails": intent_payload.get("planner_inputs", {}).get("change_plan_guardrails")
        if isinstance(intent_payload.get("planner_inputs"), dict)
        else None,
        "proposal_id": agent_payload.get("proposal_id") or intent_payload.get("proposal_id"),
        "status": status,
        "planned_run": {
            "proposal_out": proposal_out,
            "run_out": run_out,
            "run_report": run_report,
            "candidate_out": candidate_out,
            "regression_out": regression_out,
            "checker_template_out": checker_template_out if args.emit_checker_template else None,
            "baseline": args.baseline,
            "baseline_index": args.baseline_index,
            "runtime_threshold": args.runtime_threshold,
            "policy": policy_path,
            "promote_apply_require_ranking_explanation": bool(args.promote_apply_require_ranking_explanation),
            "promote_apply_required_min_top_score_margin": args.promote_apply_required_min_top_score_margin,
        },
    }
    if planner_proc.returncode != 0:
        summary["planner_stderr_tail"] = (planner_proc.stderr or planner_proc.stdout)[-500:]
    if agent_proc is not None and agent_proc.returncode != 0:
        summary["agent_run_stderr_tail"] = (agent_proc.stderr or agent_proc.stdout)[-500:]
    if args.dry_run:
        overrides = intent_payload.get("overrides", {}) if isinstance(intent_payload, dict) else {}
        summary["planned_risk_level"] = (overrides.get("risk_level") if isinstance(overrides, dict) else None) or "low"
        try:
            policy_payload = load_policy(policy_path)
            summary["policy_version"] = policy_payload.get("version")
            summary["planned_required_human_checks"] = _compute_planned_required_checks(
                intent_payload=intent_payload,
                policy=policy_payload,
            )
        except Exception as exc:
            summary["planned_required_human_checks"] = _compute_planned_required_checks(
                intent_payload=intent_payload,
                policy={},
            )
            summary["policy_load_error"] = str(exc)
    if agent_payload:
        summary["policy_version"] = agent_payload.get("policy_version", summary.get("policy_version"))
        summary["policy_profile"] = agent_payload.get("policy_profile", summary.get("policy_profile"))
        summary["policy_decision"] = agent_payload.get("policy_decision")
        summary["checkers"] = agent_payload.get("checkers", [])
        summary["checker_config"] = agent_payload.get("checker_config", {})
        summary["fail_reasons"] = agent_payload.get("fail_reasons", [])
        summary["policy_reasons"] = agent_payload.get("policy_reasons", [])
        summary["human_hints"] = agent_payload.get("human_hints", [])
        summary["required_human_checks"] = agent_payload.get("required_human_checks", [])
        summary["candidate_toolchain"] = agent_payload.get("candidate_toolchain")
        summary["change_apply_status"] = agent_payload.get("change_apply_status")
        summary["change_set_hash"] = agent_payload.get("change_set_hash")
        summary["applied_changes_count"] = agent_payload.get("applied_changes_count")
        summary["change_plan_confidence_min"] = agent_payload.get("change_plan_confidence_min")
        summary["change_plan_confidence_avg"] = agent_payload.get("change_plan_confidence_avg")
        summary["change_plan_confidence_max"] = agent_payload.get("change_plan_confidence_max")
        summary["checker_template_path"] = agent_payload.get("checker_template_path")
        summary["run_path"] = agent_payload.get("run_path")
        summary["run_report_path"] = agent_payload.get("run_report_path")

    summary["governance_guardrails"] = {
        "promote_apply_require_ranking_explanation": bool(args.promote_apply_require_ranking_explanation),
        "promote_apply_required_min_top_score_margin": args.promote_apply_required_min_top_score_margin,
        "run_policy_decision": summary.get("policy_decision"),
        "run_policy_reasons_count": len(summary.get("policy_reasons") or []),
        "run_required_human_checks_count": len(summary.get("required_human_checks") or []),
    }

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
