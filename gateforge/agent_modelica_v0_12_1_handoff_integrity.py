from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V120_CLOSEOUT_PATH,
    EXPECTED_FIRST_REMEDY_IDS,
    EXPECTED_V120_HANDOFF_MODE,
    EXPECTED_V120_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v121_handoff_integrity(
    *,
    v120_closeout_path: str = str(DEFAULT_V120_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    upstream = load_json(v120_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}
    governance_pack = upstream.get("governance_pack") if isinstance(upstream.get("governance_pack"), dict) else {}
    remedy_registry = governance_pack.get("remedy_registry") if isinstance(governance_pack.get("remedy_registry"), dict) else {}
    remedy_rows = list(remedy_registry.get("remedy_rows") or [])
    admitted_remedy_ids = sorted(
        str(row.get("remedy_id") or "")
        for row in remedy_rows
        if isinstance(row, dict) and str(row.get("admission_status") or "") == "admitted"
    )

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_V120_VERSION_DECISION,
        "runtime_ready_ok": bool(conclusion.get("governance_ready_for_runtime_execution")),
        "named_pack_ready_ok": bool(conclusion.get("named_first_remedy_pack_ready")),
        "handoff_mode_ok": conclusion.get("v0_12_1_handoff_mode") == EXPECTED_V120_HANDOFF_MODE,
        "admitted_remedy_ids_ok": admitted_remedy_ids == sorted(EXPECTED_FIRST_REMEDY_IDS),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_governance_ready_for_runtime_execution": bool(conclusion.get("governance_ready_for_runtime_execution")),
        "upstream_named_first_remedy_pack_ready": bool(conclusion.get("named_first_remedy_pack_ready")),
        "admitted_remedy_ids": admitted_remedy_ids,
        "checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- admitted_remedy_ids: `{admitted_remedy_ids}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.1 handoff integrity artifact.")
    parser.add_argument("--v120-closeout", default=str(DEFAULT_V120_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v121_handoff_integrity(
        v120_closeout_path=str(args.v120_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
