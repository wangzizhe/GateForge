from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V073_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v074_handoff_integrity(
    *,
    v073_closeout_path: str = str(DEFAULT_V073_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v073_closeout_path)
    conclusion = closeout.get("conclusion") or {}

    ready_version = conclusion.get("version_decision") == "v0_7_3_phase_decision_inputs_ready"
    ready_status = conclusion.get("decision_input_status") == "ready"
    stable_coverage_recorded = conclusion.get("stable_coverage_share_pct_stable") is not None
    spillover_recorded = conclusion.get("spillover_share_pct_stable") is not None
    legacy_mapping_recorded = conclusion.get("legacy_bucket_mapping_rate_pct_stable") is not None
    gap_summary_recorded = conclusion.get("open_world_candidate_gap_summary") is not None
    supported_floor_recorded = conclusion.get("v0_7_4_open_world_readiness_supported_floor") is not None
    partial_floor_recorded = conclusion.get("v0_7_4_open_world_readiness_partial_floor") is not None
    fallback_floor_recorded = conclusion.get("v0_7_4_fallback_to_targeted_expansion_floor") is not None

    all_ok = all(
        [
            ready_version,
            ready_status,
            stable_coverage_recorded,
            spillover_recorded,
            legacy_mapping_recorded,
            gap_summary_recorded,
            supported_floor_recorded,
            partial_floor_recorded,
            fallback_floor_recorded,
        ]
    )
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if all_ok else "FAIL",
        "ready_version": ready_version,
        "ready_status": ready_status,
        "stable_coverage_recorded": stable_coverage_recorded,
        "spillover_recorded": spillover_recorded,
        "legacy_mapping_recorded": legacy_mapping_recorded,
        "gap_summary_recorded": gap_summary_recorded,
        "supported_floor_recorded": supported_floor_recorded,
        "partial_floor_recorded": partial_floor_recorded,
        "fallback_floor_recorded": fallback_floor_recorded,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.4 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- ready_version: `{ready_version}`",
                f"- ready_status: `{ready_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.4 handoff integrity audit.")
    parser.add_argument("--v073-closeout", default=str(DEFAULT_V073_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v074_handoff_integrity(
        v073_closeout_path=str(args.v073_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
