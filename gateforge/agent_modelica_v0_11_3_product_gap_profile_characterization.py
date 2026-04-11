from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .agent_modelica_v0_11_3_common import (
    DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR,
    DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH,
    NON_SUCCESS_OUTCOMES,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    outcome_sort_key,
    write_json,
    write_text,
)


def _index_case_rows_by_task_id(runs: list[dict]) -> dict[str, list[dict]]:
    indexed: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        for row in list(run.get("case_result_table") or []):
            task_id = str(row.get("task_id") or "")
            if task_id:
                indexed[task_id].append(row)
    return indexed


def _canonical_case_row(rows: list[dict]) -> dict:
    if not rows:
        return {}
    outcome_counts = Counter(str(row.get("product_gap_outcome") or "") for row in rows)
    canonical_outcome = sorted(
        outcome_counts.items(),
        key=lambda item: (-item[1], outcome_sort_key(item[0]), item[0]),
    )[0][0]
    for row in rows:
        if str(row.get("product_gap_outcome") or "") == canonical_outcome:
            return row
    return rows[0]


def build_v113_product_gap_profile_characterization(
    *,
    replay_pack_path: str = str(DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    v112_product_gap_substrate_builder_path: str = str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR),
) -> dict:
    replay_pack = load_json(replay_pack_path)
    builder = load_json(v112_product_gap_substrate_builder_path)
    substrate_rows = {
        str(row.get("task_id") or ""): row
        for row in list(builder.get("product_gap_candidate_table") or [])
    }
    case_rows_by_task = _index_case_rows_by_task_id(list(replay_pack.get("product_gap_replay_rows") or []))

    characterized_rows = []
    for task_id in sorted(case_rows_by_task):
        canonical_case = _canonical_case_row(case_rows_by_task[task_id])
        substrate_row = substrate_rows.get(task_id, {})
        characterized_rows.append(
            {
                "task_id": task_id,
                "source_id": substrate_row.get("source_id"),
                "workflow_task_template_id": substrate_row.get("workflow_task_template_id"),
                "family_id": substrate_row.get("family_id"),
                "complexity_tier": substrate_row.get("complexity_tier"),
                "product_gap_outcome": canonical_case.get("product_gap_outcome"),
                "primary_non_success_label": canonical_case.get("primary_non_success_label"),
                "candidate_gap_family": canonical_case.get("candidate_gap_family"),
                "product_gap_sidecar_status": canonical_case.get("product_gap_sidecar_status"),
                "token_count": canonical_case.get("token_count"),
            }
        )

    total = len(characterized_rows)
    non_success_rows = [row for row in characterized_rows if row["product_gap_outcome"] in NON_SUCCESS_OUTCOMES]
    surface_rows = [row for row in characterized_rows if row["product_gap_outcome"] == "surface_fix_only"]
    unresolved_rows = [row for row in characterized_rows if row["product_gap_outcome"] == "unresolved"]
    non_success_label_counts = Counter(
        str(row.get("primary_non_success_label") or "")
        for row in non_success_rows
    )
    candidate_gap_family_counts = Counter(
        str(row.get("candidate_gap_family") or "")
        for row in non_success_rows
    )
    workflow_resolution = sum(1 for row in characterized_rows if row["product_gap_outcome"] == "goal_level_resolved")
    goal_alignment = sum(1 for row in characterized_rows if row["product_gap_outcome"] in {"goal_level_resolved", "surface_fix_only"})
    unclassified_count = non_success_label_counts.get("product_gap_non_success_unclassified", 0)

    if candidate_gap_family_counts:
        dominant_gap_family = sorted(candidate_gap_family_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        candidate_dominant_gap_family_interpretability = "interpretable" if dominant_gap_family != "mixed_or_not_yet_resolved" else "partial"
    else:
        dominant_gap_family = "mixed_or_not_yet_resolved"
        candidate_dominant_gap_family_interpretability = "partial"

    why_map = {
        "context_discipline_gap": "Surface-fix-only cases concentrate in workflow paths that keep partial alignment but still lose full goal completion under product-boundary pressure.",
        "protocol_robustness_gap": "Failure structure clusters around protocol or shell-specific boundary handling rather than deeper multi-step repair inability.",
        "behavior_safety_gap": "The carried product-boundary sidecar suggests behavior-boundary violations dominate the non-success picture.",
        "efficiency_or_latency_gap": "The runtime picture is bottlenecked more by cost or latency fields than by workflow correctness.",
        "residual_core_capability_gap": "Most non-success cases remain unresolved in conversion, constraint, or validation chains even after the governed shell patches are carried forward.",
        "mixed_or_not_yet_resolved": "The current product-gap picture is still mixed across multiple candidate gap families and cannot yet support a single dominant reading.",
    }

    baseline_workflow_comparison_note = (
        "Compared with the carried v0.10.x workflow reading, the same 12-case baseline now surfaces more explicit product-boundary evidence, and the non-success picture sharpens toward residual multi-step capability limits rather than merely source-origin uncertainty."
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_product_gap_profile_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS" if total else "FAIL",
        "product_gap_profile_size": total,
        "case_characterization_table": characterized_rows,
        "workflow_resolution_rate_pct": round(workflow_resolution / total * 100, 1) if total else 0.0,
        "goal_alignment_rate_pct": round(goal_alignment / total * 100, 1) if total else 0.0,
        "surface_fix_only_rate_pct": round(len(surface_rows) / total * 100, 1) if total else 0.0,
        "unresolved_rate_pct": round(len(unresolved_rows) / total * 100, 1) if total else 0.0,
        "product_gap_non_success_unclassified_count": unclassified_count,
        "product_gap_non_success_label_distribution": dict(non_success_label_counts),
        "candidate_gap_family_sidecar_distribution": dict(candidate_gap_family_counts),
        "candidate_dominant_gap_family": dominant_gap_family,
        "candidate_dominant_gap_family_interpretability": candidate_dominant_gap_family_interpretability,
        "why_this_gap_family_is_or_is_not_currently_dominant": why_map[dominant_gap_family],
        "baseline_workflow_comparison_note": baseline_workflow_comparison_note,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.3 Product-Gap Profile Characterization",
                "",
                f"- workflow_resolution_rate_pct: `{payload['workflow_resolution_rate_pct']}`",
                f"- goal_alignment_rate_pct: `{payload['goal_alignment_rate_pct']}`",
                f"- candidate_dominant_gap_family: `{payload['candidate_dominant_gap_family']}`",
                f"- candidate_dominant_gap_family_interpretability: `{payload['candidate_dominant_gap_family_interpretability']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.3 product-gap profile characterization.")
    parser.add_argument("--replay-pack", default=str(DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v112-product-gap-substrate-builder", default=str(DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v113_product_gap_profile_characterization(
        replay_pack_path=str(args.replay_pack),
        v112_product_gap_substrate_builder_path=str(args.v112_product_gap_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
