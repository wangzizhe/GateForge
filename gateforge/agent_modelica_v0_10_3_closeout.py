from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_3_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR,
    DEFAULT_V102_CLOSEOUT_PATH,
    DEFAULT_V102_POOL_DELTA_PATH,
    READY_MAX_SINGLE_SOURCE_SHARE_PCT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_3_handoff_integrity import build_v103_handoff_integrity
from .agent_modelica_v0_10_3_real_origin_substrate_admission import build_v103_real_origin_substrate_admission
from .agent_modelica_v0_10_3_real_origin_substrate_builder import build_v103_real_origin_substrate_builder


def build_v103_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    real_origin_substrate_builder_path: str = str(DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"),
    real_origin_substrate_admission_path: str = str(DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"),
    v102_closeout_path: str = str(DEFAULT_V102_CLOSEOUT_PATH),
    v102_pool_delta_path: str = str(DEFAULT_V102_POOL_DELTA_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    handoff_path_obj = Path(handoff_integrity_path)
    builder_path_obj = Path(real_origin_substrate_builder_path)
    admission_path_obj = Path(real_origin_substrate_admission_path)
    default_handoff_path = DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"
    default_builder_path = DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"
    default_admission_path = DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"

    if not handoff_path_obj.exists() or handoff_path_obj == default_handoff_path:
        build_v103_handoff_integrity(v102_closeout_path=v102_closeout_path, out_dir=str(handoff_path_obj.parent))
    handoff = load_json(handoff_integrity_path)
    if handoff.get("handoff_integrity_status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_10_3_REAL_ORIGIN_SUBSTRATE_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_10_3_real_origin_substrate_inputs_invalid",
                "real_origin_substrate_admission_status": "invalid",
                "v0_10_4_handoff_mode": "rebuild_v0_10_3_real_origin_substrate_inputs_first",
            },
            "handoff_integrity": handoff,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.10.3 Closeout\n\n- version_decision: `v0_10_3_real_origin_substrate_inputs_invalid`\n")
        return payload

    if not builder_path_obj.exists() or builder_path_obj == default_builder_path:
        build_v103_real_origin_substrate_builder(
            v102_pool_delta_path=v102_pool_delta_path,
            out_dir=str(builder_path_obj.parent),
        )
    builder = load_json(real_origin_substrate_builder_path)

    if not admission_path_obj.exists() or admission_path_obj == default_admission_path:
        build_v103_real_origin_substrate_admission(
            real_origin_substrate_builder_path=real_origin_substrate_builder_path,
            out_dir=str(admission_path_obj.parent),
        )
    admission = load_json(real_origin_substrate_admission_path)

    admission_status = str(admission.get("real_origin_substrate_admission_status") or "invalid")
    max_single_source_share_pct = float(admission.get("max_single_source_share_pct") or builder.get("max_single_source_share_pct") or 0.0)
    if admission_status == "ready" and max_single_source_share_pct <= READY_MAX_SINGLE_SOURCE_SHARE_PCT:
        version_decision = "v0_10_3_first_real_origin_workflow_substrate_ready"
        handoff_mode = "characterize_first_real_origin_workflow_profile"
        status = "PASS"
    elif admission_status == "partial":
        version_decision = "v0_10_3_first_real_origin_workflow_substrate_partial"
        handoff_mode = "refine_real_origin_substrate_composition_first"
        status = "PASS"
    else:
        version_decision = "v0_10_3_real_origin_substrate_inputs_invalid"
        handoff_mode = "rebuild_v0_10_3_real_origin_substrate_inputs_first"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_substrate_size": admission.get("real_origin_substrate_size"),
            "source_coverage_table": admission.get("source_coverage_table"),
            "workflow_family_mix": admission.get("workflow_family_coverage_table"),
            "complexity_mix": admission.get("complexity_coverage_table"),
            "max_single_source_share_pct": max_single_source_share_pct,
            "real_origin_substrate_admission_status": admission_status,
            "why_this_is_or_is_not_valid": (
                "The first real-origin workflow substrate is now frozen from the ready pool with preserved provenance, source diversity, and zero proxy leakage."
                if admission_status == "ready"
                else "A governance-clean real-origin substrate can be frozen, but one or more composition goals remain weaker than the preferred characterization floor."
                if admission_status == "partial"
                else "Handoff or substrate-freeze inputs are invalid and must be rebuilt before real-origin profile characterization can proceed."
            ),
            "v0_10_4_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "real_origin_substrate_builder": builder,
        "real_origin_substrate_admission": admission,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.3 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- real_origin_substrate_size: `{admission.get('real_origin_substrate_size')}`",
                f"- max_single_source_share_pct: `{max_single_source_share_pct}`",
                f"- v0_10_4_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.3 real-origin substrate closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--real-origin-substrate-builder", default=str(DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"))
    parser.add_argument("--real-origin-substrate-admission", default=str(DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--v102-closeout", default=str(DEFAULT_V102_CLOSEOUT_PATH))
    parser.add_argument("--v102-pool-delta", default=str(DEFAULT_V102_POOL_DELTA_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v103_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        real_origin_substrate_builder_path=str(args.real_origin_substrate_builder),
        real_origin_substrate_admission_path=str(args.real_origin_substrate_admission),
        v102_closeout_path=str(args.v102_closeout),
        v102_pool_delta_path=str(args.v102_pool_delta),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
