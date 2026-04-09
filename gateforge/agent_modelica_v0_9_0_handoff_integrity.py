from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V086_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED_CAVEAT = "workflow_readiness_remains_partial_rather_than_supported_on_frozen_workflow_proximal_substrate"
EXPECTED_PRIMARY_QUESTION = "authenticity_constrained_barrier_aware_workflow_expansion"
EXPECTED_VERSION_DECISION = "v0_8_phase_nearly_complete_with_explicit_caveat"


def build_v090_handoff_integrity(
    *,
    v086_closeout_path: str = str(DEFAULT_V086_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    upstream = load_json(v086_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}

    checks = {
        "version_decision_ok": conclusion.get("version_decision") == EXPECTED_VERSION_DECISION,
        "primary_question_ok": conclusion.get("v0_9_primary_phase_question") == EXPECTED_PRIMARY_QUESTION,
        "do_not_continue_ok": bool(conclusion.get("do_not_continue_v0_8_same_logic_refinement_by_default")),
        "explicit_caveat_ok": conclusion.get("explicit_caveat_label") == EXPECTED_CAVEAT,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_v0_9_primary_phase_question": conclusion.get("v0_9_primary_phase_question"),
        "upstream_explicit_caveat_label": conclusion.get("explicit_caveat_label"),
        "upstream_v0_9_handoff_mode": conclusion.get("v0_9_handoff_mode"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.0 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_v0_9_primary_phase_question: `{payload['upstream_v0_9_primary_phase_question']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.0 handoff integrity artifact.")
    parser.add_argument("--v086-closeout", default=str(DEFAULT_V086_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v090_handoff_integrity(v086_closeout_path=str(args.v086_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
