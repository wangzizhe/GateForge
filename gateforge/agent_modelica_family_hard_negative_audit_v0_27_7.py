from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_slice_review_v0_27_2 import classify_omc_feedback, load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANDIDATES = REPO_ROOT / "artifacts" / "single_point_complex_pack_v0_22_6" / "single_point_candidates.jsonl"
DEFAULT_RESULTS = REPO_ROOT / "artifacts" / "deepseek_transition_history_slice_v0_27_6" / "results.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "family_hard_negative_audit_v0_27_7"


def _by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key) or ""): row for row in rows if row.get(key)}


def _attempt_labels(result: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for attempt in result.get("attempts", []):
        if not isinstance(attempt, dict) or not attempt.get("llm_called"):
            continue
        labels.append(
            classify_omc_feedback(
                str(attempt.get("raw_omc_after_patch") or ""),
                check_pass=attempt.get("check_pass_after_patch"),
            )
        )
    return labels


def _stalled_final_round(result: dict[str, Any]) -> bool:
    attempts = [attempt for attempt in result.get("attempts", []) if isinstance(attempt, dict)]
    if not attempts:
        return False
    last = attempts[-1]
    return bool(last.get("llm_called")) and bool(last.get("patched_text_present")) and not bool(last.get("model_changed"))


def audit_family_hard_negative(
    *,
    candidate_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    family: str = "single_point_resistor_observability_refactor",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = {
        candidate_id: row
        for candidate_id, row in _by_id(candidate_rows, "candidate_id").items()
        if str(row.get("mutation_pattern") or row.get("mutation_family") or "") == family
    }
    results = _by_id(result_rows, "case_id")
    audited: list[dict[str, Any]] = []
    for case_id in sorted(set(candidates) & set(results)):
        candidate = candidates[case_id]
        result = results[case_id]
        labels = _attempt_labels(result)
        terminal = labels[-1] if labels else "no_repair_attempt"
        residual_chain = [str(item) for item in candidate.get("residual_chain", [])]
        final_verdict = str(result.get("final_verdict") or "")
        audited.append(
            {
                "case_id": case_id,
                "source_complexity_class": str(candidate.get("source_complexity_class") or ""),
                "residual_count": int(candidate.get("residual_count") or 0),
                "residual_chain": residual_chain,
                "final_verdict": final_verdict,
                "repair_round_count": int(result.get("repair_round_count") or 0),
                "true_multi_turn": bool(result.get("true_multi_turn")),
                "feedback_sequence": labels,
                "terminal_feedback": terminal,
                "final_round_stalled": _stalled_final_round(result),
                "provider_error": any(str(attempt.get("llm_error") or "") for attempt in result.get("attempts", []) if isinstance(attempt, dict)),
                "hard_negative_signal": (
                    final_verdict != "PASS"
                    and terminal == "underdetermined_system"
                    and _stalled_final_round(result)
                ),
            }
        )
    terminal_counts = Counter(row["terminal_feedback"] for row in audited)
    hard_negative_count = sum(1 for row in audited if row["hard_negative_signal"])
    pass_count = sum(1 for row in audited if row["final_verdict"] == "PASS")
    stalled_count = sum(1 for row in audited if row["final_round_stalled"])
    all_source_backed = all(str(candidates[row["case_id"]].get("source_viability_status") or "") for row in audited)
    summary = {
        "version": "v0.27.7",
        "status": "PASS" if audited else "REVIEW",
        "analysis_scope": "family_hard_negative_audit",
        "family": family,
        "candidate_artifact": str(DEFAULT_CANDIDATES.relative_to(REPO_ROOT)),
        "result_artifact": str(DEFAULT_RESULTS.relative_to(REPO_ROOT)),
        "audited_case_count": len(audited),
        "pass_count": pass_count,
        "hard_negative_signal_count": hard_negative_count,
        "final_round_stall_count": stalled_count,
        "terminal_feedback_distribution": dict(sorted(terminal_counts.items())),
        "all_audited_cases_source_backed": all_source_backed,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "treat_family_as_current_hard_negative"
            if audited and hard_negative_count == len(audited) and pass_count == 0
            else "family_hard_negative_status_needs_more_evidence"
        ),
        "next_focus": "separate_hard_negative_benchmark_role_from_default_capability_eval",
    }
    return audited, summary


def run_family_hard_negative_audit(
    *,
    candidates_path: Path = DEFAULT_CANDIDATES,
    results_path: Path = DEFAULT_RESULTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    cases, summary = audit_family_hard_negative(
        candidate_rows=load_jsonl(candidates_path),
        result_rows=load_jsonl(results_path),
    )
    write_outputs(out_dir=out_dir, summary=summary, cases=cases)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "case_audits.jsonl").open("w", encoding="utf-8") as fh:
        for row in cases:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
