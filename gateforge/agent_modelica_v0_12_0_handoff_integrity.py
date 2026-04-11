from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_12_0_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V111_CLOSEOUT_PATH,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V117_CLOSEOUT_PATH,
    EXPECTED_V111_HANDOFF_MODE,
    EXPECTED_V111_VERSION_DECISION,
    EXPECTED_V112_HANDOFF_MODE,
    EXPECTED_V112_SUBSTRATE_SIZE,
    EXPECTED_V112_VERSION_DECISION,
    EXPECTED_V115_ADJUDICATION_LABEL,
    EXPECTED_V115_DOMINANT_GAP_FAMILY,
    EXPECTED_V115_VERSION_DECISION,
    EXPECTED_V117_CAVEAT,
    EXPECTED_V117_NEXT_PRIMARY_QUESTION,
    EXPECTED_V117_PHASE_STOP_CONDITION_STATUS,
    EXPECTED_V117_VERSION_DECISION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v120_handoff_integrity(
    *,
    v111_closeout_path: str = str(DEFAULT_V111_CLOSEOUT_PATH),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v117_closeout_path: str = str(DEFAULT_V117_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    v111 = load_json(v111_closeout_path).get("conclusion", {})
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    v112_admission = (v112.get("product_gap_substrate_admission") or {})
    v115 = load_json(v115_closeout_path).get("conclusion", {})
    v117 = load_json(v117_closeout_path).get("conclusion", {})

    checks = {
        "v117_version_decision_ok": v117.get("version_decision") == EXPECTED_V117_VERSION_DECISION,
        "v117_phase_stop_condition_status_ok": v117.get("phase_stop_condition_status")
        == EXPECTED_V117_PHASE_STOP_CONDITION_STATUS,
        "v117_explicit_caveat_ok": bool(v117.get("explicit_caveat_present"))
        and v117.get("explicit_caveat_label") == EXPECTED_V117_CAVEAT,
        "v117_next_primary_question_ok": v117.get("next_primary_phase_question")
        == EXPECTED_V117_NEXT_PRIMARY_QUESTION,
        "v117_do_not_continue_ok": bool(v117.get("do_not_continue_v0_11_same_product_gap_refinement_by_default")),
        "v111_version_decision_ok": v111.get("version_decision") == EXPECTED_V111_VERSION_DECISION,
        "v111_handoff_mode_ok": v111.get("v0_11_2_handoff_mode") == EXPECTED_V111_HANDOFF_MODE,
        "v112_version_decision_ok": v112_conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION,
        "v112_handoff_mode_ok": v112_conclusion.get("v0_11_3_handoff_mode") == EXPECTED_V112_HANDOFF_MODE,
        "v112_substrate_size_ok": v112_admission.get("product_gap_substrate_size") == EXPECTED_V112_SUBSTRATE_SIZE,
        "v115_version_decision_ok": v115.get("version_decision") == EXPECTED_V115_VERSION_DECISION,
        "v115_formal_adjudication_label_ok": v115.get("formal_adjudication_label") == EXPECTED_V115_ADJUDICATION_LABEL,
        "v115_execution_posture_ok": bool(v115.get("execution_posture_semantics_preserved")),
        "v115_dominant_gap_family_ok": v115.get("dominant_gap_family_readout") == EXPECTED_V115_DOMINANT_GAP_FAMILY,
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": v117.get("version_decision"),
        "upstream_next_primary_phase_question": v117.get("next_primary_phase_question"),
        "upstream_caveat_label": v117.get("explicit_caveat_label"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.0 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_next_primary_phase_question: `{payload['upstream_next_primary_phase_question']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.0 handoff integrity artifact.")
    parser.add_argument("--v111-closeout", default=str(DEFAULT_V111_CLOSEOUT_PATH))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v117-closeout", default=str(DEFAULT_V117_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v120_handoff_integrity(
        v111_closeout_path=str(args.v111_closeout),
        v112_closeout_path=str(args.v112_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v117_closeout_path=str(args.v117_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
