from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateforge.experiment_runner_shared import REPO_ROOT


DEFAULT_MULTI_C5_DIR = REPO_ROOT / "artifacts" / "multi_candidate_trajectory_v0_19_51"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "adaptive_budget_v0_20_1"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_multi_c5_results(results_dir: Path = DEFAULT_MULTI_C5_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*_multi-c5.json")):
        payload = load_json(path)
        if payload:
            payload["artifact_path"] = str(path)
            rows.append(payload)
    return rows


def choose_adaptive_budget(
    previous_rounds: list[dict[str, Any]],
    *,
    initial_budget: int = 3,
    elevated_budget: int = 5,
) -> int:
    """Choose next candidate budget from prior OMC outcome signals only."""
    if not previous_rounds:
        return initial_budget
    last = previous_rounds[-1]
    advance = str(last.get("advance") or "")
    if advance in {"stalled_no_change", "stalled_no_progress"}:
        return elevated_budget
    if not bool(last.get("any_check_pass")):
        return elevated_budget
    if not bool(last.get("any_simulate_pass")):
        return elevated_budget
    return initial_budget


def _candidate_id_as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def visible_ranked_candidates(round_row: dict[str, Any], budget: int) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for candidate in round_row.get("ranked") or []:
        candidate_id = _candidate_id_as_int(candidate.get("candidate_id"))
        if candidate_id is not None and candidate_id < budget:
            visible.append(candidate)
    return visible


def visible_simulate_attempts(round_row: dict[str, Any], budget: int) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for attempt in round_row.get("simulate_attempts") or []:
        candidate_id = _candidate_id_as_int(attempt.get("candidate_id"))
        if candidate_id is not None and candidate_id < budget:
            visible.append(attempt)
    return visible


def replay_case_budget(result: dict[str, Any]) -> dict[str, Any]:
    previous_rounds: list[dict[str, Any]] = []
    replay_rounds: list[dict[str, Any]] = []
    fixed_candidate_count = 0
    adaptive_candidate_count = 0
    fixed_simulate_visible_rounds = 0
    adaptive_simulate_visible_rounds = 0
    fixed_check_visible_rounds = 0
    adaptive_check_visible_rounds = 0

    for round_row in result.get("rounds") or []:
        fixed_budget = int(round_row.get("num_candidates") or 5)
        adaptive_budget = choose_adaptive_budget(previous_rounds)
        fixed_candidate_count += fixed_budget
        adaptive_candidate_count += adaptive_budget

        adaptive_ranked = visible_ranked_candidates(round_row, adaptive_budget)
        adaptive_sim_attempts = visible_simulate_attempts(round_row, adaptive_budget)
        adaptive_check_count = sum(1 for row in adaptive_ranked if row.get("check_pass"))
        adaptive_sim_count = sum(1 for row in adaptive_sim_attempts if row.get("simulate_pass"))
        fixed_check_count = int(round_row.get("coverage_check_pass") or 0)
        fixed_sim_count = int(round_row.get("coverage_simulate_pass") or 0)

        if fixed_check_count:
            fixed_check_visible_rounds += 1
        if adaptive_check_count:
            adaptive_check_visible_rounds += 1
        if fixed_sim_count:
            fixed_simulate_visible_rounds += 1
        if adaptive_sim_count:
            adaptive_simulate_visible_rounds += 1

        replay_rounds.append(
            {
                "round": round_row.get("round"),
                "fixed_budget": fixed_budget,
                "adaptive_budget": adaptive_budget,
                "fixed_check_pass_count": fixed_check_count,
                "adaptive_check_pass_count": adaptive_check_count,
                "fixed_simulate_pass_count": fixed_sim_count,
                "adaptive_simulate_pass_count": adaptive_sim_count,
                "adaptive_visible_ranked_count": len(adaptive_ranked),
            }
        )
        previous_rounds.append(round_row)

    round_count = len(replay_rounds)
    return {
        "candidate_id": result.get("candidate_id"),
        "source_final_status": result.get("final_status"),
        "round_count": round_count,
        "fixed_candidate_count": fixed_candidate_count,
        "adaptive_candidate_count": adaptive_candidate_count,
        "candidate_savings": fixed_candidate_count - adaptive_candidate_count,
        "fixed_any_check_rounds": fixed_check_visible_rounds,
        "adaptive_any_check_rounds": adaptive_check_visible_rounds,
        "fixed_any_simulate_rounds": fixed_simulate_visible_rounds,
        "adaptive_any_simulate_rounds": adaptive_simulate_visible_rounds,
        "replay_rounds": replay_rounds,
    }


def summarize_budget_replay(rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(rows)
    fixed_candidates = sum(int(row.get("fixed_candidate_count") or 0) for row in rows)
    adaptive_candidates = sum(int(row.get("adaptive_candidate_count") or 0) for row in rows)
    fixed_sim_rounds = sum(int(row.get("fixed_any_simulate_rounds") or 0) for row in rows)
    adaptive_sim_rounds = sum(int(row.get("adaptive_any_simulate_rounds") or 0) for row in rows)
    fixed_check_rounds = sum(int(row.get("fixed_any_check_rounds") or 0) for row in rows)
    adaptive_check_rounds = sum(int(row.get("adaptive_any_check_rounds") or 0) for row in rows)
    round_count = sum(int(row.get("round_count") or 0) for row in rows)
    savings = fixed_candidates - adaptive_candidates
    sim_retention = adaptive_sim_rounds / fixed_sim_rounds if fixed_sim_rounds else 1.0
    check_retention = adaptive_check_rounds / fixed_check_rounds if fixed_check_rounds else 1.0
    return {
        "version": "v0.20.1",
        "status": "PASS" if case_count and adaptive_candidates < fixed_candidates else "INCOMPLETE",
        "analysis_mode": "offline_replay_not_live_pass_rate",
        "case_count": case_count,
        "round_count": round_count,
        "fixed_candidate_count": fixed_candidates,
        "adaptive_candidate_count": adaptive_candidates,
        "candidate_savings": savings,
        "candidate_savings_rate": savings / fixed_candidates if fixed_candidates else 0.0,
        "fixed_any_check_rounds": fixed_check_rounds,
        "adaptive_any_check_rounds": adaptive_check_rounds,
        "check_round_retention_rate": check_retention,
        "fixed_any_simulate_rounds": fixed_sim_rounds,
        "adaptive_any_simulate_rounds": adaptive_sim_rounds,
        "simulate_round_retention_rate": sim_retention,
        "promotion_recommendation": (
            "eligible_for_live_arm"
            if adaptive_candidates < fixed_candidates and sim_retention >= 0.8
            else "do_not_promote_without_revision"
        ),
        "conclusion": (
            "adaptive_budget_reduces_candidate_cost_with_acceptable_simulate_retention"
            if adaptive_candidates < fixed_candidates and sim_retention >= 0.8
            else "adaptive_budget_replay_needs_revision"
        ),
    }


def run_adaptive_budget_replay(
    *,
    multi_c5_dir: Path = DEFAULT_MULTI_C5_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    source_rows = load_multi_c5_results(multi_c5_dir)
    replay_rows = [replay_case_budget(row) for row in source_rows]
    summary = summarize_budget_replay(replay_rows)
    write_adaptive_budget_outputs(out_dir=out_dir, replay_rows=replay_rows, summary=summary)
    return summary


def write_adaptive_budget_outputs(
    *,
    out_dir: Path,
    replay_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "replay_rows.json").write_text(
        json.dumps(replay_rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
