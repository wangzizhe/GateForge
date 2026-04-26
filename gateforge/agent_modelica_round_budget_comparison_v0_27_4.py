from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_slice_review_v0_27_2 import classify_omc_feedback, load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TWO_ROUND_RESULTS = REPO_ROOT / "artifacts" / "deepseek_source_backed_slice_v0_27_1" / "results.jsonl"
DEFAULT_THREE_ROUND_RESULTS = REPO_ROOT / "artifacts" / "deepseek_three_round_slice_v0_27_3" / "results.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "round_budget_comparison_v0_27_4"


def _by_case_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("case_id") or ""): row for row in rows if row.get("case_id")}


def _attempts(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [attempt for attempt in row.get("attempts", []) if isinstance(attempt, dict)]


def _terminal_feedback(row: dict[str, Any]) -> str:
    attempts = [attempt for attempt in _attempts(row) if attempt.get("llm_called")]
    if not attempts:
        return "no_repair_attempt"
    attempt = attempts[-1]
    return classify_omc_feedback(
        str(attempt.get("raw_omc_after_patch") or ""),
        check_pass=attempt.get("check_pass_after_patch"),
    )


def _added_round_stalled(two_round: dict[str, Any], three_round: dict[str, Any]) -> bool:
    two_count = int(two_round.get("repair_round_count") or 0)
    for attempt in _attempts(three_round):
        if int(attempt.get("round") or 0) > two_count and attempt.get("llm_called"):
            return bool(attempt.get("patched_text_present")) and not bool(attempt.get("model_changed"))
    return False


def compare_round_budget_rows(
    *,
    two_round_rows: list[dict[str, Any]],
    three_round_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    two_by_id = _by_case_id(two_round_rows)
    three_by_id = _by_case_id(three_round_rows)
    common_ids = sorted(set(two_by_id) & set(three_by_id))
    comparisons: list[dict[str, Any]] = []
    for case_id in common_ids:
        two = two_by_id[case_id]
        three = three_by_id[case_id]
        two_pass = str(two.get("final_verdict") or "") == "PASS"
        three_pass = str(three.get("final_verdict") or "") == "PASS"
        if two_pass and not three_pass:
            pass_delta = "regressed"
        elif not two_pass and three_pass:
            pass_delta = "improved"
        elif two_pass and three_pass:
            pass_delta = "preserved_pass"
        else:
            pass_delta = "preserved_fail"
        comparisons.append(
            {
                "case_id": case_id,
                "two_round_verdict": str(two.get("final_verdict") or ""),
                "three_round_verdict": str(three.get("final_verdict") or ""),
                "two_round_repair_round_count": int(two.get("repair_round_count") or 0),
                "three_round_repair_round_count": int(three.get("repair_round_count") or 0),
                "two_round_true_multi_turn": bool(two.get("true_multi_turn")),
                "three_round_true_multi_turn": bool(three.get("true_multi_turn")),
                "two_round_terminal_feedback": _terminal_feedback(two),
                "three_round_terminal_feedback": _terminal_feedback(three),
                "added_round_stalled": _added_round_stalled(two, three),
                "pass_delta": pass_delta,
            }
        )
    improved_count = sum(1 for row in comparisons if row["pass_delta"] == "improved")
    regressed_count = sum(1 for row in comparisons if row["pass_delta"] == "regressed")
    added_round_stall_count = sum(1 for row in comparisons if row["added_round_stalled"])
    two_pass_count = sum(1 for row in comparisons if row["two_round_verdict"] == "PASS")
    three_pass_count = sum(1 for row in comparisons if row["three_round_verdict"] == "PASS")
    summary = {
        "version": "v0.27.4",
        "status": "PASS" if comparisons else "REVIEW",
        "analysis_scope": "deepseek_round_budget_comparison",
        "two_round_artifact": str(DEFAULT_TWO_ROUND_RESULTS.relative_to(REPO_ROOT)),
        "three_round_artifact": str(DEFAULT_THREE_ROUND_RESULTS.relative_to(REPO_ROOT)),
        "common_case_count": len(comparisons),
        "two_round_pass_count": two_pass_count,
        "three_round_pass_count": three_pass_count,
        "improved_count": improved_count,
        "regressed_count": regressed_count,
        "added_round_stall_count": added_round_stall_count,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "do_not_promote_three_round_budget"
            if improved_count == 0 and (regressed_count > 0 or added_round_stall_count > 0)
            else "three_round_budget_needs_more_evidence"
        ),
        "next_focus": "inspect_prompt_and_observation_contract_before_expanding_budget",
    }
    return comparisons, summary


def run_round_budget_comparison(
    *,
    two_round_results: Path = DEFAULT_TWO_ROUND_RESULTS,
    three_round_results: Path = DEFAULT_THREE_ROUND_RESULTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    comparisons, summary = compare_round_budget_rows(
        two_round_rows=load_jsonl(two_round_results),
        three_round_rows=load_jsonl(three_round_results),
    )
    write_outputs(out_dir=out_dir, summary=summary, comparisons=comparisons)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], comparisons: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "case_comparisons.jsonl").open("w", encoding="utf-8") as fh:
        for row in comparisons:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
