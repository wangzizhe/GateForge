from __future__ import annotations

from typing import Any


TARGET_FAMILY = "arrayed_connector_flow"


def select_arrayed_connector_flow_candidates(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        seed
        for seed in seeds
        if str(seed.get("family") or "") == TARGET_FAMILY
        or any(term in str(seed.get("case_id") or "") for term in ("sem_19", "sem_20", "sem_21", "sem_22", "sem_23", "sem_24"))
    ]


def build_arrayed_connector_flow_expansion_summary(seeds: list[dict[str, Any]]) -> dict[str, Any]:
    selected = select_arrayed_connector_flow_candidates(seeds)
    known_hard = [seed for seed in selected if seed.get("known_hard_for")]
    return {
        "version": "v0.37.4",
        "analysis_scope": "arrayed_connector_flow_family_expansion",
        "status": "PASS" if selected else "REVIEW",
        "candidate_count": len(selected),
        "known_hard_candidate_count": len(known_hard),
        "case_ids": [str(seed.get("case_id") or "") for seed in selected],
        "decision": "expand_this_family_first" if known_hard else "needs_baseline_evidence",
    }

