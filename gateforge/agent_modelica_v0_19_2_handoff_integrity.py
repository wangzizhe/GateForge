from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_19_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V190_CLOSEOUT_PATH,
    DEFAULT_V191_CLOSEOUT_PATH,
    EXPECTED_ALIGNMENT_SAMPLE_COUNT,
    EXPECTED_ALIGNMENT_STATUS,
    EXPECTED_BENCHMARK_MIN_CASES,
    EXPECTED_DIFFICULTY_STATUS,
    EXPECTED_V190_VERSION_DECISION,
    EXPECTED_V191_HANDOFF_MODE,
    EXPECTED_V191_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v192_handoff_integrity(
    *,
    v190_closeout_path: str = str(DEFAULT_V190_CLOSEOUT_PATH),
    v191_closeout_path: str = str(DEFAULT_V191_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v190 = load_json(v190_closeout_path)
    v191 = load_json(v191_closeout_path)
    v190_conclusion = v190.get("conclusion") or {}
    v190_alignment = v190.get("distribution_alignment_check") or {}
    v191_conclusion = v191.get("conclusion") or {}

    checks = {
        "v190_status_ok": str(v190.get("status") or "") == "PASS",
        "v190_version_decision_ok": str(v190_conclusion.get("version_decision") or "") == EXPECTED_V190_VERSION_DECISION,
        "v190_distribution_alignment_status_ok": str(v190_conclusion.get("distribution_alignment_status") or "") == EXPECTED_ALIGNMENT_STATUS,
        "v190_distribution_alignment_threshold_ok": bool(v190_alignment.get("threshold_passed")),
        "v190_distribution_alignment_sample_count_ok": int(v190_alignment.get("sample_count") or 0) == EXPECTED_ALIGNMENT_SAMPLE_COUNT,
        "v190_distribution_alignment_path_ok": str(v190_alignment.get("summary_path") or "").endswith("artifacts/distribution_alignment_v0_19_0/summary.json"),
        "v191_status_ok": str(v191.get("status") or "") == "PASS",
        "v191_version_decision_ok": str(v191_conclusion.get("version_decision") or "") == EXPECTED_V191_VERSION_DECISION,
        "v191_benchmark_pass_count_ok": int(v191_conclusion.get("benchmark_pass_count") or 0) >= EXPECTED_BENCHMARK_MIN_CASES,
        "v191_difficulty_status_ok": str(v191_conclusion.get("difficulty_calibration_status") or "") == EXPECTED_DIFFICULTY_STATUS,
        "v191_handoff_mode_ok": str(v191_conclusion.get("v0_19_2_handoff_mode") or "") == EXPECTED_V191_HANDOFF_MODE,
        "v191_frontier_agent_id_ok": str(v191_conclusion.get("frontier_agent_id") or "") != "",
    }
    handoff_integrity_status = "PASS" if all(checks.values()) else "FAIL"
    result = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": handoff_integrity_status,
        "handoff_integrity_status": handoff_integrity_status,
        "checks": checks,
        "upstream_v190_version_decision": str(v190_conclusion.get("version_decision") or ""),
        "upstream_v191_version_decision": str(v191_conclusion.get("version_decision") or ""),
        "upstream_benchmark_pass_count": int(v191_conclusion.get("benchmark_pass_count") or 0),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", result)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.2 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{handoff_integrity_status}`",
                f"- upstream_v191_version_decision: `{result['upstream_v191_version_decision']}`",
                f"- upstream_benchmark_pass_count: `{result['upstream_benchmark_pass_count']}`",
            ]
        ),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.2 handoff integrity artifact.")
    parser.add_argument("--v190-closeout", default=str(DEFAULT_V190_CLOSEOUT_PATH))
    parser.add_argument("--v191-closeout", default=str(DEFAULT_V191_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v192_handoff_integrity(
        v190_closeout_path=str(args.v190_closeout),
        v191_closeout_path=str(args.v191_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload["status"], "handoff_integrity_status": payload["handoff_integrity_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
