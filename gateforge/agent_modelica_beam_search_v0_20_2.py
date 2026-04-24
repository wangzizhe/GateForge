from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import (
    DEFAULT_MULTI_C5_DIR,
    load_multi_c5_results,
)
from gateforge.experiment_runner_shared import REPO_ROOT


DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "beam_search_v0_20_2"


def _candidate_id_as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _simulate_pass_ids(round_row: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for attempt in round_row.get("simulate_attempts") or []:
        if not attempt.get("simulate_pass"):
            continue
        candidate_id = _candidate_id_as_int(attempt.get("candidate_id"))
        if candidate_id is not None:
            ids.add(candidate_id)
    return ids


def select_beam_nodes(round_row: dict[str, Any], *, beam_width: int = 2) -> list[dict[str, Any]]:
    """Select expandable nodes from already-ranked candidates.

    This is a selector only. It does not generate patches, call OMC, or repair.
    """
    selected: list[dict[str, Any]] = []
    simulate_pass_ids = _simulate_pass_ids(round_row)
    for rank_index, candidate in enumerate(round_row.get("ranked") or []):
        if len(selected) >= beam_width:
            break
        candidate_id = _candidate_id_as_int(candidate.get("candidate_id"))
        if candidate_id is None:
            continue
        if not str(candidate.get("patched_text") or "").strip():
            continue
        selected.append(
            {
                "candidate_id": candidate_id,
                "rank_index": rank_index,
                "score": candidate.get("score"),
                "check_pass": bool(candidate.get("check_pass")),
                "simulate_pass": candidate_id in simulate_pass_ids,
            }
        )
    return selected


def replay_case_beam(result: dict[str, Any], *, beam_width: int = 2) -> dict[str, Any]:
    replay_rounds: list[dict[str, Any]] = []
    fixed_candidate_count = 0
    selected_node_count = 0
    fixed_simulate_pass_nodes = 0
    selected_simulate_pass_nodes = 0
    fixed_check_pass_nodes = 0
    selected_check_pass_nodes = 0

    for round_row in result.get("rounds") or []:
        fixed_count = int(round_row.get("num_candidates") or 0)
        selected = select_beam_nodes(round_row, beam_width=beam_width)
        fixed_check = int(round_row.get("coverage_check_pass") or 0)
        fixed_sim = int(round_row.get("coverage_simulate_pass") or 0)
        selected_check = sum(1 for row in selected if row["check_pass"])
        selected_sim = sum(1 for row in selected if row["simulate_pass"])

        fixed_candidate_count += fixed_count
        selected_node_count += len(selected)
        fixed_check_pass_nodes += fixed_check
        selected_check_pass_nodes += selected_check
        fixed_simulate_pass_nodes += fixed_sim
        selected_simulate_pass_nodes += selected_sim

        replay_rounds.append(
            {
                "round": round_row.get("round"),
                "fixed_candidate_count": fixed_count,
                "selected_node_count": len(selected),
                "fixed_check_pass_count": fixed_check,
                "selected_check_pass_count": selected_check,
                "fixed_simulate_pass_count": fixed_sim,
                "selected_simulate_pass_count": selected_sim,
                "selected_nodes": selected,
            }
        )

    return {
        "candidate_id": result.get("candidate_id"),
        "source_final_status": result.get("final_status"),
        "beam_width": beam_width,
        "round_count": len(replay_rounds),
        "fixed_candidate_count": fixed_candidate_count,
        "selected_node_count": selected_node_count,
        "node_savings": fixed_candidate_count - selected_node_count,
        "fixed_check_pass_nodes": fixed_check_pass_nodes,
        "selected_check_pass_nodes": selected_check_pass_nodes,
        "fixed_simulate_pass_nodes": fixed_simulate_pass_nodes,
        "selected_simulate_pass_nodes": selected_simulate_pass_nodes,
        "replay_rounds": replay_rounds,
    }


def summarize_beam_replay(rows: list[dict[str, Any]], *, beam_width: int = 2) -> dict[str, Any]:
    case_count = len(rows)
    fixed_candidates = sum(int(row.get("fixed_candidate_count") or 0) for row in rows)
    selected_nodes = sum(int(row.get("selected_node_count") or 0) for row in rows)
    fixed_check = sum(int(row.get("fixed_check_pass_nodes") or 0) for row in rows)
    selected_check = sum(int(row.get("selected_check_pass_nodes") or 0) for row in rows)
    fixed_sim = sum(int(row.get("fixed_simulate_pass_nodes") or 0) for row in rows)
    selected_sim = sum(int(row.get("selected_simulate_pass_nodes") or 0) for row in rows)
    node_savings = fixed_candidates - selected_nodes
    sim_retention = selected_sim / fixed_sim if fixed_sim else 1.0
    check_retention = selected_check / fixed_check if fixed_check else 1.0
    return {
        "version": "v0.20.2",
        "status": "PASS" if case_count and selected_nodes < fixed_candidates else "INCOMPLETE",
        "analysis_mode": "offline_beam_selector_replay_not_live_tree_search",
        "beam_width": beam_width,
        "case_count": case_count,
        "fixed_candidate_count": fixed_candidates,
        "selected_node_count": selected_nodes,
        "node_savings": node_savings,
        "node_savings_rate": node_savings / fixed_candidates if fixed_candidates else 0.0,
        "fixed_check_pass_nodes": fixed_check,
        "selected_check_pass_nodes": selected_check,
        "check_node_retention_rate": check_retention,
        "fixed_simulate_pass_nodes": fixed_sim,
        "selected_simulate_pass_nodes": selected_sim,
        "simulate_node_retention_rate": sim_retention,
        "promotion_recommendation": (
            "eligible_for_live_tree_search_arm"
            if selected_nodes < fixed_candidates and sim_retention >= 0.8
            else "do_not_promote_without_selector_revision"
        ),
        "conclusion": (
            "beam_selector_reduces_expansion_width_with_acceptable_simulate_retention"
            if selected_nodes < fixed_candidates and sim_retention >= 0.8
            else "beam_selector_replay_needs_revision"
        ),
    }


def run_beam_replay(
    *,
    multi_c5_dir: Path = DEFAULT_MULTI_C5_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    beam_width: int = 2,
) -> dict[str, Any]:
    source_rows = load_multi_c5_results(multi_c5_dir)
    replay_rows = [replay_case_beam(row, beam_width=beam_width) for row in source_rows]
    summary = summarize_beam_replay(replay_rows, beam_width=beam_width)
    write_beam_outputs(out_dir=out_dir, replay_rows=replay_rows, summary=summary)
    return summary


def write_beam_outputs(
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
