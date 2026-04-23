"""Retrieval context builder for v0.19.58.

This module turns the local trajectory store into a thin prompt context block.
It does not generate repair hints, does not route by case id, and does not
modify candidate selection. It only exposes abstract summaries from similar
successful trajectories.
"""

from __future__ import annotations

from typing import Any

from .agent_modelica_trajectory_store_v1 import (
    abstract_root_cause_signature,
    infer_failure_type,
    infer_mutation_family,
    retrieve_similar_trajectories,
)


def build_retrieval_query(
    *,
    candidate_id: str,
    mode: str,
    omc_output: str,
    round_num: int,
) -> dict[str, Any]:
    payload = {"candidate_id": candidate_id}
    round_payload = {
        "round": round_num,
        "omc_output": omc_output,
    }
    mutation_family = infer_mutation_family(payload)
    failure_type = infer_failure_type(payload, round_payload)
    signature = abstract_root_cause_signature(payload, round_payload)
    return {
        "candidate_id": candidate_id,
        "mode": mode,
        "mutation_family": mutation_family,
        "failure_type": failure_type,
        "abstract_signature": signature,
    }


def select_retrieval_hits(
    retrieval_payload: dict[str, Any],
    *,
    exclude_candidate_id: str,
    top_k: int,
) -> list[dict[str, Any]]:
    hits = retrieval_payload.get("hits") if isinstance(retrieval_payload, dict) else []
    if not isinstance(hits, list):
        return []

    out: list[dict[str, Any]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        if str(hit.get("final_status") or "").strip().lower() != "pass":
            continue
        if str(hit.get("candidate_id") or "").strip() == str(exclude_candidate_id or "").strip():
            continue
        out.append(hit)
        if len(out) >= max(0, int(top_k)):
            break
    return out


def format_retrieval_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    lines = [
        "Similar successful trajectory summaries from past repairs (facts only, not instructions):"
    ]
    for idx, hit in enumerate(hits, start=1):
        lines.append(
            (
                f"{idx}. score={float(hit.get('score') or 0.0):.3f} "
                f"family={str(hit.get('mutation_family') or 'unknown').strip()} "
                f"failure={str(hit.get('failure_type') or 'unknown').strip()} "
                f"mode={str(hit.get('mode') or 'unknown').strip()} "
                f"summary={str(hit.get('summary') or '').strip()}"
            ).strip()
        )
    return "\n".join(lines)


def build_retrieval_context(
    *,
    store: dict[str, Any],
    candidate_id: str,
    mode: str,
    omc_output: str,
    round_num: int,
    top_k: int = 3,
) -> dict[str, Any]:
    query = build_retrieval_query(
        candidate_id=candidate_id,
        mode=mode,
        omc_output=omc_output,
        round_num=round_num,
    )
    retrieval_payload = retrieve_similar_trajectories(
        store,
        query,
        top_k=max(int(top_k) + 4, int(top_k)),
        prefer_success=True,
    )
    selected_hits = select_retrieval_hits(
        retrieval_payload,
        exclude_candidate_id=candidate_id,
        top_k=top_k,
    )
    context_text = format_retrieval_context(selected_hits)
    return {
        "query": query,
        "retrieval_latency_ms": float(retrieval_payload.get("latency_ms") or 0.0),
        "retrieved_hit_count": len(selected_hits),
        "retrieved_hits": selected_hits,
        "context_text": context_text,
        "context_label": "Historical successful trajectory context",
    }
