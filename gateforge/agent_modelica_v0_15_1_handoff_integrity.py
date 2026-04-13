from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_15_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V150_CLOSEOUT_PATH,
    EXPECTED_V150_BLOCKER,
    EXPECTED_V150_GOVERNANCE_STATUS,
    EXPECTED_V150_HANDOFF_MODE,
    EXPECTED_V150_VERSION_DECISION,
    EXPECTED_V150_VIABILITY_STATUS,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v151_handoff_integrity(
    *,
    v150_closeout_path: str = str(DEFAULT_V150_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    upstream = load_json(v150_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}
    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_V150_VERSION_DECISION,
        "governance_status_ok": conclusion.get("even_broader_change_governance_status") == EXPECTED_V150_GOVERNANCE_STATUS,
        "viability_status_ok": conclusion.get("execution_arc_viability_status") == EXPECTED_V150_VIABILITY_STATUS,
        "named_reason_ok": conclusion.get("named_reason_if_not_justified") == EXPECTED_V150_BLOCKER,
        "handoff_mode_ok": conclusion.get("v0_15_1_handoff_mode") == EXPECTED_V150_HANDOFF_MODE,
    }
    handoff_integrity_status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": handoff_integrity_status,
        "handoff_integrity_status": handoff_integrity_status,
        "carried_v150_version_decision": conclusion.get("version_decision", ""),
        "carried_even_broader_change_governance_status": conclusion.get("even_broader_change_governance_status", ""),
        "carried_execution_arc_viability_status": conclusion.get("execution_arc_viability_status", ""),
        "carried_named_reason_if_not_justified": conclusion.get("named_reason_if_not_justified", ""),
        "carried_named_first_even_broader_change_pack_ready": bool(conclusion.get("named_first_even_broader_change_pack_ready")),
        "checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.15.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{handoff_integrity_status}`",
                f"- carried_v150_version_decision: `{payload['carried_v150_version_decision']}`",
                f"- carried_execution_arc_viability_status: `{payload['carried_execution_arc_viability_status']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.1 handoff integrity artifact.")
    parser.add_argument("--v150-closeout", default=str(DEFAULT_V150_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v151_handoff_integrity(
        v150_closeout_path=str(args.v150_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
