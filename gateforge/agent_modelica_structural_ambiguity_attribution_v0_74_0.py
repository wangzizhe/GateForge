from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "structural_ambiguity_attribution_v0_74_0"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classify_candidate_strategy(candidate: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(candidate.get("candidate_id") or ""),
            str(candidate.get("rationale") or ""),
        ]
    ).lower()
    if str(candidate.get("candidate_id") or "") == "initial":
        return "initial_check"
    if "nullspace" in text or "null-space" in text or "minimum-norm" in text:
        return "nullspace_or_projection_closure"
    if "remove redundant" in text or "remove equation" in text or "redundant equation" in text:
        return "remove_redundant_constraint"
    if "differential" in text or "der(" in text:
        return "add_dynamics_or_differential_equations"
    if "projection" in text:
        return "projection_constraint"
    if "estimate" in text or "residual" in text:
        return "residual_definition_change"
    return "other_candidate_strategy"


def summarize_run_case(row: dict[str, Any]) -> dict[str, Any]:
    candidates = list(row.get("candidate_files") or [])
    strategy_counts = Counter(classify_candidate_strategy(candidate) for candidate in candidates)
    first_check_pass = next((candidate for candidate in candidates if candidate.get("write_check_ok")), None)
    first_simulate_pass = next((candidate for candidate in candidates if candidate.get("write_simulate_ok")), None)
    return {
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "submitted_candidate_id": str(row.get("submitted_candidate_id") or ""),
        "token_used": int(row.get("token_used") or 0),
        "candidate_count": len(candidates),
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "first_check_pass_candidate_id": str((first_check_pass or {}).get("candidate_id") or ""),
        "first_simulate_pass_candidate_id": str((first_simulate_pass or {}).get("candidate_id") or ""),
        "has_simulate_pass_candidate": bool(first_simulate_pass),
        "candidate_sequence": [
            {
                "candidate_id": str(candidate.get("candidate_id") or ""),
                "strategy": classify_candidate_strategy(candidate),
                "check_ok": bool(candidate.get("write_check_ok")),
                "simulate_ok": bool(candidate.get("write_simulate_ok")),
                "rationale_excerpt": str(candidate.get("rationale") or "")[:240],
            }
            for candidate in candidates
        ],
    }


def build_structural_ambiguity_attribution(
    *,
    result_paths_by_budget: dict[str, Path],
    out_dir: Path = DEFAULT_OUT_DIR,
    summary_version: str = "v0.74.0",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for budget_label, path in result_paths_by_budget.items():
        for result in load_jsonl(path):
            case_summary = summarize_run_case(result)
            case_summary["budget_label"] = str(budget_label)
            rows.append(case_summary)
    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row)
    case_patterns: list[dict[str, Any]] = []
    for case_id, case_rows in sorted(by_case.items()):
        sorted_rows = sorted(case_rows, key=lambda item: item["budget_label"])
        pass_budgets = [row["budget_label"] for row in sorted_rows if row["final_verdict"] == "PASS"]
        fail_budgets = [row["budget_label"] for row in sorted_rows if row["final_verdict"] != "PASS"]
        strategies_in_pass = Counter()
        strategies_in_fail = Counter()
        for row in sorted_rows:
            target = strategies_in_pass if row["final_verdict"] == "PASS" else strategies_in_fail
            target.update(row["strategy_counts"])
        if pass_budgets and fail_budgets:
            pattern = "budget_sensitive_candidate_search_depth"
        elif pass_budgets:
            pattern = "solved_at_observed_budgets"
        else:
            pattern = "unsolved_at_observed_budgets"
        case_patterns.append(
            {
                "case_id": case_id,
                "attribution_pattern": pattern,
                "pass_budgets": pass_budgets,
                "fail_budgets": fail_budgets,
                "strategies_in_pass": dict(sorted(strategies_in_pass.items())),
                "strategies_in_fail": dict(sorted(strategies_in_fail.items())),
                "successful_simulate_candidate_ids": [
                    row["first_simulate_pass_candidate_id"]
                    for row in sorted_rows
                    if row["first_simulate_pass_candidate_id"]
                ],
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_attribution.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out_dir / "case_patterns.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in case_patterns),
        encoding="utf-8",
    )
    pattern_counts = Counter(row["attribution_pattern"] for row in case_patterns)
    summary = {
        "version": summary_version,
        "analysis_scope": "structural_ambiguity_budget_trajectory_attribution",
        "status": "PASS" if rows else "REVIEW",
        "artifact_complete": bool(rows),
        "run_count": len(rows),
        "case_count": len(case_patterns),
        "attribution_pattern_counts": dict(sorted(pattern_counts.items())),
        "budget_sensitive_case_ids": [
            row["case_id"]
            for row in case_patterns
            if row["attribution_pattern"] == "budget_sensitive_candidate_search_depth"
        ],
        "candidate_strategy_scope": (
            "Attribution uses candidate metadata and tool-visible OMC outcomes only. It does not inspect private "
            "chain-of-thought."
        ),
        "next_construction_hypothesis": (
            "Medium-hardness comes from requiring the LLM to choose an additional independent projection/closure "
            "constraint after an initial structural diagnosis, not from the broad family name alone."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    return summary
