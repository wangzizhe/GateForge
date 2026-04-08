from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_0_common import (
    AUDIT_DEGRADED_MIN,
    AUDIT_PROMOTED_MIN,
    DEFAULT_PILOT_PROFILE_OUT_DIR,
    DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR,
    GOAL_SPECIFIC_RATE_PROMOTED_MIN,
    GOAL_SPECIFIC_TASK_COUNT_DEGRADED_MIN,
    LEGACY_BUCKET_MAPPING_RATE_MIN,
    SCHEMA_PREFIX,
    SPILLOVER_SHARE_MAX,
    TASK_COUNT_MIN,
    UNCLASSIFIED_PENDING_MAX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v080_workflow_substrate_admission(
    *,
    substrate_path: str = str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR / "summary.json"),
    pilot_profile_path: str = str(DEFAULT_PILOT_PROFILE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR),
) -> dict:
    substrate = load_json(substrate_path)
    pilot = load_json(pilot_profile_path)

    workflow_pass = float(substrate.get("workflow_proximity_audit_pass_rate_pct") or 0.0)
    goal_framing = float(substrate.get("goal_level_framing_rate_pct") or 0.0)
    contextual = float(substrate.get("contextual_plausibility_rate_pct") or 0.0)
    non_trivial = float(substrate.get("non_trivial_from_context_rate_pct") or 0.0)
    goal_specific_rate = float(substrate.get("goal_specific_check_rate_pct") or 0.0)
    goal_specific_count = int(substrate.get("goal_specific_check_task_count") or 0)
    task_count = int(substrate.get("task_count") or 0)
    mapping = float(pilot.get("legacy_bucket_mapping_rate_pct") or 0.0)
    spillover = float(pilot.get("spillover_share_pct") or 0.0)
    unclassified = int(pilot.get("unclassified_pending_taxonomy_count") or 0)
    goal_context_required = bool(pilot.get("workflow_resolution_rate_requires_goal_context"))
    oracle_frozen = bool(pilot.get("goal_level_resolution_criterion_frozen"))
    delta_rate = float(pilot.get("workflow_proximity_delta_vs_v0_7_rate_pct") or 0.0)

    invalid = any(
        [
            workflow_pass < AUDIT_DEGRADED_MIN,
            goal_framing < AUDIT_DEGRADED_MIN,
            contextual < AUDIT_DEGRADED_MIN,
            non_trivial < AUDIT_DEGRADED_MIN,
            goal_specific_count < GOAL_SPECIFIC_TASK_COUNT_DEGRADED_MIN,
            task_count < TASK_COUNT_MIN,
            mapping < LEGACY_BUCKET_MAPPING_RATE_MIN,
            spillover > SPILLOVER_SHARE_MAX,
            unclassified > UNCLASSIFIED_PENDING_MAX,
            not oracle_frozen,
        ]
    )
    ready = all(
        [
            workflow_pass >= AUDIT_PROMOTED_MIN,
            goal_framing >= AUDIT_PROMOTED_MIN,
            contextual >= AUDIT_PROMOTED_MIN,
            non_trivial >= AUDIT_PROMOTED_MIN,
            goal_specific_rate >= GOAL_SPECIFIC_RATE_PROMOTED_MIN,
            task_count >= TASK_COUNT_MIN,
            mapping >= LEGACY_BUCKET_MAPPING_RATE_MIN,
            spillover <= SPILLOVER_SHARE_MAX,
            unclassified <= UNCLASSIFIED_PENDING_MAX,
            goal_context_required,
            delta_rate >= AUDIT_PROMOTED_MIN,
            oracle_frozen,
        ]
    )
    if invalid:
        status = "invalid"
    elif ready:
        status = "ready"
    else:
        status = "partial"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_workflow_substrate_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"ready", "partial"} else "FAIL",
        "workflow_substrate_admission_status": status,
        "workflow_proximity_audit_pass_rate_pct": workflow_pass,
        "goal_specific_check_rate_pct": goal_specific_rate,
        "legacy_bucket_mapping_rate_pct": mapping,
        "spillover_share_pct": spillover,
        "unclassified_pending_taxonomy_count": unclassified,
        "workflow_resolution_rate_requires_goal_context": goal_context_required,
        "goal_level_success_definition_frozen": oracle_frozen,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.0 Workflow Substrate Admission",
                "",
                f"- workflow_substrate_admission_status: `{status}`",
                f"- workflow_proximity_audit_pass_rate_pct: `{workflow_pass}`",
                f"- goal_specific_check_rate_pct: `{goal_specific_rate}`",
                f"- legacy_bucket_mapping_rate_pct: `{mapping}`",
                f"- spillover_share_pct: `{spillover}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.0 workflow substrate admission summary.")
    parser.add_argument(
        "--substrate-path",
        default=str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--pilot-profile",
        default=str(DEFAULT_PILOT_PROFILE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v080_workflow_substrate_admission(
        substrate_path=str(args.substrate_path),
        pilot_profile_path=str(args.pilot_profile),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
