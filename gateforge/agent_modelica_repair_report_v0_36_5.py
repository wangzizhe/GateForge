from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "repair_report_v0_36_5"


def _final_eval(result: dict[str, Any]) -> dict[str, Any]:
    for step in reversed(list(result.get("steps") or [])):
        if step.get("step") == "final_eval":
            return step
    return {}


def classify_repair_failure(result: dict[str, Any]) -> str:
    if str(result.get("provider_error") or "").strip():
        return "provider_failure"
    if result.get("final_verdict") == "PASS":
        return "passed"
    if not bool(result.get("submitted")):
        return "no_final_submission"
    final_eval = _final_eval(result)
    if final_eval and not bool(final_eval.get("check_ok")):
        return "final_model_check_failed"
    if final_eval and not bool(final_eval.get("simulate_ok")):
        return "final_simulation_failed"
    return "agent_failed"


def build_repair_report(
    result: dict[str, Any],
    *,
    provider_status: str = "provider_stable",
    trajectory_path: str = "",
) -> dict[str, Any]:
    final_eval = _final_eval(result)
    tool_calls: list[str] = []
    for step in result.get("steps") or []:
        for call in step.get("tool_calls") or []:
            name = str(call.get("name") or "")
            if name:
                tool_calls.append(name)
    failure_category = classify_repair_failure(result)
    return {
        "version": "v0.36.5",
        "analysis_scope": "user_facing_repair_report",
        "case_id": str(result.get("case_id") or ""),
        "model_name": str(result.get("model_name") or ""),
        "provider": str(result.get("provider") or ""),
        "tool_profile": str(result.get("tool_profile") or ""),
        "provider_status": provider_status,
        "final_status": str(result.get("final_verdict") or "FAILED"),
        "submitted": bool(result.get("submitted")),
        "check_ok": bool(final_eval.get("check_ok")) if final_eval else None,
        "simulate_ok": bool(final_eval.get("simulate_ok")) if final_eval else None,
        "step_count": int(result.get("step_count") or len(result.get("steps") or [])),
        "tool_call_sequence": tool_calls,
        "failure_category": failure_category,
        "trajectory_path": trajectory_path,
        "report_markdown": render_repair_report_markdown(
            case_id=str(result.get("case_id") or ""),
            final_status=str(result.get("final_verdict") or "FAILED"),
            provider_status=provider_status,
            submitted=bool(result.get("submitted")),
            failure_category=failure_category,
            trajectory_path=trajectory_path,
            tool_calls=tool_calls,
        ),
    }


def render_repair_report_markdown(
    *,
    case_id: str,
    final_status: str,
    provider_status: str,
    submitted: bool,
    failure_category: str,
    trajectory_path: str,
    tool_calls: list[str],
) -> str:
    calls = ", ".join(tool_calls) if tool_calls else "no tool calls recorded"
    submitted_text = "yes" if submitted else "no"
    lines = [
        f"# GateForge Repair Report: {case_id}",
        "",
        f"- Final status: {final_status}",
        f"- Provider status: {provider_status}",
        f"- Submitted final model: {submitted_text}",
        f"- Failure category: {failure_category}",
        f"- Tool calls: {calls}",
    ]
    if trajectory_path:
        lines.append(f"- Trajectory artifact: {trajectory_path}")
    return "\n".join(lines) + "\n"


def write_repair_report_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    report: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "repair_report.md").write_text(str(report.get("report_markdown") or ""), encoding="utf-8")

