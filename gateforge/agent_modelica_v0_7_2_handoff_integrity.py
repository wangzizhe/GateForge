from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V071_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v072_handoff_integrity(
    *,
    v071_closeout_path: str = str(DEFAULT_V071_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v071 = load_json(v071_closeout_path)
    conclusion = v071.get("conclusion") or {}
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS"
        if all(
            [
                conclusion.get("version_decision") == "v0_7_1_readiness_profile_ready",
                conclusion.get("profile_admission_status") == "ready",
                float(conclusion.get("legacy_bucket_mapping_rate_pct_after_live_run") or 0.0) >= 70.0,
                float(conclusion.get("spillover_share_pct_after_live_run") or 100.0) <= 25.0,
                float(conclusion.get("stable_coverage_share_pct") or 0.0) >= 40.0,
                str(conclusion.get("dominant_pressure_source") or "unknown") != "unknown",
            ]
        )
        else "FAIL",
        "ready_version": conclusion.get("version_decision") == "v0_7_1_readiness_profile_ready",
        "ready_admission": conclusion.get("profile_admission_status") == "ready",
        "legacy_mapping_ok": float(conclusion.get("legacy_bucket_mapping_rate_pct_after_live_run") or 0.0) >= 70.0,
        "spillover_ok": float(conclusion.get("spillover_share_pct_after_live_run") or 100.0) <= 25.0,
        "stable_core_ok": float(conclusion.get("stable_coverage_share_pct") or 0.0) >= 40.0,
        "dominant_pressure_source_recorded": str(conclusion.get("dominant_pressure_source") or "unknown") != "unknown",
        "dominant_pressure_source_from_v071": conclusion.get("dominant_pressure_source"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.2 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- dominant_pressure_source_from_v071: `{payload['dominant_pressure_source_from_v071']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.2 handoff integrity summary.")
    parser.add_argument("--v071-closeout", default=str(DEFAULT_V071_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v072_handoff_integrity(
        v071_closeout_path=str(args.v071_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
