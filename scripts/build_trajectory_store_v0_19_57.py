#!/usr/bin/env python3
"""Build the v0.19.57 trajectory retrieval store from existing artifacts."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_trajectory_store_v1 import (
    build_trajectory_store,
    retrieve_similar_trajectories,
    save_trajectory_store,
)


DEFAULT_INPUT_DIRS = [
    "artifacts/phantom_multiturn_experiment_v0_19_37",
    "artifacts/compound_underdetermined_experiment_v0_19_38",
    "artifacts/compound_dm_context_experiment_v0_19_39",
    "artifacts/context_ablation_experiment_v0_19_42",
    "artifacts/multiturn_context_experiment_v0_19_42",
    "artifacts/raw_only_triple_trajectory_v0_19_45",
    "artifacts/raw_only_triple_triple_underdetermined_experiment_v0_19_45_pp_pv_pv",
    "artifacts/triple_hint_experiment_v0_19_46",
    "artifacts/formatted_signal_experiment_v0_19_48",
    "artifacts/memory_triple_trajectory_v0_19_49",
    "artifacts/domain_knowledge_experiment_v0_19_50",
    "artifacts/multi_candidate_trajectory_v0_19_51",
    "artifacts/tool_injection_trajectory_v0_19_54",
    "artifacts/representation_trajectory_v0_19_56",
    "artifacts/representation_routing_trajectory_v0_19_56",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        action="append",
        default=[],
        help="Artifact directory or trajectory JSON file. Can be repeated.",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/trajectory_store_v0_19_57",
        help="Output directory for store.json and summary.json.",
    )
    parser.add_argument("--vector-dim", type=int, default=512)
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


def _summarize_store(store: dict[str, Any], *, latency_ms: float, top_k: int) -> dict[str, Any]:
    family_counts: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    for entry in store.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        family = str(entry.get("mutation_family") or "unknown")
        failure = str(entry.get("failure_type") or "unknown")
        family_counts[family] = family_counts.get(family, 0) + 1
        failure_counts[failure] = failure_counts.get(failure, 0) + 1
    return {
        "version": "v0.19.57",
        "entry_count": int(store.get("entry_count") or 0),
        "success_count": int(store.get("success_count") or 0),
        "failure_count": int(store.get("failure_count") or 0),
        "source_file_count": int(store.get("source_file_count") or 0),
        "skipped_file_count": int(store.get("skipped_file_count") or 0),
        "vector_dim": int(store.get("vector_dim") or 0),
        "top_k": top_k,
        "retrieval_latency_ms": round(latency_ms, 3),
        "latency_pass": latency_ms <= 500.0,
        "family_counts": dict(sorted(family_counts.items())),
        "failure_counts": dict(sorted(failure_counts.items())),
        "success_criterion": {
            "success_entries_ge_100": int(store.get("success_count") or 0) >= 100,
            "failure_entries_ge_50": int(store.get("failure_count") or 0) >= 50,
            "latency_le_500ms": latency_ms <= 500.0,
        },
    }


def main() -> int:
    args = _parse_args()
    input_paths = [Path(p) for p in (args.input_dir or DEFAULT_INPUT_DIRS)]
    out_dir = Path(args.out_dir)
    store_path = out_dir / "store.json"
    summary_path = out_dir / "summary.json"

    store = build_trajectory_store(input_paths, vector_dim=int(args.vector_dim))
    query = {
        "mutation_family": "compound_underdetermined",
        "failure_type": "underdetermined_structural",
        "abstract_signature": {
            "mutation_family": "compound_underdetermined",
            "failure_type": "underdetermined_structural",
            "has_parameter_promotion_marker": True,
            "has_phantom_marker": True,
            "deficit_bucket": "mid",
            "round_count_bucket": "low",
        },
    }
    started = time.perf_counter()
    retrieval = retrieve_similar_trajectories(store, query, top_k=int(args.top_k))
    latency_ms = (time.perf_counter() - started) * 1000.0

    save_trajectory_store(store, store_path)
    summary = _summarize_store(store, latency_ms=latency_ms, top_k=int(args.top_k))
    summary["sample_retrieval"] = retrieval
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
