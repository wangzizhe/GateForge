from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_3_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V072_CLOSEOUT_PATH,
    LEGACY_BUCKET_MAPPING_PARTIAL_MIN,
    SCHEMA_PREFIX,
    SPILLOVER_PARTIAL_MAX,
    STABLE_COVERAGE_READY_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v073_handoff_integrity(
    *,
    v072_closeout_path: str = str(DEFAULT_V072_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v072_closeout_path)
    conclusion = closeout.get("conclusion") or {}

    ready_version = conclusion.get("version_decision") == "v0_7_2_readiness_profile_stable"
    stable_status = conclusion.get("profile_stability_status") == "stable"
    legacy_mapping_ok = float(conclusion.get("legacy_bucket_mapping_rate_pct_after_extension") or 0.0) >= LEGACY_BUCKET_MAPPING_PARTIAL_MIN
    spillover_ok = float(conclusion.get("spillover_share_pct_after_extension") or 100.0) <= SPILLOVER_PARTIAL_MAX
    stable_core_ok = float(conclusion.get("stable_coverage_share_pct_after_extension") or 0.0) >= STABLE_COVERAGE_READY_MIN
    dominant_pressure_recorded = str(conclusion.get("dominant_pressure_source_after_extension") or "unknown") != "unknown"

    all_ok = all(
        [
            ready_version,
            stable_status,
            legacy_mapping_ok,
            spillover_ok,
            stable_core_ok,
            dominant_pressure_recorded,
        ]
    )
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if all_ok else "FAIL",
        "ready_version": ready_version,
        "stable_status": stable_status,
        "legacy_mapping_ok": legacy_mapping_ok,
        "spillover_ok": spillover_ok,
        "stable_core_ok": stable_core_ok,
        "dominant_pressure_recorded": dominant_pressure_recorded,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.3 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- ready_version: `{ready_version}`",
                f"- stable_status: `{stable_status}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.3 handoff integrity audit.")
    parser.add_argument("--v072-closeout", default=str(DEFAULT_V072_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v073_handoff_integrity(
        v072_closeout_path=str(args.v072_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
