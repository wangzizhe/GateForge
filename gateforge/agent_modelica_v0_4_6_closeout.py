from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_6_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DEFERRED_AUDIT_OUT_DIR,
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V0_5_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_6_deferred_question_audit import build_v046_deferred_question_audit
from .agent_modelica_v0_4_6_phase_ledger import build_v046_phase_ledger
from .agent_modelica_v0_4_6_stop_condition_audit import build_v046_stop_condition_audit
from .agent_modelica_v0_4_6_v0_5_handoff import build_v046_v0_5_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v046_closeout(
    *,
    phase_ledger_path: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"),
    stop_audit_path: str = str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"),
    deferred_question_audit_path: str = str(DEFAULT_DEFERRED_AUDIT_OUT_DIR / "summary.json"),
    v0_5_handoff_path: str = str(DEFAULT_V0_5_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(phase_ledger_path).exists():
        build_v046_phase_ledger(out_dir=str(Path(phase_ledger_path).parent))
    if not Path(stop_audit_path).exists():
        build_v046_stop_condition_audit(out_dir=str(Path(stop_audit_path).parent))
    if not Path(deferred_question_audit_path).exists():
        build_v046_deferred_question_audit(out_dir=str(Path(deferred_question_audit_path).parent))
    if not Path(v0_5_handoff_path).exists():
        build_v046_v0_5_handoff(out_dir=str(Path(v0_5_handoff_path).parent))

    ledger = load_json(phase_ledger_path)
    stop_audit = load_json(stop_audit_path)
    deferred = load_json(deferred_question_audit_path)
    handoff = load_json(v0_5_handoff_path)

    phase_primary_question_answered = str(stop_audit.get("phase_stop_condition_status") or "") == "met"
    deferred_questions_non_blocking = str(deferred.get("deferred_question_blocking_status") or "") == "non_blocking_only"

    if phase_primary_question_answered and deferred_questions_non_blocking:
        version_decision = "v0_4_phase_complete_prepare_v0_5"
        phase_status = "learning_effectiveness_phase_complete"
    elif phase_primary_question_answered:
        version_decision = "v0_4_phase_nearly_complete_with_explicit_caveat"
        phase_status = "learning_effectiveness_phase_nearly_complete"
    else:
        version_decision = "v0_4_phase_not_ready_for_closeout"
        phase_status = "learning_effectiveness_phase_incomplete"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_4_PHASE_SYNTHESIS_READY",
        "conclusion": {
            "version_decision": version_decision,
            "phase_status": phase_status,
            "phase_primary_question_answered": phase_primary_question_answered,
            "deferred_questions_non_blocking": deferred_questions_non_blocking,
            "v0_5_handoff_mode": handoff.get("v0_5_handoff_mode"),
            "v0_5_handoff_spec": str(Path(v0_5_handoff_path).resolve()),
            "do_not_continue_v0_4_experiments_by_default": version_decision == "v0_4_phase_complete_prepare_v0_5",
        },
        "phase_ledger": ledger,
        "stop_condition_audit": stop_audit,
        "deferred_question_audit": deferred,
        "v0_5_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.6 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- phase_status: `{(payload.get('conclusion') or {}).get('phase_status')}`",
                f"- v0_5_handoff_mode: `{(payload.get('conclusion') or {}).get('v0_5_handoff_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.6 phase closeout.")
    parser.add_argument("--phase-ledger", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-audit", default=str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--deferred-question-audit", default=str(DEFAULT_DEFERRED_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-5-handoff", default=str(DEFAULT_V0_5_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v046_closeout(
        phase_ledger_path=str(args.phase_ledger),
        stop_audit_path=str(args.stop_audit),
        deferred_question_audit_path=str(args.deferred_question_audit),
        v0_5_handoff_path=str(args.v0_5_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
