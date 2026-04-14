from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_19_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V190_CLOSEOUT_PATH,
    EXPECTED_ALIGNMENT_SAMPLE_COUNT,
    EXPECTED_DISTRIBUTION_ALIGNMENT_STATUS,
    EXPECTED_V190_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v191_handoff_integrity(
    *,
    v190_closeout_path: str = str(DEFAULT_V190_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    payload = load_json(v190_closeout_path)
    conclusion = payload.get("conclusion") or {}
    alignment = payload.get("distribution_alignment_check") or {}
    checks = {
        "status_ok": str(payload.get("status") or "") == "PASS",
        "version_decision_ok": str(conclusion.get("version_decision") or "") == EXPECTED_V190_VERSION_DECISION,
        "taxonomy_frozen_ok": bool(conclusion.get("taxonomy_frozen")),
        "stop_signal_frozen_ok": bool(conclusion.get("stop_signal_frozen")),
        "trajectory_schema_frozen_ok": bool(conclusion.get("trajectory_schema_frozen")),
        "distribution_alignment_status_ok": str(conclusion.get("distribution_alignment_status") or "") == EXPECTED_DISTRIBUTION_ALIGNMENT_STATUS,
        "distribution_alignment_threshold_ok": bool(alignment.get("threshold_passed")),
        "distribution_alignment_sample_count_ok": int(alignment.get("sample_count") or 0) == EXPECTED_ALIGNMENT_SAMPLE_COUNT,
    }
    handoff_integrity_status = "PASS" if all(checks.values()) else "FAIL"
    result = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": handoff_integrity_status,
        "handoff_integrity_status": handoff_integrity_status,
        "checks": checks,
        "upstream_version_decision": str(conclusion.get("version_decision") or ""),
        "upstream_distribution_alignment_status": str(conclusion.get("distribution_alignment_status") or ""),
        "upstream_distribution_alignment_sample_count": int(alignment.get("sample_count") or 0),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", result)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{handoff_integrity_status}`",
                f"- upstream_version_decision: `{result['upstream_version_decision']}`",
            ]
        ),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.1 handoff integrity artifact.")
    parser.add_argument("--v190-closeout", default=str(DEFAULT_V190_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v191_handoff_integrity(v190_closeout_path=str(args.v190_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload["status"], "handoff_integrity_status": payload["handoff_integrity_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
