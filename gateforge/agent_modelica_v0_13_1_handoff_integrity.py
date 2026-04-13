from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_13_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V130_CLOSEOUT_PATH,
    EXPECTED_ADMITTED_INTERVENTION_IDS,
    EXPECTED_V130_HANDOFF_MODE,
    EXPECTED_V130_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v131_handoff_integrity(
    *,
    v130_closeout_path: str = str(DEFAULT_V130_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    v130 = load_json(v130_closeout_path)
    conclusion = v130.get("conclusion") if isinstance(v130.get("conclusion"), dict) else {}
    governance_pack = v130.get("governance_pack") if isinstance(v130.get("governance_pack"), dict) else {}

    upstream_version_decision = str(conclusion.get("version_decision") or "")
    upstream_governance_ready = bool(conclusion.get("governance_ready_for_runtime_execution"))
    upstream_minimum_pass = bool(conclusion.get("minimum_completion_signal_pass"))
    upstream_named_pack_ready = bool(conclusion.get("named_first_intervention_pack_ready"))
    upstream_handoff_mode = str(conclusion.get("v0_13_1_handoff_mode") or "")

    admission = (
        governance_pack.get("capability_intervention_admission")
        if isinstance(governance_pack.get("capability_intervention_admission"), dict)
        else {}
    )
    admitted_rows = list((admission.get("admitted_intervention_table") or []))
    admitted_ids = frozenset(str(row.get("intervention_id") or "") for row in admitted_rows if isinstance(row, dict))

    version_decision_ok = upstream_version_decision == EXPECTED_V130_VERSION_DECISION
    handoff_mode_ok = upstream_handoff_mode == EXPECTED_V130_HANDOFF_MODE
    governance_ready_ok = upstream_governance_ready
    minimum_pass_ok = upstream_minimum_pass
    named_pack_ready_ok = upstream_named_pack_ready
    admitted_ids_ok = admitted_ids == EXPECTED_ADMITTED_INTERVENTION_IDS

    all_pass = all(
        [
            version_decision_ok,
            handoff_mode_ok,
            governance_ready_ok,
            minimum_pass_ok,
            named_pack_ready_ok,
            admitted_ids_ok,
        ]
    )
    handoff_integrity_status = "PASS" if all_pass else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "handoff_integrity_status": handoff_integrity_status,
        "upstream_version_decision": upstream_version_decision,
        "upstream_governance_ready_for_runtime_execution": upstream_governance_ready,
        "upstream_minimum_completion_signal_pass": upstream_minimum_pass,
        "upstream_named_first_intervention_pack_ready": upstream_named_pack_ready,
        "upstream_v0_13_1_handoff_mode": upstream_handoff_mode,
        "admitted_intervention_ids": sorted(admitted_ids),
        "checks": {
            "version_decision_ok": version_decision_ok,
            "handoff_mode_ok": handoff_mode_ok,
            "governance_ready_ok": governance_ready_ok,
            "minimum_completion_signal_pass_ok": minimum_pass_ok,
            "named_first_intervention_pack_ready_ok": named_pack_ready_ok,
            "admitted_intervention_ids_ok": admitted_ids_ok,
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.1 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{handoff_integrity_status}`",
                f"- upstream_version_decision: `{upstream_version_decision}`",
                f"- upstream_v0_13_1_handoff_mode: `{upstream_handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.1 handoff integrity artifact.")
    parser.add_argument("--v130-closeout", default=str(DEFAULT_V130_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v131_handoff_integrity(
        v130_closeout_path=str(args.v130_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
