from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_3_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_SIZE,
    EXPECTED_V112_HANDOFF_MODE,
    EXPECTED_V112_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v113_handoff_integrity(
    *,
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v112_closeout_path)
    conclusion = upstream.get("conclusion", {})
    admission = upstream.get("product_gap_substrate_admission", {})

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION,
        "substrate_ready_ok": conclusion.get("first_product_gap_substrate_status") == "ready",
        "handoff_mode_ok": conclusion.get("v0_11_3_handoff_mode") == EXPECTED_V112_HANDOFF_MODE,
        "admission_status_ok": admission.get("product_gap_substrate_admission_status") == "ready",
        "substrate_size_ok": int(admission.get("product_gap_substrate_size") or 0) == DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_SIZE,
        "same_substrate_continuity_ok": bool(admission.get("same_substrate_continuity_pass")),
        "instrumentation_completeness_ok": bool(admission.get("instrumentation_completeness_pass")),
        "traceability_ok": bool(admission.get("traceability_pass")),
        "dynamic_prompt_field_state_ok": admission.get("dynamic_prompt_field_audit_state") == "explicit_and_still_open",
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_11_3_handoff_mode"),
        "upstream_substrate_ready": conclusion.get("first_product_gap_substrate_status"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.3 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.3 handoff integrity artifact.")
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v113_handoff_integrity(
        v112_closeout_path=str(args.v112_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
