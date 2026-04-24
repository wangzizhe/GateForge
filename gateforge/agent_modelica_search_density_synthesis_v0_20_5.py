from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateforge.experiment_runner_shared import REPO_ROOT


DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "search_density_synthesis_v0_20_5"
DEFAULT_INPUTS = {
    "substrate": REPO_ROOT / "artifacts" / "search_density_v0_20_0" / "summary.json",
    "adaptive_budget": REPO_ROOT / "artifacts" / "adaptive_budget_v0_20_1" / "summary.json",
    "beam_width_2": REPO_ROOT / "artifacts" / "beam_search_v0_20_2" / "summary.json",
    "beam_width_4": REPO_ROOT / "artifacts" / "beam_search_v0_20_2_bw4" / "summary.json",
    "candidate_diversity": REPO_ROOT / "artifacts" / "candidate_diversity_v0_20_3" / "summary.json",
    "diversity_resampling": REPO_ROOT / "artifacts" / "diversity_resampling_v0_20_4" / "summary.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_search_density_decisions(inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    adaptive = inputs.get("adaptive_budget") or {}
    beam2 = inputs.get("beam_width_2") or {}
    beam4 = inputs.get("beam_width_4") or {}
    diversity = inputs.get("candidate_diversity") or {}
    resampling = inputs.get("diversity_resampling") or {}

    adaptive_live = adaptive.get("promotion_recommendation") == "eligible_for_live_arm"
    beam2_live = beam2.get("promotion_recommendation") == "eligible_for_live_tree_search_arm"
    beam4_live = beam4.get("promotion_recommendation") == "eligible_for_live_tree_search_arm"
    diversity_needed = diversity.get("recommendation") == "prioritize_diversity_prompting"
    resampling_ready = resampling.get("conclusion") == "diversity_aware_resampling_profile_ready"

    return {
        "default_strategy": "fixed-c5-remains-current-default",
        "adaptive_budget": {
            "decision": "live_arm_candidate" if adaptive_live else "hold",
            "reason": "offline_replay_saves_candidates_but_is_not_live_pass_rate",
        },
        "beam_tree_search": {
            "decision": "beam_width_4_live_arm_candidate" if beam4_live else "hold",
            "reason": (
                "beam_width_2_prunes_too_aggressively"
                if not beam2_live
                else "beam_width_2_retention_ok"
            ),
        },
        "diversity_aware_resampling": {
            "decision": "highest_priority_live_profile" if diversity_needed and resampling_ready else "hold",
            "reason": "candidate_pool_has_systemic_structural_duplication",
        },
        "next_phase": "v0.21_generation_distribution_alignment",
        "live_experiment_priority_order": [
            "diversity-aware-c5",
            "adaptive-budget",
            "beam-width-4-tree-search",
        ],
    }


def build_search_density_synthesis(
    *,
    input_paths: dict[str, Path] = DEFAULT_INPUTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    inputs = {name: load_json(path) for name, path in input_paths.items()}
    missing = [name for name, payload in inputs.items() if not payload]
    decisions = build_search_density_decisions(inputs)
    summary = {
        "version": "v0.20.5",
        "status": "PASS" if not missing else "INCOMPLETE",
        "missing_inputs": missing,
        "input_statuses": {name: payload.get("status") for name, payload in inputs.items()},
        "key_metrics": {
            "substrate_main_case_count": (inputs.get("substrate") or {}).get("main_case_count"),
            "substrate_shadow_case_count": (inputs.get("substrate") or {}).get("shadow_case_count"),
            "adaptive_candidate_savings_rate": (inputs.get("adaptive_budget") or {}).get("candidate_savings_rate"),
            "adaptive_simulate_retention": (inputs.get("adaptive_budget") or {}).get("simulate_round_retention_rate"),
            "beam_width_2_simulate_retention": (inputs.get("beam_width_2") or {}).get("simulate_node_retention_rate"),
            "beam_width_4_simulate_retention": (inputs.get("beam_width_4") or {}).get("simulate_node_retention_rate"),
            "candidate_structural_uniqueness": (inputs.get("candidate_diversity") or {}).get("average_structural_uniqueness_rate"),
            "diversity_resample_rate": (inputs.get("diversity_resampling") or {}).get("diversity_resample_rate"),
        },
        "decisions": decisions,
        "conclusion": "search_density_v2_offline_phase_closed" if not missing else "search_density_v2_synthesis_incomplete",
    }
    write_synthesis_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_synthesis_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
