from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import (
    DEFAULT_MULTI_C5_DIR,
    load_multi_c5_results,
)
from gateforge.agent_modelica_candidate_diversity_v0_20_3 import analyze_round_diversity
from gateforge.experiment_runner_shared import REPO_ROOT


DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "diversity_resampling_v0_20_4"


def classify_resampling_need(
    *,
    structural_uniqueness_rate: float,
    text_uniqueness_rate: float,
    simulate_pass_count: int,
    structural_threshold: float = 0.75,
) -> str:
    if structural_uniqueness_rate < structural_threshold:
        return "diversity_resample"
    if simulate_pass_count <= 0 and text_uniqueness_rate < 0.9:
        return "failure_aware_resample"
    return "keep_standard_sampling"


def build_safe_resampling_note(row: dict[str, Any]) -> str:
    """Build a model-profile note without case-specific repair hints."""
    recommendation = str(row.get("recommendation") or "")
    if recommendation == "diversity_resample":
        return (
            "The previous candidate batch contained repeated structural edit patterns. "
            "Generate the next batch as distinct repair hypotheses that touch different "
            "kinds of declarations or equations. Do not repeat the same structural edit."
        )
    if recommendation == "failure_aware_resample":
        return (
            "The previous candidate batch did not produce a passing validation signal. "
            "Generate the next batch using a different repair strategy rather than minor "
            "variants of the same edit."
        )
    return "Continue standard candidate sampling."


def build_resampling_row(result: dict[str, Any], round_row: dict[str, Any]) -> dict[str, Any]:
    diversity = analyze_round_diversity(result, round_row)
    recommendation = classify_resampling_need(
        structural_uniqueness_rate=float(diversity.get("structural_uniqueness_rate") or 0.0),
        text_uniqueness_rate=float(diversity.get("text_uniqueness_rate") or 0.0),
        simulate_pass_count=int(diversity.get("simulate_pass_count") or 0),
    )
    row = {
        "candidate_id": diversity.get("candidate_id"),
        "round": diversity.get("round"),
        "candidate_count": diversity.get("candidate_count"),
        "unique_text_count": diversity.get("unique_text_count"),
        "unique_structural_signature_count": diversity.get("unique_structural_signature_count"),
        "text_uniqueness_rate": diversity.get("text_uniqueness_rate"),
        "structural_uniqueness_rate": diversity.get("structural_uniqueness_rate"),
        "duplicate_structural_signature_count": diversity.get("duplicate_structural_signature_count"),
        "simulate_pass_count": diversity.get("simulate_pass_count"),
        "recommendation": recommendation,
    }
    row["safe_resampling_note"] = build_safe_resampling_note(row)
    return row


def build_resampling_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for round_row in result.get("rounds") or []:
            rows.append(build_resampling_row(result, round_row))
    return rows


def summarize_resampling(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    diversity_count = sum(1 for row in rows if row.get("recommendation") == "diversity_resample")
    failure_count = sum(1 for row in rows if row.get("recommendation") == "failure_aware_resample")
    standard_count = sum(1 for row in rows if row.get("recommendation") == "keep_standard_sampling")
    avg_structural = (
        sum(float(row.get("structural_uniqueness_rate") or 0.0) for row in rows) / total
        if total
        else 0.0
    )
    return {
        "version": "v0.20.4",
        "status": "PASS" if total else "INCOMPLETE",
        "analysis_mode": "offline_resampling_profile_not_live_repair",
        "round_count": total,
        "diversity_resample_count": diversity_count,
        "failure_aware_resample_count": failure_count,
        "keep_standard_sampling_count": standard_count,
        "diversity_resample_rate": diversity_count / total if total else 0.0,
        "average_structural_uniqueness_rate": avg_structural,
        "prompt_safety_discipline": {
            "no_case_id_routing": True,
            "no_model_family_routing": True,
            "no_variable_name_hint": True,
            "no_wrapper_repair": True,
        },
        "conclusion": (
            "diversity_aware_resampling_profile_ready"
            if diversity_count > 0
            else "diversity_resampling_not_triggered"
        ),
    }


def run_diversity_resampling_profile(
    *,
    multi_c5_dir: Path = DEFAULT_MULTI_C5_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    results = load_multi_c5_results(multi_c5_dir)
    rows = build_resampling_rows(results)
    summary = summarize_resampling(rows)
    write_resampling_outputs(out_dir=out_dir, rows=rows, summary=summary)
    return summary


def write_resampling_outputs(
    *,
    out_dir: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resampling_rows.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
