from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_0_common import (
    DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR,
    DEFAULT_V060_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TASK_COUNT_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)


_TASK_ROWS = [
    {"task_id": "v070_case_01", "family_id": "component_api_alignment", "complexity_tier": "simple", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_02", "family_id": "component_api_alignment", "complexity_tier": "simple", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_03", "family_id": "component_api_alignment", "complexity_tier": "medium", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_04", "family_id": "component_api_alignment", "complexity_tier": "complex", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
    {"task_id": "v070_case_05", "family_id": "component_api_alignment", "complexity_tier": "complex", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "clean"},
    {"task_id": "v070_case_06", "family_id": "local_interface_alignment", "complexity_tier": "simple", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_07", "family_id": "local_interface_alignment", "complexity_tier": "medium", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_08", "family_id": "local_interface_alignment", "complexity_tier": "medium", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "covered_but_fragile", "dispatch_risk": "clean"},
    {"task_id": "v070_case_09", "family_id": "local_interface_alignment", "complexity_tier": "complex", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
    {"task_id": "v070_case_10", "family_id": "local_interface_alignment", "complexity_tier": "complex", "curation_class": "open_world_adjacent", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "clean"},
    {"task_id": "v070_case_11", "family_id": "local_interface_alignment", "complexity_tier": "complex", "curation_class": "open_world_adjacent", "legacy_bucket_hint": "unclassified_pending_taxonomy", "dispatch_risk": "clean"},
    {"task_id": "v070_case_12", "family_id": "medium_redeclare_alignment", "complexity_tier": "simple", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_13", "family_id": "medium_redeclare_alignment", "complexity_tier": "medium", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_14", "family_id": "medium_redeclare_alignment", "complexity_tier": "medium", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "covered_but_fragile", "dispatch_risk": "clean"},
    {"task_id": "v070_case_15", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "bounded_uncovered_subtype_candidate", "dispatch_risk": "clean"},
    {"task_id": "v070_case_16", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "curation_class": "open_world_adjacent", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "clean"},
    {"task_id": "v070_case_17", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "curation_class": "open_world_adjacent", "legacy_bucket_hint": "unclassified_pending_taxonomy", "dispatch_risk": "clean"},
    {"task_id": "v070_case_18", "family_id": "component_api_alignment", "complexity_tier": "medium", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
    {"task_id": "v070_case_19", "family_id": "local_interface_alignment", "complexity_tier": "medium", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
    {"task_id": "v070_case_20", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "curation_class": "weakly_curated_mix", "legacy_bucket_hint": "bounded_uncovered_subtype_candidate", "dispatch_risk": "clean"},
    {"task_id": "v070_case_21", "family_id": "component_api_alignment", "complexity_tier": "complex", "curation_class": "open_world_adjacent", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "ambiguous"},
    {"task_id": "v070_case_22", "family_id": "local_interface_alignment", "complexity_tier": "simple", "curation_class": "natural_core", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
]


def build_v070_open_world_adjacent_substrate(
    *,
    v060_closeout_path: str = str(DEFAULT_V060_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR),
) -> dict:
    v060 = load_json(v060_closeout_path)
    v060_task_count = ((v060.get("block_a_substrate") or {}).get("case_count")) or 24
    task_count = len(_TASK_ROWS)

    curation_counts = {
        "natural_core": sum(1 for row in _TASK_ROWS if row["curation_class"] == "natural_core"),
        "weakly_curated_mix": sum(1 for row in _TASK_ROWS if row["curation_class"] == "weakly_curated_mix"),
        "open_world_adjacent": sum(1 for row in _TASK_ROWS if row["curation_class"] == "open_world_adjacent"),
    }
    family_breakdown = {}
    complexity_breakdown = {}
    for row in _TASK_ROWS:
        family_breakdown[row["family_id"]] = family_breakdown.get(row["family_id"], 0) + 1
        complexity_breakdown[row["complexity_tier"]] = complexity_breakdown.get(row["complexity_tier"], 0) + 1

    weaker_curation_metric = round(
        (curation_counts["weakly_curated_mix"] + curation_counts["open_world_adjacent"]) / task_count * 100,
        1,
    )
    weaker_curation_metric_vs_v0_6 = round(weaker_curation_metric - 41.7, 1)
    weaker_curation_confirmed = weaker_curation_metric >= 50.0 and curation_counts["open_world_adjacent"] >= 4

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_open_world_adjacent_substrate",
        "generated_at_utc": now_utc(),
        "status": "PASS" if weaker_curation_confirmed and task_count >= TASK_COUNT_MIN else "FAIL",
        "open_world_adjacent_substrate_frozen": True,
        "task_count": task_count,
        "task_count_vs_v0_6": task_count - v060_task_count,
        "family_breakdown": family_breakdown,
        "complexity_breakdown": complexity_breakdown,
        "curation_class_breakdown": curation_counts,
        "weaker_curation_audit": (
            "The substrate no longer preserves family/complexity balance case-by-case. "
            "It deliberately allows naturally uneven pressure and open-world-adjacent spillover "
            "while retaining auditable bucket mapping."
        ),
        "representativeness_vs_workflow_boundary": (
            "This substrate weakens error-distribution curation relative to v0.6.x, "
            "but it is still an error-distribution claim rather than a user-workflow claim."
        ),
        "why_less_case_balanced_than_v0_6": (
            "v0.6.x enforced representative balancing across families and complexity tiers. "
            "v0.7.0 admits uneven family pressure, repeated complex-tier pressure, and open-world-adjacent "
            "cases without restoring per-case balance."
        ),
        "weaker_curation_metric": weaker_curation_metric,
        "weaker_curation_metric_vs_v0_6": weaker_curation_metric_vs_v0_6,
        "weaker_curation_confirmed": weaker_curation_confirmed,
        "task_rows": _TASK_ROWS,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.0 Open-World-Adjacent Substrate",
                "",
                f"- status: `{payload['status']}`",
                f"- task_count: `{task_count}`",
                f"- weaker_curation_metric: `{weaker_curation_metric}`",
                f"- weaker_curation_metric_vs_v0_6: `{weaker_curation_metric_vs_v0_6}`",
                f"- weaker_curation_confirmed: `{weaker_curation_confirmed}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.0 open-world-adjacent substrate.")
    parser.add_argument("--v060-closeout", default=str(DEFAULT_V060_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v070_open_world_adjacent_substrate(
        v060_closeout_path=str(args.v060_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
