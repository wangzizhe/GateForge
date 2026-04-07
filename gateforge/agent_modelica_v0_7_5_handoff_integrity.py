from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V074_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v075_handoff_integrity(
    *,
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v074_closeout_path)
    conclusion = closeout.get("conclusion") or {}

    correct_version = (
        conclusion.get("version_decision")
        == "v0_7_4_open_world_readiness_partial_but_interpretable"
    )
    correct_status = (
        conclusion.get("readiness_adjudication_status") == "partial_but_interpretable"
    )
    supported_floor_was_false = conclusion.get("supported_floor_passed") is False
    partial_floor_was_true = conclusion.get("partial_floor_passed") is True
    fallback_floor_was_false = conclusion.get("fallback_floor_passed") is False
    dominant_recorded = (
        conclusion.get("dominant_pressure_source_reference") not in (None, "unknown")
    )

    all_ok = all(
        [
            correct_version,
            correct_status,
            supported_floor_was_false,
            partial_floor_was_true,
            fallback_floor_was_false,
            dominant_recorded,
        ]
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if all_ok else "FAIL",
        "correct_version": correct_version,
        "correct_status": correct_status,
        "supported_floor_was_false": supported_floor_was_false,
        "partial_floor_was_true": partial_floor_was_true,
        "fallback_floor_was_false": fallback_floor_was_false,
        "dominant_recorded": dominant_recorded,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.5 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- correct_version: `{correct_version}`",
                f"- correct_status: `{correct_status}`",
                f"- supported_floor_was_false: `{supported_floor_was_false}`",
                f"- partial_floor_was_true: `{partial_floor_was_true}`",
                f"- fallback_floor_was_false: `{fallback_floor_was_false}`",
                f"- dominant_recorded: `{dominant_recorded}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.5 handoff integrity audit.")
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v075_handoff_integrity(
        v074_closeout_path=str(args.v074_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
