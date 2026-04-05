from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_6_common import (
    DEFAULT_DEFERRED_AUDIT_OUT_DIR,
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V0_5_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_6_deferred_question_audit import build_v046_deferred_question_audit
from .agent_modelica_v0_4_6_stop_condition_audit import build_v046_stop_condition_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_5_handoff"


def build_v046_v0_5_handoff(
    *,
    stop_audit_path: str = str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"),
    deferred_question_audit_path: str = str(DEFAULT_DEFERRED_AUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_V0_5_HANDOFF_OUT_DIR),
) -> dict:
    if not Path(stop_audit_path).exists():
        build_v046_stop_condition_audit(out_dir=str(Path(stop_audit_path).parent))
    if not Path(deferred_question_audit_path).exists():
        build_v046_deferred_question_audit(out_dir=str(Path(deferred_question_audit_path).parent))
    stop_audit = load_json(stop_audit_path)
    deferred = load_json(deferred_question_audit_path)

    if str(stop_audit.get("phase_stop_condition_status") or "") == "met" and str(deferred.get("deferred_question_blocking_status") or "") == "non_blocking_only":
        handoff_mode = "prepare_v0_5"
    else:
        handoff_mode = "reassess_v0_4_scope"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "stop_audit_path": str(Path(stop_audit_path).resolve()),
        "deferred_question_audit_path": str(Path(deferred_question_audit_path).resolve()),
        "v0_5_handoff_mode": handoff_mode,
        "v0_5_primary_eval_question": "Which phase-level question should follow a completed learning-effectiveness phase: broader real-distribution validation, capability-boundary mapping, open-world repair readiness, or conditioning-mechanism comparison?",
        "v0_5_phase_level_question_class": "phase_level_question_selection_required",
        "v0_5_default_mode": "explicit_phase_question_selection",
        "v0_5_non_goals": [
            "do_not_repeat_v0_4_learning_effectiveness_mainline",
            "do_not_reopen_v0_3_family_construction",
            "do_not_default_to_planner_injection_only_without_phase_level_justification",
        ],
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.6 -> v0.5 Handoff",
                "",
                f"- v0_5_handoff_mode: `{payload.get('v0_5_handoff_mode')}`",
                f"- v0_5_default_mode: `{payload.get('v0_5_default_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.6 -> v0.5 handoff.")
    parser.add_argument("--stop-audit", default=str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--deferred-question-audit", default=str(DEFAULT_DEFERRED_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_5_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v046_v0_5_handoff(
        stop_audit_path=str(args.stop_audit),
        deferred_question_audit_path=str(args.deferred_question_audit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_5_handoff_mode": payload.get("v0_5_handoff_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
