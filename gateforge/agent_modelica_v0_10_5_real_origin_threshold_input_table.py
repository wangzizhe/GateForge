from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_5_common import (
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_V104_CHARACTERIZATION_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v105_real_origin_threshold_input_table(
    *,
    v104_characterization_path: str = str(DEFAULT_V104_CHARACTERIZATION_PATH),
    out_dir: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR),
) -> dict:
    """Build the auditable threshold-input table from the frozen v0.10.4 characterized profile.

    Hard rule: this table is a frozen readout of upstream artifacts, not a recomputed profile.
    Case counts are derived by counting rows from case_characterization_table, not from re-running.
    """
    out_root = Path(out_dir)
    characterization = load_json(v104_characterization_path)
    case_table = list(characterization.get("case_characterization_table") or [])

    total = len(case_table)
    workflow_resolution_count = sum(1 for row in case_table if row.get("pilot_outcome") == "goal_level_resolved")
    surface_fix_only_count = sum(1 for row in case_table if row.get("pilot_outcome") == "surface_fix_only")
    goal_alignment_count = workflow_resolution_count + surface_fix_only_count
    unresolved_count = sum(1 for row in case_table if row.get("pilot_outcome") == "unresolved")

    # Percentage mirrors — display only; comparisons must use case counts
    workflow_resolution_rate_pct = round(workflow_resolution_count / total * 100, 1) if total else 0.0
    goal_alignment_rate_pct = round(goal_alignment_count / total * 100, 1) if total else 0.0
    surface_fix_only_rate_pct = round(surface_fix_only_count / total * 100, 1) if total else 0.0
    unresolved_rate_pct = round(unresolved_count / total * 100, 1) if total else 0.0

    replay_floor_sidecar = {
        "profile_run_count": characterization.get("profile_run_count"),
        "profile_non_success_unclassified_count": characterization.get("profile_non_success_unclassified_count"),
        "workflow_level_interpretable": characterization.get("workflow_level_interpretable"),
        "non_success_label_coverage_rate_pct": characterization.get("non_success_label_coverage_rate_pct"),
        "execution_source": characterization.get("execution_source"),
    }

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_real_origin_threshold_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS" if total > 0 else "FAIL",
        "real_origin_substrate_case_count": total,
        "workflow_resolution_case_count": workflow_resolution_count,
        "goal_alignment_case_count": goal_alignment_count,
        "surface_fix_only_case_count": surface_fix_only_count,
        "unresolved_case_count": unresolved_count,
        # Display-only percentage mirrors
        "workflow_resolution_rate_pct_display": workflow_resolution_rate_pct,
        "goal_alignment_rate_pct_display": goal_alignment_rate_pct,
        "surface_fix_only_rate_pct_display": surface_fix_only_rate_pct,
        "unresolved_rate_pct_display": unresolved_rate_pct,
        "profile_run_count": characterization.get("profile_run_count"),
        "profile_non_success_unclassified_count": characterization.get("profile_non_success_unclassified_count"),
        "replay_floor_sidecar": replay_floor_sidecar,
        "derivation_source": "frozen_v0_10_4_characterization_readout",
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.5 Real-Origin Threshold Input Table",
                "",
                f"- real_origin_substrate_case_count: `{total}`",
                f"- workflow_resolution_case_count: `{workflow_resolution_count}` ({workflow_resolution_rate_pct}%)",
                f"- goal_alignment_case_count: `{goal_alignment_count}` ({goal_alignment_rate_pct}%)",
                f"- surface_fix_only_case_count: `{surface_fix_only_count}` ({surface_fix_only_rate_pct}%)",
                f"- unresolved_case_count: `{unresolved_count}` ({unresolved_rate_pct}%)",
                f"- profile_run_count: `{characterization.get('profile_run_count')}`",
                f"- profile_non_success_unclassified_count: `{characterization.get('profile_non_success_unclassified_count')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.5 real-origin threshold input table.")
    parser.add_argument("--v104-characterization", default=str(DEFAULT_V104_CHARACTERIZATION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v105_real_origin_threshold_input_table(
        v104_characterization_path=str(args.v104_characterization),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "real_origin_substrate_case_count": payload.get("real_origin_substrate_case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
