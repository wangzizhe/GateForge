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

    cmd = [
        sys.executable,
        "-m",
        "gateforge.autopilot",
        "--goal",
        goal,
        "--planner-backend",
        args.planner_backend,
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
        "--intent-out",
        autopilot_intent_out,
        "--agent-run-out",
        autopilot_agent_run_out,
        "--out",
        autopilot_out,
        "--report",
        autopilot_report,
    ]
    if args.proposal_id:
        cmd.extend(["--proposal-id", args.proposal_id])
    if args.policy:
        cmd.extend(["--policy", args.policy])
    if args.policy_profile:
        cmd.extend(["--policy-profile", args.policy_profile])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    after_payload = {}
    if Path(autopilot_out).exists():
        after_payload = json.loads(Path(autopilot_out).read_text(encoding="utf-8"))

    after = {
        "proposal_id": after_payload.get("proposal_id"),
        "status": after_payload.get("status", "UNKNOWN"),
        "policy_decision": after_payload.get("policy_decision", "UNKNOWN"),
        "reasons": (
            after_payload.get("policy_reasons")
            if isinstance(after_payload.get("policy_reasons"), list)
            else after_payload.get("fail_reasons", [])
        ),
        "autopilot_summary_path": autopilot_out,
        "autopilot_report_path": autopilot_report,
        "autopilot_intent_path": autopilot_intent_out,
        "autopilot_agent_run_path": autopilot_agent_run_out,
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
    if proc.returncode != 0:
        summary["autopilot_stderr_tail"] = (proc.stderr or proc.stdout)[-800:]

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
