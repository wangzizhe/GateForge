from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_9_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_9_0_common import PRIORITY_BARRIERS
from .agent_modelica_v0_9_2_common import (
    BASELINE_SOURCE_ID,
    DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR,
    DEFAULT_V091_POOL_DELTA_PATH,
    MAX_SUBSTRATE_SIZE,
    MIN_SUBSTRATE_SIZE,
    READY_BARRIER_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _barrier_label(row: dict) -> str:
    audit = row.get("barrier_sampling_audit") if isinstance(row.get("barrier_sampling_audit"), dict) else {}
    return str(audit.get("target_barrier_family") or "")


def _source_counts(rows: list[dict]) -> Counter:
    return Counter(str(row.get("source_id") or "") for row in rows if isinstance(row, dict))


def _candidate_sort_key(row: dict, selected_rows: list[dict]) -> tuple:
    source_counts = _source_counts(selected_rows)
    source_id = str(row.get("source_id") or "")
    barrier = _barrier_label(row)
    source_diversity_pressure = source_counts.get(source_id, 0)
    baseline_penalty = 0 if source_id != BASELINE_SOURCE_ID else 1
    barrier_rank = PRIORITY_BARRIERS.index(barrier) if barrier in PRIORITY_BARRIERS else len(PRIORITY_BARRIERS)
    return (
        baseline_penalty,
        source_diversity_pressure,
        barrier_rank,
        str(row.get("task_id") or ""),
    )


def _coverage_counts(rows: list[dict]) -> dict[str, int]:
    counts = {barrier: 0 for barrier in PRIORITY_BARRIERS}
    for row in rows:
        barrier = _barrier_label(row)
        if barrier in counts:
            counts[barrier] += 1
    return counts


def build_v092_expanded_substrate_builder(
    *,
    v091_pool_delta_path: str = str(DEFAULT_V091_POOL_DELTA_PATH),
    out_dir: str = str(DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v091_pool_delta_path)
    pool = upstream.get("post_expansion_candidate_pool") if isinstance(upstream.get("post_expansion_candidate_pool"), list) else []
    admitted_pool = [row for row, verdict in zip(pool, evaluate_candidate_rows(pool)) if verdict.get("admitted")]

    baseline_rows = [row for row in admitted_pool if str(row.get("source_id") or "") == BASELINE_SOURCE_ID]
    remaining_rows = [row for row in admitted_pool if str(row.get("source_id") or "") != BASELINE_SOURCE_ID]

    selected_rows = list(sorted(baseline_rows, key=lambda row: str(row.get("task_id") or "")))
    for barrier in PRIORITY_BARRIERS:
        deficit = max(0, READY_BARRIER_MIN - _coverage_counts(selected_rows)[barrier])
        eligible = [row for row in remaining_rows if _barrier_label(row) == barrier]
        eligible = sorted(eligible, key=lambda row: _candidate_sort_key(row, selected_rows))
        chosen = eligible[:deficit]
        selected_rows.extend(chosen)
        chosen_ids = {str(row.get("task_id") or "") for row in chosen}
        remaining_rows = [row for row in remaining_rows if str(row.get("task_id") or "") not in chosen_ids]

    while len(selected_rows) < MIN_SUBSTRATE_SIZE and remaining_rows:
        next_row = sorted(remaining_rows, key=lambda row: _candidate_sort_key(row, selected_rows))[0]
        selected_rows.append(next_row)
        next_id = str(next_row.get("task_id") or "")
        remaining_rows = [row for row in remaining_rows if str(row.get("task_id") or "") != next_id]

    if len(selected_rows) > MAX_SUBSTRATE_SIZE:
        selected_rows = selected_rows[:MAX_SUBSTRATE_SIZE]

    barrier_counts = _coverage_counts(selected_rows)
    source_mix = dict(sorted(_source_counts(selected_rows).items()))
    workflow_family_mix = dict(sorted(Counter(str(row.get("family_id") or "") for row in selected_rows).items()))
    complexity_mix = dict(sorted(Counter(str(row.get("complexity_tier") or "") for row in selected_rows).items()))
    goal_specific_check_mode_mix = dict(sorted(Counter(str(row.get("goal_specific_check_mode") or "") for row in selected_rows).items()))
    template_mix = dict(sorted(Counter(str(row.get("workflow_task_template_id") or "") for row in selected_rows).items()))

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_expanded_substrate_builder",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "expanded_substrate_candidate_count": len(selected_rows),
        "expanded_substrate_candidate_table": [
            {
                **row,
                "priority_barrier_label": _barrier_label(row),
                "expanded_substrate_admission_pass": True,
            }
            for row in selected_rows
        ],
        "source_mix": source_mix,
        "workflow_family_mix": workflow_family_mix,
        "complexity_mix": complexity_mix,
        "goal_specific_check_mode_mix": goal_specific_check_mode_mix,
        "workflow_task_template_mix": template_mix,
        "priority_barrier_coverage_table": barrier_counts,
        "baseline_rows_preserved_count": sum(1 for row in selected_rows if str(row.get("source_id") or "") == BASELINE_SOURCE_ID),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.2 Expanded Substrate Builder",
                "",
                f"- expanded_substrate_candidate_count: `{len(selected_rows)}`",
                f"- priority_barrier_coverage_table: `{barrier_counts}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.2 expanded substrate candidate artifact.")
    parser.add_argument("--v091-pool-delta", default=str(DEFAULT_V091_POOL_DELTA_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v092_expanded_substrate_builder(
        v091_pool_delta_path=str(args.v091_pool_delta),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "expanded_substrate_candidate_count": payload.get("expanded_substrate_candidate_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
