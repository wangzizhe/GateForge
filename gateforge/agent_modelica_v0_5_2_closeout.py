from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_2_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_ENTRY_TRIAGE_OUT_DIR,
    DEFAULT_SIGNAL_AUDIT_OUT_DIR,
    DEFAULT_V051_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_2_expansion_adjudication import build_v052_expansion_adjudication
from .agent_modelica_v0_5_2_entry_spec import build_v052_entry_spec
from .agent_modelica_v0_5_2_entry_triage import build_v052_entry_triage
from .agent_modelica_v0_5_2_signal_audit import build_v052_signal_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v052_closeout(
    *,
    v0_5_1_closeout_path: str = str(DEFAULT_V051_CLOSEOUT_PATH),
    signal_audit_path: str = str(DEFAULT_SIGNAL_AUDIT_OUT_DIR / "summary.json"),
    entry_triage_path: str = str(DEFAULT_ENTRY_TRIAGE_OUT_DIR / "summary.json"),
    entry_spec_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"),
    adjudication_path: str = str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    rebuild_signal = True
    if Path(signal_audit_path).exists():
        existing_signal = load_json(signal_audit_path)
        rebuild_signal = str(existing_signal.get("v0_5_1_closeout_path") or "") != str(Path(v0_5_1_closeout_path).resolve())
    if rebuild_signal:
        build_v052_signal_audit(v0_5_1_closeout_path=v0_5_1_closeout_path, out_dir=str(Path(signal_audit_path).parent))
    rebuild_triage = True
    if Path(entry_triage_path).exists():
        existing_triage = load_json(entry_triage_path)
        rebuild_triage = str(existing_triage.get("signal_audit_path") or "") != str(Path(signal_audit_path).resolve())
    if rebuild_triage:
        build_v052_entry_triage(
            v0_5_1_closeout_path=v0_5_1_closeout_path,
            signal_audit_path=str(signal_audit_path),
            out_dir=str(Path(entry_triage_path).parent),
        )
    rebuild_spec = True
    if Path(entry_spec_path).exists():
        existing_spec = load_json(entry_spec_path)
        rebuild_spec = str(existing_spec.get("entry_triage_path") or "") != str(Path(entry_triage_path).resolve())
    if rebuild_spec:
        build_v052_entry_spec(entry_triage_path=str(entry_triage_path), out_dir=str(Path(entry_spec_path).parent))
    rebuild_adjudication = True
    if Path(adjudication_path).exists():
        existing_adjudication = load_json(adjudication_path)
        rebuild_adjudication = str(existing_adjudication.get("signal_audit_path") or "") != str(Path(signal_audit_path).resolve())
    if rebuild_adjudication:
        build_v052_expansion_adjudication(
            signal_audit_path=str(signal_audit_path),
            entry_triage_path=str(entry_triage_path),
            entry_spec_path=str(entry_spec_path),
            out_dir=str(Path(adjudication_path).parent),
        )

    signal = load_json(signal_audit_path)
    triage = load_json(entry_triage_path)
    spec = load_json(entry_spec_path)
    adjudication = load_json(adjudication_path)

    if bool(adjudication.get("entry_ready")):
        version_decision = "v0_5_2_targeted_expansion_entry_ready"
        targeted_expansion_status = "entry_ready"
        handoff_mode = "run_entry_first_fix_on_targeted_expansion"
    elif bool(signal.get("recurring_signal_supported")):
        version_decision = "v0_5_2_targeted_expansion_partial"
        targeted_expansion_status = "partial"
        handoff_mode = "repair_targeted_expansion_entry_gaps_first"
    else:
        version_decision = "v0_5_2_targeted_expansion_not_supported"
        targeted_expansion_status = "not_supported"
        handoff_mode = "return_to_broader_real_validation"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_2_TARGETED_EXPANSION_DECISION_READY",
        "conclusion": {
            "version_decision": version_decision,
            "targeted_expansion_status": targeted_expansion_status,
            "selected_entry_pattern_id": triage.get("selected_entry_pattern_id"),
            "entry_ready": adjudication.get("entry_ready"),
            "v0_5_3_handoff_mode": handoff_mode,
            "v0_5_3_primary_eval_question": "Given the frozen targeted-expansion entry, can the next version turn this bounded uncovered slice into a stable first-fix lane without scope creep?",
        },
        "signal_audit": signal,
        "entry_triage": triage,
        "entry_spec": spec,
        "expansion_adjudication": adjudication,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- targeted_expansion_status: `{targeted_expansion_status}`",
                f"- v0_5_3_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.2 targeted-expansion decision closeout.")
    parser.add_argument("--v0-5-1-closeout", default=str(DEFAULT_V051_CLOSEOUT_PATH))
    parser.add_argument("--signal-audit", default=str(DEFAULT_SIGNAL_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-triage", default=str(DEFAULT_ENTRY_TRIAGE_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-spec", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--adjudication", default=str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v052_closeout(
        v0_5_1_closeout_path=str(args.v0_5_1_closeout),
        signal_audit_path=str(args.signal_audit),
        entry_triage_path=str(args.entry_triage),
        entry_spec_path=str(args.entry_spec),
        adjudication_path=str(args.adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
