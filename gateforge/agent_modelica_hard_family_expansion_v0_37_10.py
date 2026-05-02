from __future__ import annotations

from typing import Any


TARGET_FAMILY = "reusable_contract_adapter"


def select_reusable_contract_candidates(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for seed in seeds:
        text = " ".join(
            [
                str(seed.get("family") or ""),
                str(seed.get("case_id") or ""),
                str(seed.get("workflow_intent") or ""),
                str(seed.get("visible_task_description") or ""),
            ]
        ).lower()
        if any(term in text for term in ("reusable", "contract", "adapter", "probe", "monitor")):
            selected.append(seed)
    return selected


def build_reusable_contract_expansion_summary(seeds: list[dict[str, Any]]) -> dict[str, Any]:
    selected = select_reusable_contract_candidates(seeds)
    return {
        "version": "v0.37.10",
        "analysis_scope": "reusable_contract_adapter_family_expansion",
        "status": "PASS" if selected else "REVIEW",
        "candidate_count": len(selected),
        "known_hard_candidate_count": sum(1 for seed in selected if seed.get("known_hard_for")),
        "case_ids": [str(seed.get("case_id") or "") for seed in selected],
    }

