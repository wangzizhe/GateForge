from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V111_CLOSEOUT_PATH,
    EXPECTED_V111_HANDOFF_MODE,
    EXPECTED_V111_PATCH_PACK_STATUS,
    EXPECTED_V111_VALIDATION_STATUS,
    EXPECTED_V111_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v112_handoff_integrity(
    *,
    v111_closeout_path: str = str(DEFAULT_V111_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v111_closeout_path)
    conclusion = upstream.get("conclusion", {})
    patch_pack = upstream.get("patch_pack_execution", {})
    validation = upstream.get("bounded_validation_pack", {})

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_V111_VERSION_DECISION,
        "patch_pack_ready_ok": conclusion.get("first_product_gap_patch_pack_status") == EXPECTED_V111_PATCH_PACK_STATUS,
        "handoff_mode_ok": conclusion.get("v0_11_2_handoff_mode") == EXPECTED_V111_HANDOFF_MODE,
        "patch_pack_execution_status_ok": patch_pack.get("patch_pack_execution_status") == EXPECTED_V111_PATCH_PACK_STATUS,
        "validation_pack_status_ok": validation.get("validation_pack_status") == EXPECTED_V111_VALIDATION_STATUS,
        "required_sidecar_fields_emitted_ok": bool(validation.get("required_sidecar_fields_emitted")),
        "traceability_pass_ok": bool(validation.get("one_to_one_traceability_pass")),
        "profile_level_claim_block_ok": not bool(validation.get("profile_level_claim_made")),
        "bounded_validation_only_ok": bool(validation.get("bounded_validation_only")),
        "non_regression_pass_ok": bool(validation.get("non_regression_pass")),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_11_2_handoff_mode"),
        "upstream_patch_pack_ready": conclusion.get("first_product_gap_patch_pack_status"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.2 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.2 handoff integrity artifact.")
    parser.add_argument("--v111-closeout", default=str(DEFAULT_V111_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v112_handoff_integrity(
        v111_closeout_path=str(args.v111_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
