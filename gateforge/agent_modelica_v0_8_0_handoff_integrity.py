from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_0_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V077_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v080_handoff_integrity(
    *,
    v077_closeout_path: str = str(DEFAULT_V077_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v077 = load_json(v077_closeout_path)
    conclusion = v077.get("conclusion") or {}
    version_decision = str(conclusion.get("version_decision") or "")
    phase_status = str(conclusion.get("phase_status") or "")
    primary_question = (
        ((conclusion.get("v0_8_handoff_spec") or {}).get("v0_8_primary_phase_question"))
        or ""
    )
    no_continue = bool(conclusion.get("do_not_continue_v0_7_same_logic_refinement_by_default"))

    checks = {
        "version_decision_ok": version_decision == "v0_7_phase_complete_prepare_v0_8",
        "phase_status_ok": phase_status == "complete",
        "primary_question_ok": primary_question == "workflow_proximal_readiness_evaluation",
        "do_not_continue_ok": no_continue,
    }
    passed = all(checks.values())

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": version_decision,
        "upstream_phase_status": phase_status,
        "upstream_v0_8_primary_phase_question": primary_question,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.0 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{version_decision}`",
                f"- upstream_phase_status: `{phase_status}`",
                f"- upstream_v0_8_primary_phase_question: `{primary_question}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.0 handoff integrity summary.")
    parser.add_argument("--v077-closeout", default=str(DEFAULT_V077_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v080_handoff_integrity(
        v077_closeout_path=str(args.v077_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
