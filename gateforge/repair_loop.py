from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
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
    before = summary.get("before", {})
    after = summary.get("after", {})
    comparison = summary.get("comparison", {})
    lines = [
        "# GateForge Repair Loop Summary",
        "",
        f"- status: `{summary.get('status')}`",
        f"- planner_backend: `{summary.get('planner_backend')}`",
        f"- source_path: `{summary.get('source_path')}`",
        f"- source_kind: `{summary.get('source_kind')}`",
        f"- source_proposal_id: `{summary.get('source_proposal_id')}`",
        f"- goal: `{summary.get('goal')}`",
        f"- planner_guardrail_decision: `{summary.get('planner_guardrail_decision')}`",
        f"- planner_guardrail_report_path: `{summary.get('planner_guardrail_report_path')}`",
        f"- retry_used: `{summary.get('retry_used')}`",
        "",
        "## Before",
        "",
        f"- status: `{before.get('status')}`",
        f"- policy_decision: `{before.get('policy_decision')}`",
        f"- reasons_count: `{len(before.get('reasons', []))}`",
        "",
        "## After",
        "",
        f"- status: `{after.get('status')}`",
        f"- policy_decision: `{after.get('policy_decision')}`",
        f"- reasons_count: `{len(after.get('reasons', []))}`",
        f"- autopilot_summary_path: `{after.get('autopilot_summary_path')}`",
        "",
        "## Comparison",
        "",
        f"- delta: `{comparison.get('delta')}`",
        f"- score_before: `{comparison.get('score_before')}`",
        f"- score_after: `{comparison.get('score_after')}`",
        "",
        "### Fixed Reasons",
        "",
    ]
    fixed = comparison.get("fixed_reasons", [])
    if fixed:
        lines.extend([f"- `{r}`" for r in fixed])
    else:
        lines.append("- `none`")
    lines.extend(["", "### New Reasons", ""])
    new = comparison.get("new_reasons", [])
    if new:
        lines.extend([f"- `{r}`" for r in new])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Planner Guardrail Violations", ""])
    violations = summary.get("planner_guardrail_violations", [])
    if violations:
        lines.extend([f"- `{item}`" for item in violations])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Attempts", ""])
    attempts = summary.get("attempts", [])
    if attempts:
        for item in attempts:
            lines.append(
                f"- attempt#{item.get('attempt')}: backend=`{item.get('planner_backend')}` "
                f"status=`{item.get('status')}` exit_code=`{item.get('exit_code')}`"
            )
    else:
        lines.append("- `none`")
    lines.extend(["", "## Retry Analysis", ""])
    retry_analysis = summary.get("retry_analysis", {})
    if retry_analysis:
        lines.append(f"- selected_attempt: `{retry_analysis.get('selected_attempt')}`")
        lines.append(f"- first_attempt_status: `{retry_analysis.get('first_attempt_status')}`")
        lines.append(f"- selected_attempt_status: `{retry_analysis.get('selected_attempt_status')}`")
        lines.append(f"- recovered_by_retry: `{retry_analysis.get('recovered_by_retry')}`")
        fixed = retry_analysis.get("fixed_guardrail_rule_ids", [])
        new = retry_analysis.get("new_guardrail_rule_ids", [])
        lines.append(f"- fixed_guardrail_rule_ids: `{','.join(fixed) if fixed else 'none'}`")
        lines.append(f"- new_guardrail_rule_ids: `{','.join(new) if new else 'none'}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _collect_reasons(payload: dict) -> list[str]:
    for key in ("policy_reasons", "fail_reasons", "reasons"):
        value = payload.get(key)
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, str)]
    return []


def _source_kind(payload: dict) -> str:
    if "policy_decision" in payload and "fail_reasons" in payload:
        return "run_summary"
    if "decision" in payload and "reasons" in payload:
        return "regression"
    return "unknown"


def _normalize_before(payload: dict) -> dict:
    kind = _source_kind(payload)
    status = payload.get("status")
    policy_decision = payload.get("policy_decision")
    if status is None and isinstance(payload.get("decision"), str):
        status = payload.get("decision")
    if policy_decision is None and isinstance(payload.get("decision"), str):
        policy_decision = payload.get("decision")
    return {
        "source_kind": kind,
        "proposal_id": payload.get("proposal_id"),
        "status": status or "UNKNOWN",
        "policy_decision": policy_decision or "UNKNOWN",
        "reasons": _collect_reasons(payload),
    }


