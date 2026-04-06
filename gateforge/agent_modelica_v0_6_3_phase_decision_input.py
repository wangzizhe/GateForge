from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_3_common import (
    DEFAULT_DECISION_INPUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V062_LIVE_RUN_PATH,
    DEFAULT_V062_PROFILE_STABILITY_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_3_handoff_integrity import build_v063_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_phase_decision_input"


def build_v063_phase_decision_input(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    profile_stability_path: str = str(DEFAULT_V062_PROFILE_STABILITY_PATH),
    live_run_path: str = str(DEFAULT_V062_LIVE_RUN_PATH),
    out_dir: str = str(DEFAULT_DECISION_INPUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v063_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    stability = load_json(profile_stability_path)
    live_run = load_json(live_run_path)
    rows = live_run.get("case_result_table") if isinstance(live_run.get("case_result_table"), list) else []

    total = len(rows)
    bounded_uncovered_count = sum(1 for row in rows if row.get("assigned_bucket") == "bounded_uncovered_subtype_candidate")
    spillover_count = sum(1 for row in rows if row.get("assigned_bucket") == "topology_or_open_world_spillover")

    bounded_uncovered_signal_share_pct = round((100.0 * bounded_uncovered_count / total), 1) if total else 0.0
    topology_or_open_world_spillover_share_pct = round((100.0 * spillover_count / total), 1) if total else 0.0

    phase_decision_input_table = {
        "stable_coverage_share_pct": stability.get("stable_coverage_share_pct"),
        "fragile_coverage_share_pct": stability.get("fragile_coverage_share_pct"),
        "limited_or_uncovered_share_pct": stability.get("limited_or_uncovered_share_pct"),
        "legacy_taxonomy_still_sufficient": stability.get("legacy_taxonomy_still_sufficient"),
        "fluid_network_extension_status_under_representative_pressure": stability.get("fluid_network_extension_status_under_representative_pressure"),
        "bounded_uncovered_signal_share_pct": bounded_uncovered_signal_share_pct,
        "topology_or_open_world_spillover_share_pct": topology_or_open_world_spillover_share_pct,
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity.get("status") == "PASS" else "FAIL",
        "phase_decision_input_table": phase_decision_input_table,
        "stable_coverage_share_pct": stability.get("stable_coverage_share_pct"),
        "fragile_coverage_share_pct": stability.get("fragile_coverage_share_pct"),
        "limited_or_uncovered_share_pct": stability.get("limited_or_uncovered_share_pct"),
        "legacy_taxonomy_still_sufficient": stability.get("legacy_taxonomy_still_sufficient"),
        "fluid_network_extension_status_under_representative_pressure": stability.get("fluid_network_extension_status_under_representative_pressure"),
        "bounded_uncovered_signal_share_pct": bounded_uncovered_signal_share_pct,
        "topology_or_open_world_spillover_share_pct": topology_or_open_world_spillover_share_pct,
        "why_current_profile_supports_or_does_not_support_open_world_candidate": (
            "The current stable authority profile is representative and taxonomy-stable, "
            "but only 47.2% of cases remain in covered_success and the promoted family "
            "extension remains fragile rather than fully stable."
        ),
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.3 Phase Decision Input",
                "",
                f"- stable_coverage_share_pct: `{payload.get('stable_coverage_share_pct')}`",
                f"- bounded_uncovered_signal_share_pct: `{bounded_uncovered_signal_share_pct}`",
                f"- topology_or_open_world_spillover_share_pct: `{topology_or_open_world_spillover_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.3 phase decision input table.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-stability", default=str(DEFAULT_V062_PROFILE_STABILITY_PATH))
    parser.add_argument("--live-run", default=str(DEFAULT_V062_LIVE_RUN_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_DECISION_INPUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v063_phase_decision_input(
        handoff_integrity_path=str(args.handoff_integrity),
        profile_stability_path=str(args.profile_stability),
        live_run_path=str(args.live_run),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "stable_coverage_share_pct": payload.get("stable_coverage_share_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
