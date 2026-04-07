from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_6_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V075_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v076_handoff_integrity(
    *,
    v075_closeout_path: str = str(DEFAULT_V075_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v075_closeout_path)
    conclusion = closeout.get("conclusion") or {}

    correct_version = (
        conclusion.get("version_decision")
        == "v0_7_5_open_world_readiness_partial_but_interpretable"
    )
    correct_status = (
        conclusion.get("readiness_refinement_status") == "partial_but_interpretable"
    )
    bounded_uncovered_subcritical = conclusion.get("bounded_uncovered_still_subcritical") is True
    remaining_gap_single = conclusion.get("remaining_gap_count_after_refinement") == 1
    dominant_gap_matches = (
        conclusion.get("dominant_remaining_gap_after_refinement")
        == "stable_coverage_below_supported_floor"
    )

    all_ok = all(
        [
            correct_version,
            correct_status,
            bounded_uncovered_subcritical,
            remaining_gap_single,
            dominant_gap_matches,
        ]
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if all_ok else "FAIL",
        "correct_version": correct_version,
        "correct_status": correct_status,
        "bounded_uncovered_still_subcritical": bounded_uncovered_subcritical,
        "remaining_gap_single": remaining_gap_single,
        "dominant_gap_matches": dominant_gap_matches,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.6 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- correct_version: `{correct_version}`",
                f"- correct_status: `{correct_status}`",
                f"- bounded_uncovered_still_subcritical: `{bounded_uncovered_subcritical}`",
                f"- remaining_gap_single: `{remaining_gap_single}`",
                f"- dominant_gap_matches: `{dominant_gap_matches}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.6 handoff integrity audit.")
    parser.add_argument("--v075-closeout", default=str(DEFAULT_V075_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v076_handoff_integrity(
        v075_closeout_path=str(args.v075_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