def _status_score(status: str | None) -> int:
    value = (status or "").upper()
    if value == "PASS":
        return 2
    if value == "NEEDS_REVIEW":
        return 1
    if value == "FAIL":
        return 0
    return -1


def _default_goal(before: dict) -> str:
    return (
        "Repair failed governance gate and run demo mock pass under policy constraints. "
        "Focus on stable, low-risk fix."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fail -> repair proposal -> rerun loop through autopilot")
    parser.add_argument("--source", required=True, help="Path to fail run summary or regression JSON")
    parser.add_argument("--goal", default=None, help="Optional explicit repair goal")
    parser.add_argument(
        "--planner-backend",
        default="rule",
        choices=["rule", "gemini", "openai"],
        help="Planner backend for repair proposal generation",
    )
    parser.add_argument("--proposal-id", default=None, help="Optional explicit proposal_id for repaired run")
    parser.add_argument("--baseline", default="auto", help="Baseline evidence path (or auto)")
    parser.add_argument("--baseline-index", default="baselines/index.json", help="Baseline index JSON path")
    parser.add_argument("--runtime-threshold", type=float, default=0.2, help="Runtime regression ratio threshold")
    parser.add_argument("--policy", default=None, help="Optional policy JSON path")
    parser.add_argument("--policy-profile", default=None, help="Optional policy profile name")
    parser.add_argument(
        "--save-run-under",
        default="autopilot",
        choices=["autopilot", "agent"],
        help="Artifacts namespace for repaired run",
    )
    parser.add_argument(
        "--planner-change-plan-confidence-min",
        type=float,
        default=0.5,
        help="Forwarded to autopilot planner guardrail for minimum change_plan confidence",
    )
    parser.add_argument(
        "--planner-change-plan-confidence-max",
        type=float,
        default=1.0,
        help="Forwarded to autopilot planner guardrail for maximum change_plan confidence",
    )
    parser.add_argument(
        "--planner-change-plan-allowed-file",
        action="append",
        default=None,
        help="Forwarded planner file whitelist for change_plan/change_set files (repeatable)",
    )
    parser.add_argument(
        "--retry-on-failed-attempt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="If first repair attempt fails, allow fallback retries",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Maximum number of fallback retries after first failed attempt",
    )
    parser.add_argument(
        "--retry-fallback-planner-backend",
        choices=["rule", "gemini", "openai"],
        default="rule",
        help="Planner backend for conservative retry",
    )
    parser.add_argument(
        "--retry-confidence-min",
        type=float,
        default=0.8,
        help="Minimum planner confidence for conservative retry",
    )
    parser.add_argument(
        "--retry-allowed-file",
        action="append",
        default=None,
        help="Allowed planner file whitelist for conservative retry (repeatable)",
    )
    parser.add_argument(
        "--out",
        default="artifacts/repair_loop/repair_loop_summary.json",
        help="Where to write repair-loop summary JSON",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Where to write repair-loop summary markdown",
    )
    args = parser.parse_args()
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be >= 0")

    source_payload = json.loads(Path(args.source).read_text(encoding="utf-8"))
    before = _normalize_before(source_payload)
    goal = args.goal or _default_goal(before)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        context_path = tmp.name
        json.dump(
            {
                "risk_level": "low",
                "change_summary": (
                    f"Repair loop from {before['source_kind']} status={before['status']} "
                    f"policy_decision={before['policy_decision']} reasons={before['reasons']}"
                ),
            },
            tmp,
        )

    out_path = Path(args.out)
    run_dir = out_path.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    autopilot_out = str(run_dir / "autopilot_after.json")
    autopilot_report = str(run_dir / "autopilot_after.md")
    autopilot_intent_out = str(run_dir / "autopilot_intent.json")
    autopilot_agent_run_out = str(run_dir / "autopilot_agent_run.json")

    def _build_autopilot_cmd(
        *,
        planner_backend: str,
        proposal_id: str | None,
        conf_min: float,
        conf_max: float,
        allowed_files: list[str] | None,
        out_json: str,
        out_md: str,
        intent_out: str,
        agent_run_out: str,
    ) -> list[str]:
        cmd = [
            sys.executable,
            "-m",
            "gateforge.autopilot",
            "--goal",
            goal,
            "--planner-backend",
            planner_backend,
            "--context-json",
            context_path,
            "--baseline",
            args.baseline,
            "--baseline-index",
            args.baseline_index,
            "--runtime-threshold",
            str(args.runtime_threshold),
            "--save-run-under",
            args.save_run_under,
            "--planner-change-plan-confidence-min",
            str(conf_min),
            "--planner-change-plan-confidence-max",
            str(conf_max),
            "--intent-out",
            intent_out,
            "--agent-run-out",
            agent_run_out,
            "--out",
            out_json,
            "--report",
            out_md,
        ]
        if proposal_id:
            cmd.extend(["--proposal-id", proposal_id])
        if args.policy:
            cmd.extend(["--policy", args.policy])
        if args.policy_profile:
            cmd.extend(["--policy-profile", args.policy_profile])
        for file_path in allowed_files or []:
            cmd.extend(["--planner-change-plan-allowed-file", file_path])
        return cmd

    attempts: list[dict] = []
    cmd = _build_autopilot_cmd(
        planner_backend=args.planner_backend,
        proposal_id=args.proposal_id,
        conf_min=args.planner_change_plan_confidence_min,
        conf_max=args.planner_change_plan_confidence_max,
        allowed_files=args.planner_change_plan_allowed_file,
        out_json=autopilot_out,
        out_md=autopilot_report,
        intent_out=autopilot_intent_out,
        agent_run_out=autopilot_agent_run_out,
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    after_payload = {}
    if Path(autopilot_out).exists():
        after_payload = json.loads(Path(autopilot_out).read_text(encoding="utf-8"))
    attempts.append(
        {
            "attempt": 1,
            "planner_backend": args.planner_backend,
            "exit_code": proc.returncode,
            "status": after_payload.get("status"),
            "planner_guardrail_decision": after_payload.get("planner_guardrail_decision"),
            "planner_guardrail_violations": after_payload.get("planner_guardrail_violations", []),
            "planner_guardrail_violation_objects": after_payload.get("planner_guardrail_violation_objects", []),
            "summary_path": autopilot_out,
            "report_path": autopilot_report,
            "intent_path": autopilot_intent_out,
            "agent_run_path": autopilot_agent_run_out,
        }
    )

    retry_used = False
    retry_proc = None
    selected_attempt = 1
    max_retries = args.max_retries if args.retry_on_failed_attempt else 0
    retry_allowed_files = args.retry_allowed_file or ["examples/openmodelica/MinimalProbe.mo"]
    for retry_index in range(1, max_retries + 1):
        if proc.returncode == 0:
            break
        retry_used = True
        retry_out = str(run_dir / f"autopilot_after_retry_{retry_index}.json")
        retry_report = str(run_dir / f"autopilot_after_retry_{retry_index}.md")
        retry_intent_out = str(run_dir / f"autopilot_intent_retry_{retry_index}.json")
        retry_agent_run_out = str(run_dir / f"autopilot_agent_run_retry_{retry_index}.json")
        retry_cmd = _build_autopilot_cmd(
            planner_backend=args.retry_fallback_planner_backend,
            proposal_id=f"{args.proposal_id}-retry{retry_index}" if args.proposal_id else None,
            conf_min=max(args.planner_change_plan_confidence_min, args.retry_confidence_min),
            conf_max=args.planner_change_plan_confidence_max,
            allowed_files=retry_allowed_files,
            out_json=retry_out,
            out_md=retry_report,
            intent_out=retry_intent_out,
            agent_run_out=retry_agent_run_out,
        )
        retry_proc = subprocess.run(retry_cmd, capture_output=True, text=True, check=False)
        retry_payload = {}
        if Path(retry_out).exists():
            retry_payload = json.loads(Path(retry_out).read_text(encoding="utf-8"))
        attempts.append(
            {
                "attempt": retry_index + 1,
                "planner_backend": args.retry_fallback_planner_backend,
                "exit_code": retry_proc.returncode,
                "status": retry_payload.get("status"),
                "planner_guardrail_decision": retry_payload.get("planner_guardrail_decision"),
                "planner_guardrail_violations": retry_payload.get("planner_guardrail_violations", []),
                "planner_guardrail_violation_objects": retry_payload.get("planner_guardrail_violation_objects", []),
                "summary_path": retry_out,
                "report_path": retry_report,
                "intent_path": retry_intent_out,
                "agent_run_path": retry_agent_run_out,
            }
        )
        if retry_payload and _status_score(
            retry_payload.get("policy_decision") or retry_payload.get("status")
        ) >= _status_score(after_payload.get("policy_decision") or after_payload.get("status")):
            after_payload = retry_payload
            proc = retry_proc
            selected_attempt = retry_index + 1

    selected_attempt_payload = next((a for a in attempts if a.get("attempt") == selected_attempt), attempts[0])
    after = {
        "proposal_id": after_payload.get("proposal_id"),
        "status": after_payload.get("status", "UNKNOWN"),
        "policy_decision": after_payload.get("policy_decision", "UNKNOWN"),
        "reasons": (
            after_payload.get("policy_reasons")
            if isinstance(after_payload.get("policy_reasons"), list)
            else after_payload.get("fail_reasons", [])
        ),
        "autopilot_summary_path": selected_attempt_payload.get("summary_path"),
        "autopilot_report_path": selected_attempt_payload.get("report_path"),
        "autopilot_intent_path": selected_attempt_payload.get("intent_path"),
        "autopilot_agent_run_path": selected_attempt_payload.get("agent_run_path"),
        "autopilot_exit_code": proc.returncode,
    }
    before_reasons = set(before.get("reasons", []))
    after_reasons = set(after.get("reasons", []))
    score_before = _status_score(before.get("policy_decision") or before.get("status"))
    score_after = _status_score(after.get("policy_decision") or after.get("status"))
    if score_after > score_before:
        delta = "improved"
    elif score_after < score_before:
        delta = "worse"
    else:
        delta = "unchanged"

    summary = {
        "status": after.get("status"),
        "planner_backend": args.planner_backend,
        "source_path": args.source,
        "source_kind": before.get("source_kind"),
        "source_proposal_id": before.get("proposal_id"),
        "goal": goal,
        "planner_change_plan_confidence_min": args.planner_change_plan_confidence_min,
        "planner_change_plan_confidence_max": args.planner_change_plan_confidence_max,
        "planner_change_plan_allowed_files": args.planner_change_plan_allowed_file or [],
        "planner_guardrail_decision": after_payload.get("planner_guardrail_decision"),
        "planner_guardrail_violations": after_payload.get("planner_guardrail_violations", []),
        "planner_guardrail_violation_objects": after_payload.get("planner_guardrail_violation_objects", []),
        "planner_guardrail_report_path": after_payload.get("planner_guardrail_report_path"),
        "retry_on_failed_attempt": args.retry_on_failed_attempt,
        "max_retries": args.max_retries,
        "retry_used": retry_used,
        "selected_attempt": selected_attempt,
        "attempts": attempts,
        "before": before,
        "after": after,
        "comparison": {
            "delta": delta,
            "score_before": score_before,
            "score_after": score_after,
            "fixed_reasons": sorted(before_reasons - after_reasons),
            "new_reasons": sorted(after_reasons - before_reasons),
        },
    }
    if attempts:
        first = attempts[0]
        selected = next((a for a in attempts if a.get("attempt") == selected_attempt), attempts[-1])
        first_rules = {
            item.get("rule_id")
            for item in (first.get("planner_guardrail_violation_objects") or [])
            if isinstance(item, dict) and isinstance(item.get("rule_id"), str)
        }
        selected_rules = {
            item.get("rule_id")
            for item in (selected.get("planner_guardrail_violation_objects") or [])
            if isinstance(item, dict) and isinstance(item.get("rule_id"), str)
        }
        summary["retry_analysis"] = {
            "selected_attempt": selected.get("attempt"),
            "first_attempt_status": first.get("status"),
            "selected_attempt_status": selected.get("status"),
            "recovered_by_retry": bool(retry_used and selected.get("attempt") != first.get("attempt")),
            "fixed_guardrail_rule_ids": sorted(first_rules - selected_rules),
            "new_guardrail_rule_ids": sorted(selected_rules - first_rules),
        }
    if proc.returncode != 0:
        summary["autopilot_stderr_tail"] = (proc.stderr or proc.stdout)[-800:]
    if retry_proc is not None and retry_proc.returncode != 0:
        summary["retry_stderr_tail"] = (retry_proc.stderr or retry_proc.stdout)[-800:]

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "delta": summary["comparison"]["delta"],
                "planner_backend": args.planner_backend,
            }
        )
    )
    if proc.returncode != 0:
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
