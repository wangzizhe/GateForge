from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "behavioral_oracle_v0_27_13"

_ALLOWED_VERDICTS = {"behavior_pass", "behavior_error", "infra_error"}

_FORBIDDEN_ORACLE_TERMS = (
    "root_cause",
    "root cause",
    "repair_hint",
    "expected_fix",
    "target_patch",
    "deterministic_diagnosis",
    "routing_decision",
    "you should",
    "try fixing",
    "suggest",
    "recommend",
)


def run_behavioral_oracle(
    *,
    check_ok: bool,
    simulate_ok: bool,
    raw_output: str,
    model_name: str = "",
) -> tuple[str, str]:
    if not check_ok:
        verdict = "infra_error"
        feedback = (
            f"behavioral_oracle_verdict: N/A\n"
            f"model: {model_name}\n"
            f"checkModel: FAIL\n"
            f"reason: behavioral oracle requires checkModel pass to evaluate\n"
        )
        return verdict, feedback

    if not simulate_ok:
        sim_error = _extract_simulation_error(raw_output)
        verdict = "behavior_error"
        feedback = (
            f"behavioral_oracle_verdict: FAIL\n"
            f"model: {model_name}\n"
            f"checkModel: PASS\n"
            f"simulate: FAIL\n"
            f"simulation_error: {sim_error}\n"
        )
        return verdict, feedback

    verdict = "behavior_pass"
    feedback = (
        f"behavioral_oracle_verdict: PASS\n"
        f"model: {model_name}\n"
        f"checkModel: PASS\n"
        f"simulate: PASS\n"
    )
    return verdict, feedback


def _extract_simulation_error(raw_output: str) -> str:
    text = raw_output or ""
    idx = text.find("record SimulationResult")
    if idx < 0:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("error:") or stripped.lower().startswith("warning:"):
                return stripped
        return "simulation_failed_no_detail"
    snippet = text[idx:]
    lines = snippet.splitlines()
    error_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if "error:" in lower and ("too few equations" in lower or "under-determined" in lower or "over-determined" in lower or "too many equations" in lower):
            error_lines.append(stripped)
        elif "warning: variable" in lower and "does not have any remaining equation" in lower:
            error_lines.append(stripped)
        elif "the original equations were:" in lower:
            error_lines.append(stripped)
        elif error_lines and (lower.startswith("equation") or "which needs to solve for" in lower):
            error_lines.append(stripped)
    if error_lines:
        return " ; ".join(error_lines)
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if "error:" in lower:
            return stripped
    return "simulation_failed_no_detail"


def validate_oracle_feedback(feedback: str) -> list[str]:
    errors: list[str] = []
    lowered = feedback.lower()
    for term in _FORBIDDEN_ORACLE_TERMS:
        if term.lower() in lowered:
            errors.append(f"forbidden:{term}")
    return errors


def build_behavioral_oracle_summary(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    check_ok_cases = [
        (True, True, "Check of Demo completed successfully.\nrecord SimulationResult\nresultFile = \"Demo_res.mat\"\nend SimulationResult;", "Demo"),
        (True, False, "Check of Demo completed successfully.\nClass Demo has 5 equation(s) and 6 variable(s).\nrecord SimulationResult\nresultFile = \"\"\nmessages = \"Failed to build model: Demo\"\nend SimulationResult;\n\"Error: Too few equations, under-determined system.\"\n[/tmp/Demo.mo:10:3-10:20:writable] Warning: Variable x does not have any remaining equation to be solved in.", "Demo"),
        (False, False, "model_check_error", "Demo"),
    ]
    results: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    for check_ok, simulate_ok, raw, model_name in check_ok_cases:
        verdict, feedback = run_behavioral_oracle(
            check_ok=check_ok, simulate_ok=simulate_ok, raw_output=raw, model_name=model_name,
        )
        errs = validate_oracle_feedback(feedback)
        validation_errors.extend(errs)
        results.append({"check_ok": check_ok, "simulate_ok": simulate_ok, "verdict": verdict, "feedback": feedback, "validation_errors": errs})
    summary = {
        "version": "v0.27.13",
        "status": "PASS" if not validation_errors else "REVIEW",
        "analysis_scope": "behavioral_oracle_contract",
        "canonical_cases_tested": len(results),
        "validation_errors": validation_errors,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "hint_terms_found": len(validation_errors) > 0,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "behavioral_oracle_ready_for_harness_integration"
            if not validation_errors
            else "behavioral_oracle_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "canonical_results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
