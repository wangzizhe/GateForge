from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_34_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_FAMILY_LEDGER_OUT_DIR,
    DEFAULT_REAL_DIST_OUT_DIR,
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V0_4_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_34_family_ledger import build_v0334_family_ledger
from .agent_modelica_v0_3_34_real_distribution_synthesis import build_v0334_real_distribution_synthesis
from .agent_modelica_v0_3_34_stop_condition_audit import build_v0334_stop_condition_audit
from .agent_modelica_v0_3_34_v0_4_handoff import build_v0334_v0_4_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0334_closeout(
    *,
    family_ledger_path: str = str(DEFAULT_FAMILY_LEDGER_OUT_DIR / "summary.json"),
    stop_audit_path: str = str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"),
    real_distribution_synthesis_path: str = str(DEFAULT_REAL_DIST_OUT_DIR / "summary.json"),
    v0_4_handoff_path: str = str(DEFAULT_V0_4_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(family_ledger_path).exists():
        build_v0334_family_ledger(out_dir=str(Path(family_ledger_path).parent))
    if not Path(stop_audit_path).exists():
        build_v0334_stop_condition_audit(out_dir=str(Path(stop_audit_path).parent))
    if not Path(real_distribution_synthesis_path).exists():
        build_v0334_real_distribution_synthesis(out_dir=str(Path(real_distribution_synthesis_path).parent))
    if not Path(v0_4_handoff_path).exists():
        build_v0334_v0_4_handoff(out_dir=str(Path(v0_4_handoff_path).parent))

    ledger = load_json(family_ledger_path)
    stop_audit = load_json(stop_audit_path)
    real_dist = load_json(real_distribution_synthesis_path)
    handoff = load_json(v0_4_handoff_path)

    if not bool(stop_audit.get("overall_stop_condition_met")):
        version_decision = "v0_3_phase_not_yet_complete"
        phase_status = "stage2_curriculum_construction_incomplete"
        recommended_next_version = "v0.3.35"
    elif norm(real_dist.get("material_overlap_supported")) in {"true", "insufficient_evidence"}:
        version_decision = "v0_3_phase_complete_prepare_v0_4"
        phase_status = "stage2_curriculum_construction_complete"
        recommended_next_version = "v0.4.0"
    else:
        version_decision = "v0_3_phase_nearly_complete_one_more_gap"
        phase_status = "stage2_curriculum_construction_nearly_complete"
        recommended_next_version = "v0.3.35"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_3_PHASE_SYNTHESIS_READY",
        "conclusion": {
            "version_decision": version_decision,
            "phase_status": phase_status,
            "recommended_next_version": recommended_next_version,
            "v0_4_handoff_spec": str(Path(v0_4_handoff_path).resolve()),
            "do_not_continue_family_construction_by_default": version_decision == "v0_3_phase_complete_prepare_v0_4",
            "material_overlap_supported": norm(real_dist.get("material_overlap_supported")),
            "real_distribution_authority_status": (
                "deferred_to_v0_4_back_check"
                if norm(real_dist.get("material_overlap_supported")) == "insufficient_evidence"
                else "resolved_in_v0_3"
            ),
            "summary": (
                "v0.3.x family construction is complete; v0.4.x should start from learning effectiveness with a required real-distribution back-check."
                if version_decision == "v0_3_phase_complete_prepare_v0_4"
                else (
                    "v0.3.x is close to phase completion, but one remaining gap still blocks the transition."
                    if version_decision == "v0_3_phase_nearly_complete_one_more_gap"
                    else "v0.3.x still requires more curriculum-construction work before the phase can close."
                )
            ),
        },
        "family_ledger": ledger,
        "stop_condition_audit": stop_audit,
        "real_distribution_synthesis": real_dist,
        "v0_4_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.34 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- phase_status: `{(payload.get('conclusion') or {}).get('phase_status')}`",
                f"- recommended_next_version: `{(payload.get('conclusion') or {}).get('recommended_next_version')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.34 phase closeout.")
    parser.add_argument("--family-ledger", default=str(DEFAULT_FAMILY_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--stop-audit", default=str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--real-distribution-synthesis", default=str(DEFAULT_REAL_DIST_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-handoff", default=str(DEFAULT_V0_4_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0334_closeout(
        family_ledger_path=str(args.family_ledger),
        stop_audit_path=str(args.stop_audit),
        real_distribution_synthesis_path=str(args.real_distribution_synthesis),
        v0_4_handoff_path=str(args.v0_4_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
