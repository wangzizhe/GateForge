from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_0_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V097_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED_VERSION_DECISION = "v0_9_phase_nearly_complete_with_explicit_caveat"
EXPECTED_CAVEAT = "expanded_workflow_readiness_remains_partial_rather_than_supported_even_after_authenticity_constrained_barrier_aware_expansion"
EXPECTED_PRIMARY_QUESTION = "real_origin_workflow_readiness_evaluation"
EXPECTED_HANDOFF_MODE = "start_next_phase_with_explicit_v0_9_caveat"


def build_v1000_handoff_integrity(
    *,
    v097_closeout_path: str = str(DEFAULT_V097_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v097_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_VERSION_DECISION,
        "phase_status_ok": conclusion.get("phase_status") == "nearly_complete",
        "phase_stop_condition_ok": conclusion.get("phase_stop_condition_status") == "met",
        "explicit_caveat_ok": conclusion.get("explicit_caveat_label") == EXPECTED_CAVEAT,
        "primary_question_ok": conclusion.get("next_primary_phase_question") == EXPECTED_PRIMARY_QUESTION,
        "do_not_continue_ok": bool(conclusion.get("do_not_continue_v0_9_same_authentic_expansion_by_default")),
        "handoff_mode_ok": conclusion.get("next_phase_handoff_mode") == EXPECTED_HANDOFF_MODE,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_next_primary_phase_question": conclusion.get("next_primary_phase_question"),
        "upstream_explicit_caveat_label": conclusion.get("explicit_caveat_label"),
        "upstream_next_phase_handoff_mode": conclusion.get("next_phase_handoff_mode"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.0 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_next_primary_phase_question: `{payload['upstream_next_primary_phase_question']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.0 handoff integrity artifact.")
    parser.add_argument("--v097-closeout", default=str(DEFAULT_V097_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v1000_handoff_integrity(v097_closeout_path=str(args.v097_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
