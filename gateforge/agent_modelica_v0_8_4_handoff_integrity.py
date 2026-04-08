from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V083_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v084_handoff_integrity(
    *,
    v083_closeout_path: str = str(DEFAULT_V083_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v083_closeout_path)
    conclusion = closeout.get("conclusion") or {}
    handoff = closeout.get("handoff_integrity") or {}
    validation_summary = closeout.get("threshold_validation_summary") or {}

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == "v0_8_3_threshold_pack_validated",
        "handoff_mode_ok": conclusion.get("v0_8_4_handoff_mode") == "run_late_workflow_readiness_adjudication",
        "upstream_validation_status_ok": validation_summary.get("same_logic_validation_status") == "validated",
        "baseline_route_ok": conclusion.get("current_baseline_route_observed")
        == "workflow_readiness_partial_but_interpretable",
        "execution_source_ok": handoff.get("upstream_execution_source") == "gateforge_run_contract_live_path",
        "pack_overlap_absent_ok": not bool(validation_summary.get("pack_overlap_detected")),
        "pack_under_specified_absent_ok": not bool(validation_summary.get("pack_under_specified_detected")),
    }

    passed = all(checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_8_4_handoff_mode"),
        "upstream_execution_source": handoff.get("upstream_execution_source"),
        "upstream_baseline_route": conclusion.get("current_baseline_route_observed"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.4 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_baseline_route: `{payload['upstream_baseline_route']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.4 handoff integrity artifact.")
    parser.add_argument("--v083-closeout", default=str(DEFAULT_V083_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v084_handoff_integrity(
        v083_closeout_path=str(args.v083_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
