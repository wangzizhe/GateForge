from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_10_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_10_3_common import (
    DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR,
    DEFAULT_V102_POOL_DELTA_PATH,
    READY_MAX_SINGLE_SOURCE_SHARE_PCT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _max_source_share_pct(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    counts = Counter(str(row.get("source_id") or "") for row in rows if str(row.get("source_id") or ""))
    if not counts:
        return 0.0
    return round(max(counts.values()) * 100.0 / float(len(rows)), 1)


def build_v103_real_origin_substrate_builder(
    *,
    v102_pool_delta_path: str = str(DEFAULT_V102_POOL_DELTA_PATH),
    out_dir: str = str(DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v102_pool_delta_path)
    pool = upstream.get("post_expansion_candidate_pool") if isinstance(upstream.get("post_expansion_candidate_pool"), list) else []
    evaluations = evaluate_candidate_rows(pool)

    selected_rows: list[dict] = []
    excluded_rows: list[dict] = []
    seen_task_ids: set[str] = set()
    for row, verdict in zip(pool, evaluations):
        source_origin_class = verdict.get("source_origin_class")
        task_id = str(row.get("task_id") or "")
        if verdict.get("mainline_counted") and task_id not in seen_task_ids:
            selected_rows.append(
                {
                    **row,
                    "real_origin_substrate_admission_pass": True,
                    "real_origin_substrate_inclusion_reason": "upstream_mainline_real_origin_row_preserved",
                }
            )
            seen_task_ids.add(task_id)
        else:
            excluded_rows.append(
                {
                    "task_id": task_id,
                    "source_id": row.get("source_id"),
                    "source_origin_class": source_origin_class,
                    "exclusion_reason": "duplicate_task_id"
                    if task_id in seen_task_ids and verdict.get("mainline_counted")
                    else "not_mainline_real_origin_candidate",
                    "candidate_row_evaluation": verdict,
                }
            )

    source_mix = dict(sorted(Counter(str(row.get("source_id") or "") for row in selected_rows).items()))
    workflow_family_mix = dict(sorted(Counter(str(row.get("family_id") or "") for row in selected_rows).items()))
    complexity_mix = dict(sorted(Counter(str(row.get("complexity_tier") or "") for row in selected_rows).items()))
    max_single_source_share_pct = _max_source_share_pct(selected_rows)

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_real_origin_substrate_builder",
        "generated_at_utc": now_utc(),
        "status": "PASS" if selected_rows else "FAIL",
        "real_origin_substrate_candidate_count": len(selected_rows),
        "real_origin_substrate_candidate_table": selected_rows,
        "excluded_upstream_mainline_row_table": excluded_rows,
        "excluded_upstream_mainline_row_count": len(excluded_rows),
        "source_mix": source_mix,
        "workflow_family_mix": workflow_family_mix,
        "complexity_mix": complexity_mix,
        "max_single_source_share_pct": max_single_source_share_pct,
        "source_diversity_ceiling_preserved": max_single_source_share_pct <= READY_MAX_SINGLE_SOURCE_SHARE_PCT,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.3 Real-Origin Substrate Builder",
                "",
                f"- real_origin_substrate_candidate_count: `{len(selected_rows)}`",
                f"- max_single_source_share_pct: `{max_single_source_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.3 real-origin substrate candidate artifact.")
    parser.add_argument("--v102-pool-delta", default=str(DEFAULT_V102_POOL_DELTA_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v103_real_origin_substrate_builder(
        v102_pool_delta_path=str(args.v102_pool_delta),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "real_origin_substrate_candidate_count": payload.get("real_origin_substrate_candidate_count"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
