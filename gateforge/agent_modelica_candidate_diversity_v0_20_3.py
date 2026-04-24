from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import (
    DEFAULT_MULTI_C5_DIR,
    load_multi_c5_results,
)
from gateforge.experiment_runner_shared import REPO_ROOT


DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_diversity_v0_20_3"

DECL_RE = re.compile(r"^\s*(parameter\s+)?(Real|Integer|Boolean|String)\s+[A-Za-z_][A-Za-z0-9_]*")
EQUATION_RE = re.compile(r"^\s*(der\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]+\])?)\s*=")


def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def structural_signature(model_text: str) -> str:
    """Create a coarse structure signature without interpreting Modelica semantics."""
    declarations: list[str] = []
    equations: list[str] = []
    for line in model_text.splitlines():
        stripped = line.split("//", 1)[0].strip()
        if DECL_RE.match(stripped):
            declarations.append(re.sub(r"\s+", " ", stripped.split('"')[0]).strip())
        elif EQUATION_RE.match(stripped):
            lhs = stripped.split("=", 1)[0].strip()
            equations.append(lhs)
    payload = json.dumps(
        {
            "decl_count": len(declarations),
            "equation_count": len(equations),
            "decls": sorted(declarations),
            "eq_lhs": sorted(equations),
        },
        sort_keys=True,
    )
    return _hash_text(payload)


def _simulate_pass_ids(round_row: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for attempt in round_row.get("simulate_attempts") or []:
        if not attempt.get("simulate_pass"):
            continue
        try:
            ids.add(int(attempt.get("candidate_id")))
        except (TypeError, ValueError):
            continue
    return ids


def analyze_round_diversity(result: dict[str, Any], round_row: dict[str, Any]) -> dict[str, Any]:
    ranked = list(round_row.get("ranked") or [])
    text_hashes: list[str] = []
    structural_hashes: list[str] = []
    simulate_pass_ids = _simulate_pass_ids(round_row)
    simulate_pass_rank_positions: list[int] = []

    for rank_index, candidate in enumerate(ranked):
        text = str(candidate.get("patched_text") or "")
        text_hashes.append(_hash_text(text))
        structural_hashes.append(structural_signature(text))
        try:
            candidate_id = int(candidate.get("candidate_id"))
        except (TypeError, ValueError):
            continue
        if candidate_id in simulate_pass_ids:
            simulate_pass_rank_positions.append(rank_index)

    candidate_count = len(ranked)
    unique_text_count = len(set(text_hashes))
    unique_structural_count = len(set(structural_hashes))
    return {
        "candidate_id": result.get("candidate_id"),
        "round": round_row.get("round"),
        "candidate_count": candidate_count,
        "unique_text_count": unique_text_count,
        "unique_structural_signature_count": unique_structural_count,
        "text_uniqueness_rate": unique_text_count / candidate_count if candidate_count else 0.0,
        "structural_uniqueness_rate": unique_structural_count / candidate_count if candidate_count else 0.0,
        "duplicate_text_count": candidate_count - unique_text_count,
        "duplicate_structural_signature_count": candidate_count - unique_structural_count,
        "simulate_pass_rank_positions": simulate_pass_rank_positions,
        "simulate_pass_count": len(simulate_pass_rank_positions),
        "top2_contains_simulate_pass": any(pos < 2 for pos in simulate_pass_rank_positions),
        "top4_contains_simulate_pass": any(pos < 4 for pos in simulate_pass_rank_positions),
    }


def analyze_candidate_diversity(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for round_row in result.get("rounds") or []:
            rows.append(analyze_round_diversity(result, round_row))
    return rows


def summarize_diversity(round_rows: list[dict[str, Any]]) -> dict[str, Any]:
    round_count = len(round_rows)
    total_candidates = sum(int(row.get("candidate_count") or 0) for row in round_rows)
    duplicate_text = sum(int(row.get("duplicate_text_count") or 0) for row in round_rows)
    duplicate_structural = sum(int(row.get("duplicate_structural_signature_count") or 0) for row in round_rows)
    simulate_rounds = [row for row in round_rows if int(row.get("simulate_pass_count") or 0) > 0]
    top2_hits = sum(1 for row in simulate_rounds if row.get("top2_contains_simulate_pass"))
    top4_hits = sum(1 for row in simulate_rounds if row.get("top4_contains_simulate_pass"))
    all_sim_positions = [
        pos
        for row in round_rows
        for pos in (row.get("simulate_pass_rank_positions") or [])
    ]
    position_counts = Counter(str(pos) for pos in all_sim_positions)
    avg_text_uniqueness = (
        sum(float(row.get("text_uniqueness_rate") or 0.0) for row in round_rows) / round_count
        if round_count
        else 0.0
    )
    avg_structural_uniqueness = (
        sum(float(row.get("structural_uniqueness_rate") or 0.0) for row in round_rows) / round_count
        if round_count
        else 0.0
    )
    top2_retention = top2_hits / len(simulate_rounds) if simulate_rounds else 1.0
    top4_retention = top4_hits / len(simulate_rounds) if simulate_rounds else 1.0
    if avg_structural_uniqueness < 0.75:
        recommendation = "prioritize_diversity_prompting"
    elif top2_retention < 0.8 and top4_retention >= 0.8:
        recommendation = "avoid_aggressive_pruning_use_wider_beam_or_better_selector"
    else:
        recommendation = "diversity_not_primary_bottleneck"
    return {
        "version": "v0.20.3",
        "status": "PASS" if round_count else "INCOMPLETE",
        "analysis_mode": "offline_candidate_diversity_audit",
        "round_count": round_count,
        "candidate_count": total_candidates,
        "duplicate_text_count": duplicate_text,
        "duplicate_structural_signature_count": duplicate_structural,
        "average_text_uniqueness_rate": avg_text_uniqueness,
        "average_structural_uniqueness_rate": avg_structural_uniqueness,
        "simulate_visible_round_count": len(simulate_rounds),
        "top2_simulate_round_retention": top2_retention,
        "top4_simulate_round_retention": top4_retention,
        "simulate_pass_rank_position_counts": dict(sorted(position_counts.items())),
        "recommendation": recommendation,
        "conclusion": recommendation,
    }


def run_candidate_diversity_audit(
    *,
    multi_c5_dir: Path = DEFAULT_MULTI_C5_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    results = load_multi_c5_results(multi_c5_dir)
    round_rows = analyze_candidate_diversity(results)
    summary = summarize_diversity(round_rows)
    write_diversity_outputs(out_dir=out_dir, round_rows=round_rows, summary=summary)
    return summary


def write_diversity_outputs(
    *,
    out_dir: Path,
    round_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "round_rows.json").write_text(
        json.dumps(round_rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
