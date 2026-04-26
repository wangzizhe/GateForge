from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_RESULTS = REPO_ROOT / "artifacts" / "deepseek_source_backed_slice_v0_27_1" / "results.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "deepseek_slice_review_v0_27_2"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def classify_omc_feedback(raw_output: str, *, check_pass: bool | None) -> str:
    if check_pass:
        return "none"
    text = raw_output or ""
    lowered = text.lower()
    if "wrong number of subscripts" in lowered:
        return "wrong_number_of_subscripts"
    if "too few equations" in lowered or "under-determined system" in lowered:
        return "underdetermined_system"
    if "too many equations" in lowered or "over-determined system" in lowered:
        return "overdetermined_system"
    if re.search(r"\bclass\b.*\bnot found\b", lowered):
        return "missing_class_or_component"
    if "syntax error" in lowered or "parser error" in lowered:
        return "syntax_error"
    if "error:" in lowered:
        return "other_model_check_error"
    return "unknown_or_empty_feedback"


def _attempt_feedback_label(attempt: dict[str, Any]) -> str:
    return classify_omc_feedback(
        str(attempt.get("raw_omc_after_patch") or ""),
        check_pass=attempt.get("check_pass_after_patch"),
    )


def summarize_case(row: dict[str, Any]) -> dict[str, Any]:
    attempts = [attempt for attempt in row.get("attempts", []) if isinstance(attempt, dict)]
    feedback_sequence = [_attempt_feedback_label(attempt) for attempt in attempts if attempt.get("llm_called")]
    changed_rounds = [int(attempt.get("round") or 0) for attempt in attempts if attempt.get("llm_called") and attempt.get("model_changed")]
    failed_repair_rounds = [
        int(attempt.get("round") or 0)
        for attempt in attempts
        if attempt.get("llm_called") and attempt.get("patched_text_present") and not attempt.get("check_pass_after_patch")
    ]
    final_verdict = str(row.get("final_verdict") or "")
    repair_round_count = int(row.get("repair_round_count") or 0)
    true_multi_turn = final_verdict == "PASS" and repair_round_count >= 2 and bool(failed_repair_rounds)
    terminal_feedback = feedback_sequence[-1] if feedback_sequence else "no_repair_attempt"
    return {
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": final_verdict,
        "repair_round_count": repair_round_count,
        "executor_attempt_count": int(row.get("executor_attempt_count") or len(attempts)),
        "feedback_sequence": feedback_sequence,
        "terminal_feedback": terminal_feedback,
        "changed_rounds": changed_rounds,
        "failed_repair_rounds": failed_repair_rounds,
        "true_multi_turn": true_multi_turn,
        "provider_error": any(str(attempt.get("llm_error") or "") for attempt in attempts),
        "observation_validation_error_count": int(row.get("observation_validation_error_count") or 0),
    }


def build_slice_review_summary(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = [summarize_case(row) for row in rows]
    terminal_counter = Counter(str(case["terminal_feedback"]) for case in cases)
    sequence_counter = Counter(" -> ".join(case["feedback_sequence"]) for case in cases)
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    true_multi_turn_count = sum(1 for case in cases if case["true_multi_turn"])
    provider_error_count = sum(1 for case in cases if case["provider_error"])
    observation_error_count = sum(int(case["observation_validation_error_count"]) for case in cases)
    repeated_failure_signature = ""
    if terminal_counter:
        label, count = terminal_counter.most_common(1)[0]
        if label != "none" and count >= 2:
            repeated_failure_signature = label
    summary = {
        "version": "v0.27.2",
        "status": "PASS" if cases and provider_error_count == 0 and observation_error_count == 0 else "REVIEW",
        "analysis_scope": "deepseek_source_backed_slice_review",
        "input_artifact": str(DEFAULT_INPUT_RESULTS.relative_to(REPO_ROOT)),
        "case_count": len(cases),
        "pass_count": pass_count,
        "provider_error_count": provider_error_count,
        "observation_validation_error_count": observation_error_count,
        "true_multi_turn_count": true_multi_turn_count,
        "terminal_feedback_distribution": dict(sorted(terminal_counter.items())),
        "feedback_sequence_distribution": dict(sorted(sequence_counter.items())),
        "repeated_failure_signature": repeated_failure_signature,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "hold_family_expansion_review_residuals"
            if repeated_failure_signature
            else "slice_ready_for_limited_family_expansion"
        ),
        "next_focus": (
            "rerun_same_slice_with_one_more_raw_feedback_round"
            if repeated_failure_signature
            else "expand_to_cross_family_source_backed_slice"
        ),
    }
    return cases, summary


def run_deepseek_slice_review(
    *,
    input_results: Path = DEFAULT_INPUT_RESULTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(input_results)
    cases, summary = build_slice_review_summary(rows)
    write_outputs(out_dir=out_dir, summary=summary, cases=cases)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "case_reviews.jsonl").open("w", encoding="utf-8") as fh:
        for row in cases:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
