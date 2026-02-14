from __future__ import annotations

import argparse
import json
from pathlib import Path

from .policy import evaluate_policy, load_policy, resolve_policy_path, run_required_human_checks


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_source(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("run_path"), str):
        run_path = Path(payload["run_path"])
        if run_path.exists():
            return json.loads(run_path.read_text(encoding="utf-8"))
    return payload


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


def _derive_policy_view(payload: dict, policy: dict) -> tuple[str, list[str], str]:
    reasons = _collect_reasons(payload)
    decision = payload.get("policy_decision")
    risk_level = str(payload.get("risk_level") or "low")
    if isinstance(decision, str) and decision in {"PASS", "FAIL", "NEEDS_REVIEW"}:
        return decision, reasons, risk_level
    result = evaluate_policy(reasons, risk_level, policy)
    return str(result.get("policy_decision") or "FAIL"), list(result.get("policy_reasons") or reasons), risk_level


def _build_tasks(payload: dict, policy: dict, policy_decision: str, policy_reasons: list[str]) -> list[dict]:
    tasks: list[dict] = []
    task_id = 1

    def add(category: str, title: str, description: str, source: str) -> None:
        nonlocal task_id
        tasks.append(
            {
                "id": f"T{task_id:03d}",
                "category": category,
                "title": title,
                "description": description,
                "source": source,
            }
        )
        task_id += 1

    add(
        "triage",
        "Classify failure and scope impact",
        "Confirm source summary fields (status/policy_decision/reasons/backend/model_script) and classify failure family.",
        "default",
    )

    if isinstance(payload.get("candidate_path"), str):
        add(
            "evidence",
            "Inspect candidate evidence artifact",
            f"Open candidate evidence JSON at {payload.get('candidate_path')} and verify failure_type/log_excerpt consistency.",
            "candidate_path",
        )
    if isinstance(payload.get("regression_path"), str):
        add(
            "evidence",
            "Inspect regression artifact",
            f"Open regression JSON at {payload.get('regression_path')} and validate reason list/findings.",
            "regression_path",
        )

    failure_type = payload.get("failure_type")
    required_checks = run_required_human_checks(
        policy=policy,
        policy_decision=policy_decision,
        policy_reasons=policy_reasons,
        candidate_failure_type=str(failure_type) if isinstance(failure_type, str) else None,
    )
    for check in required_checks:
        add("required_check", "Required human check", check, "policy.required_human_checks")

    for reason in policy_reasons:
        add(
            "fix_plan",
            f"Address reason: {reason}",
            f"Create targeted fix proposal for `{reason}` and prepare rerun evidence to confirm resolution.",
            "policy_reasons",
        )

    add(
        "validation",
        "Rerun gate after fix",
        "Rerun proposal/check/simulate/regress and verify decision reaches PASS or accepted NEEDS_REVIEW with justification.",
        "default",
    )
    return tasks


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Repair Tasks",
        "",
        f"- proposal_id: `{summary.get('proposal_id')}`",
        f"- source_kind: `{summary.get('source_kind')}`",
        f"- status: `{summary.get('status')}`",
        f"- policy_decision: `{summary.get('policy_decision')}`",
        f"- risk_level: `{summary.get('risk_level')}`",
        f"- policy_path: `{summary.get('policy_path')}`",
        "",
        "## Policy Reasons",
        "",
    ]
    reasons = summary.get("policy_reasons", [])
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Tasks", ""])
    tasks = summary.get("tasks", [])
    if tasks:
        for item in tasks:
            lines.append(
                f"- `{item.get('id')}` [{item.get('category')}] {item.get('title')}: {item.get('description')}"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate actionable repair tasks from failed governance summary")
    parser.add_argument("--source", required=True, help="Path to run/regression/autopilot summary JSON")
    parser.add_argument("--policy", default=None, help="Optional policy JSON path")
    parser.add_argument("--policy-profile", default=None, help="Optional policy profile name")
    parser.add_argument("--out", default="artifacts/repair_tasks/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    policy_path = resolve_policy_path(policy_path=args.policy, policy_profile=args.policy_profile)
    policy = load_policy(policy_path)
    source = _load_source(args.source)

    policy_decision, policy_reasons, risk_level = _derive_policy_view(source, policy)
    tasks = _build_tasks(source, policy, policy_decision, policy_reasons)

    summary = {
        "source_path": args.source,
        "source_kind": _source_kind(source),
        "proposal_id": source.get("proposal_id"),
        "status": source.get("status") or source.get("decision"),
        "policy_decision": policy_decision,
        "policy_reasons": policy_reasons,
        "risk_level": risk_level,
        "policy_path": policy_path,
        "task_count": len(tasks),
        "tasks": tasks,
    }

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"task_count": summary["task_count"], "policy_decision": summary["policy_decision"]}))


if __name__ == "__main__":
    main()
