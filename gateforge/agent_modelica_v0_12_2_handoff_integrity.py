from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V121_CLOSEOUT_PATH,
    EXPECTED_V121_HANDOFF_MODE,
    EXPECTED_V121_PACK_LEVEL_EFFECT,
    EXPECTED_V121_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v122_handoff_integrity(
    *,
    v121_closeout_path: str = str(DEFAULT_V121_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    upstream = load_json(v121_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}

    version_decision = conclusion.get("version_decision")
    pack_level_effect = conclusion.get("pack_level_effect")
    same_execution_source = conclusion.get("same_execution_source")
    same_case_requirement_met = conclusion.get("same_case_requirement_met")
    handoff_mode = conclusion.get("v0_12_2_handoff_mode")

    checks = {
        "version_decision_ok": version_decision == EXPECTED_V121_VERSION_DECISION,
        "pack_level_effect_ok": pack_level_effect == EXPECTED_V121_PACK_LEVEL_EFFECT,
        "same_execution_source_ok": bool(same_execution_source),
        "same_case_requirement_met_ok": bool(same_case_requirement_met),
        "handoff_mode_ok": handoff_mode == EXPECTED_V121_HANDOFF_MODE,
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "upstream_version_decision": version_decision,
        "upstream_pack_level_effect": pack_level_effect,
        "upstream_same_execution_source": same_execution_source,
        "upstream_same_case_requirement_met": same_case_requirement_met,
        "upstream_handoff_mode": handoff_mode,
        "checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.2 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{version_decision}`",
                f"- upstream_pack_level_effect: `{pack_level_effect}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.2 handoff integrity artifact.")
    parser.add_argument("--v121-closeout", default=str(DEFAULT_V121_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v122_handoff_integrity(
        v121_closeout_path=str(args.v121_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
