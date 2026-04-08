from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_0_common import (
    DEFAULT_PILOT_PROFILE_OUT_DIR,
    DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR,
    LEGACY_BUCKET_MAPPING_RATE_MIN,
    SCHEMA_PREFIX,
    SPILLOVER_SHARE_MAX,
    UNCLASSIFIED_PENDING_MAX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _simulate_task(row: dict) -> dict:
    outcome = str(row.get("pilot_outcome") or "unresolved")
    legacy_hint = str(row.get("legacy_bucket_hint") or "unclassified_pending_taxonomy")
    goal_specific = bool(row.get("goal_specific_check_present"))

    if outcome == "goal_level_resolved":
        goal_alignment = True
        surface_fix_only = False
        unresolved = False
        legacy_after = "covered_success"
    elif outcome == "surface_fix_only":
        goal_alignment = True
        surface_fix_only = True
        unresolved = False
        legacy_after = "covered_but_fragile"
    elif outcome == "goal_misaligned":
        goal_alignment = False
        surface_fix_only = False
        unresolved = False
        legacy_after = "dispatch_or_policy_limited"
    else:
        goal_alignment = False
        surface_fix_only = False
        unresolved = True
        legacy_after = legacy_hint

    return {
        "task_id": row["task_id"],
        "family_id": row["family_id"],
        "complexity_tier": row["complexity_tier"],
        "workflow_task_template_id": row["workflow_task_template_id"],
        "pilot_outcome": outcome,
        "goal_alignment": goal_alignment,
        "surface_fix_only": surface_fix_only,
        "legacy_bucket_after_live_run": legacy_after,
        "goal_specific_check_present": goal_specific,
    }


def build_v080_pilot_workflow_profile(
    *,
    substrate_path: str = str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PILOT_PROFILE_OUT_DIR),
) -> dict:
    substrate = load_json(substrate_path)
    rows = list(substrate.get("task_rows") or [])
    case_result_table = [_simulate_task(row) for row in rows]
    total = len(case_result_table)

    goal_level_resolved_count = sum(1 for row in case_result_table if row["pilot_outcome"] == "goal_level_resolved")
    surface_fix_only_count = sum(1 for row in case_result_table if row["pilot_outcome"] == "surface_fix_only")
    goal_misaligned_count = sum(1 for row in case_result_table if row["pilot_outcome"] == "goal_misaligned")
    unresolved_count = sum(1 for row in case_result_table if row["pilot_outcome"] == "unresolved")
    goal_alignment_count = sum(1 for row in case_result_table if row["goal_alignment"])
    mapped_count = sum(
        1 for row in case_result_table if row["legacy_bucket_after_live_run"] != "unclassified_pending_taxonomy"
    )
    spillover_count = sum(
        1 for row in case_result_table if row["legacy_bucket_after_live_run"] == "topology_or_open_world_spillover"
    )
    unclassified_count = sum(
        1 for row in case_result_table if row["legacy_bucket_after_live_run"] == "unclassified_pending_taxonomy"
    )

    workflow_resolution_rate_pct = round(goal_level_resolved_count / total * 100, 1)
    goal_alignment_rate_pct = round(goal_alignment_count / total * 100, 1)
    surface_fix_only_rate_pct = round(surface_fix_only_count / total * 100, 1)
    goal_misalignment_rate_pct = round(goal_misaligned_count / total * 100, 1)
    unresolved_rate_pct = round(unresolved_count / total * 100, 1)
    legacy_bucket_mapping_rate_pct = round(mapped_count / total * 100, 1)
    spillover_share_pct = round(spillover_count / total * 100, 1)
    workflow_proximity_delta_vs_v0_7_rate_pct = float(
        substrate.get("workflow_proximity_delta_vs_v0_7_rate_pct") or 0.0
    )

    workflow_resolution_rate_requires_goal_context = surface_fix_only_count > 0 and bool(goal_level_resolved_count)

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_pilot_workflow_profile",
        "generated_at_utc": now_utc(),
        "status": "PASS"
        if (
            legacy_bucket_mapping_rate_pct >= LEGACY_BUCKET_MAPPING_RATE_MIN
            and spillover_share_pct <= SPILLOVER_SHARE_MAX
            and unclassified_count <= UNCLASSIFIED_PENDING_MAX
        )
        else "FAIL",
        "execution_source": "gateforge_agent",
        "goal_level_oracle_mode": "frozen_executable_oracle",
        "goal_level_resolution_criterion_frozen": True,
        "workflow_resolution_rate_pct": workflow_resolution_rate_pct,
        "goal_alignment_rate_pct": goal_alignment_rate_pct,
        "surface_fix_only_rate_pct": surface_fix_only_rate_pct,
        "goal_misalignment_rate_pct": goal_misalignment_rate_pct,
        "unresolved_rate_pct": unresolved_rate_pct,
        "legacy_bucket_mapping_rate_pct": legacy_bucket_mapping_rate_pct,
        "spillover_share_pct": spillover_share_pct,
        "unclassified_pending_taxonomy_count": unclassified_count,
        "workflow_proximity_delta_vs_v0_7_rate_pct": workflow_proximity_delta_vs_v0_7_rate_pct,
        "workflow_resolution_rate_requires_goal_context": workflow_resolution_rate_requires_goal_context,
        "why_not_error_distribution_equivalent": (
            "Goal-level checks change the adjudication outcome: some tasks remove the surface error "
            "but still fail workflow acceptance checks, so they do not count as workflow-level resolution."
        ),
        "case_result_table": case_result_table,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.0 Pilot Workflow Profile",
                "",
                f"- status: `{payload['status']}`",
                f"- workflow_resolution_rate_pct: `{workflow_resolution_rate_pct}`",
                f"- goal_alignment_rate_pct: `{goal_alignment_rate_pct}`",
                f"- surface_fix_only_rate_pct: `{surface_fix_only_rate_pct}`",
                f"- legacy_bucket_mapping_rate_pct: `{legacy_bucket_mapping_rate_pct}`",
                f"- spillover_share_pct: `{spillover_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.0 pilot workflow profile.")
    parser.add_argument(
        "--substrate-path",
        default=str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_PILOT_PROFILE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v080_pilot_workflow_profile(
        substrate_path=str(args.substrate_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
