from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_3_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V082_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v083_handoff_integrity(
    *,
    v082_closeout_path: str = str(DEFAULT_V082_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v082_closeout_path)
    conclusion = closeout.get("conclusion") or {}
    freeze = closeout.get("threshold_freeze") or {}
    integrity = closeout.get("handoff_integrity") or {}

    checks = {
        "version_decision_ok": conclusion.get("version_decision")
        == "v0_8_2_workflow_readiness_thresholds_frozen",
        "handoff_mode_ok": conclusion.get("v0_8_3_handoff_mode")
        == "validate_frozen_workflow_readiness_threshold_pack",
        "anti_tautology_ok": bool(conclusion.get("anti_tautology_pass")),
        "integer_safe_ok": bool(conclusion.get("integer_safe_pass")),
        "class_distinction_ok": bool(conclusion.get("class_distinction_pass")),
        "upstream_execution_source_ok": integrity.get("execution_source")
        == "gateforge_run_contract_live_path",
        "threshold_pack_status_ok": freeze.get("threshold_pack_status") == "FROZEN",
    }
    passed = all(checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_8_3_handoff_mode"),
        "upstream_execution_source": integrity.get("execution_source"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.3 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.3 handoff integrity summary.")
    parser.add_argument("--v082-closeout", default=str(DEFAULT_V082_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v083_handoff_integrity(
        v082_closeout_path=str(args.v082_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
