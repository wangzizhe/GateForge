from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_1_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_GAIN_UNLOCK_OUT_DIR,
    DEFAULT_REAUDIT_OUT_DIR,
    DEFAULT_SIGNAL_PACK_OUT_DIR,
    DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR,
    DEFAULT_V0_4_2_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_1_conditioning_reaudit import build_v041_conditioning_reaudit
from .agent_modelica_v0_4_1_gain_unlock_gate import build_v041_gain_unlock_gate
from .agent_modelica_v0_4_1_signal_pack import build_v041_signal_pack
from .agent_modelica_v0_4_1_signal_source_audit import build_v041_signal_source_audit
from .agent_modelica_v0_4_1_v0_4_2_handoff import build_v041_v0_4_2_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v041_closeout(
    *,
    signal_source_audit_path: str = str(DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR / "summary.json"),
    signal_pack_path: str = str(DEFAULT_SIGNAL_PACK_OUT_DIR / "summary.json"),
    conditioning_reaudit_path: str = str(DEFAULT_REAUDIT_OUT_DIR / "summary.json"),
    gain_unlock_path: str = str(DEFAULT_GAIN_UNLOCK_OUT_DIR / "summary.json"),
    v0_4_2_handoff_path: str = str(DEFAULT_V0_4_2_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(signal_source_audit_path).exists():
        build_v041_signal_source_audit(out_dir=str(Path(signal_source_audit_path).parent))
    if not Path(signal_pack_path).exists():
        build_v041_signal_pack(out_dir=str(Path(signal_pack_path).parent))
    if not Path(conditioning_reaudit_path).exists():
        build_v041_conditioning_reaudit(out_dir=str(Path(conditioning_reaudit_path).parent))
    if not Path(gain_unlock_path).exists():
        build_v041_gain_unlock_gate(out_dir=str(Path(gain_unlock_path).parent))
    if not Path(v0_4_2_handoff_path).exists():
        build_v041_v0_4_2_handoff(out_dir=str(Path(v0_4_2_handoff_path).parent))

    source_audit = load_json(signal_source_audit_path)
    signal_pack = load_json(signal_pack_path)
    reaudit = load_json(conditioning_reaudit_path)
    unlock = load_json(gain_unlock_path)
    handoff = load_json(v0_4_2_handoff_path)

    if not bool(source_audit.get("signal_source_ready")):
        version_decision = "v0_4_1_stage2_conditioning_signal_not_ready"
    elif int(signal_pack.get("signal_record_count") or 0) <= 0 or int(signal_pack.get("exact_stage2_key_count") or 0) <= 0:
        version_decision = "v0_4_1_stage2_conditioning_signal_not_ready"
    elif not bool(signal_pack.get("signal_pack_ready")):
        version_decision = "v0_4_1_stage2_conditioning_signal_partial"
    elif not bool(reaudit.get("conditioning_reactivation_ready")):
        version_decision = "v0_4_1_stage2_conditioning_signal_partial"
    else:
        version_decision = "v0_4_1_stage2_conditioning_signal_ready"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_4_1_SIGNAL_REFRESH_READY",
        "conclusion": {
            "version_decision": version_decision,
            "stage2_conditioning_signal_ready": bool(signal_pack.get("signal_pack_ready")) and bool(reaudit.get("conditioning_reactivation_ready")),
            "synthetic_gain_measurement_unlocked": bool(unlock.get("synthetic_gain_measurement_unlocked")),
            "v0_4_2_primary_eval_question": handoff.get("v0_4_2_primary_eval_question"),
            "v0_4_2_required_real_back_check": True,
            "primary_bottleneck": (
                "signal_source_not_ready"
                if not bool(source_audit.get("signal_source_ready"))
                else (
                "signal_pack_too_sparse"
                    if not bool(signal_pack.get("signal_pack_ready"))
                    else (
                        "conditioning_reactivation_still_low"
                        if not bool(reaudit.get("conditioning_reactivation_ready"))
                        else "none"
                    )
                )
            ),
            "v0_4_2_handoff_spec": str(Path(v0_4_2_handoff_path).resolve()),
        },
        "signal_source_audit": source_audit,
        "signal_pack": signal_pack,
        "conditioning_reaudit": reaudit,
        "gain_unlock_gate": unlock,
        "v0_4_2_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.1 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- stage2_conditioning_signal_ready: `{(payload.get('conclusion') or {}).get('stage2_conditioning_signal_ready')}`",
                f"- synthetic_gain_measurement_unlocked: `{(payload.get('conclusion') or {}).get('synthetic_gain_measurement_unlocked')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.1 closeout.")
    parser.add_argument("--signal-source-audit", default=str(DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--signal-pack", default=str(DEFAULT_SIGNAL_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--conditioning-reaudit", default=str(DEFAULT_REAUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--gain-unlock", default=str(DEFAULT_GAIN_UNLOCK_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-2-handoff", default=str(DEFAULT_V0_4_2_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v041_closeout(
        signal_source_audit_path=str(args.signal_source_audit),
        signal_pack_path=str(args.signal_pack),
        conditioning_reaudit_path=str(args.conditioning_reaudit),
        gain_unlock_path=str(args.gain_unlock),
        v0_4_2_handoff_path=str(args.v0_4_2_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
