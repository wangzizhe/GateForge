from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_33_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_MANIFEST_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    DEFAULT_V0331_CLOSEOUT_PATH,
    DEFAULT_V0332_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    handoff_substrate_valid,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_33_coverage_manifest import build_v0333_coverage_manifest
from .agent_modelica_v0_3_33_dual_recheck import build_v0333_dual_recheck
from .agent_modelica_v0_3_33_first_fix_evidence import build_v0333_first_fix_evidence
from .agent_modelica_v0_3_33_surface_export_audit import build_v0333_surface_export_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def _subtype_supported(v0331_closeout: dict, subtype: str) -> bool:
    first_fix = (((v0331_closeout.get("first_fix_evidence") or {}).get("subtype_breakdown")) or {}).get(subtype) or {}
    dual = (((v0331_closeout.get("dual_recheck") or {}).get("subtype_breakdown")) or {}).get(subtype) or {}
    return (
        int(first_fix.get("task_count") or 0) > 0
        and int(dual.get("task_count") or 0) > 0
        and float(dual.get("second_residual_medium_redeclare_retained_rate_pct") or 0.0) >= 60.0
        and float(dual.get("dual_full_resolution_rate_pct") or 0.0) >= 40.0
    )


def build_v0333_closeout(
    *,
    v0331_closeout_path: str = str(DEFAULT_V0331_CLOSEOUT_PATH),
    v0332_closeout_path: str = str(DEFAULT_V0332_CLOSEOUT_PATH),
    manifest_path: str = str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"),
    surface_audit_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(manifest_path).exists():
        build_v0333_coverage_manifest(v0331_closeout_path=v0331_closeout_path, v0332_closeout_path=v0332_closeout_path, out_dir=str(Path(manifest_path).parent))
    if not Path(surface_audit_path).exists():
        build_v0333_surface_export_audit(manifest_path=str(DEFAULT_MANIFEST_OUT_DIR / "taskset.json"), out_dir=str(Path(surface_audit_path).parent))
    if not Path(first_fix_path).exists():
        build_v0333_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0333_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))

    v0331 = load_json(v0331_closeout_path)
    v0332 = load_json(v0332_closeout_path)
    manifest = load_json(manifest_path)
    surface = load_json(surface_audit_path)
    first_fix = load_json(first_fix_path)
    dual = load_json(dual_recheck_path)

    if not handoff_substrate_valid(v0331, v0332):
        version_decision = "handoff_substrate_invalid"
        third_family_status = "still_partial_due_to_pipe_slice"
        pipe_slice_authority_confidence = "directional_only"
        next_phase_recommendation = "repair_handoff_substrate"
        primary_bottleneck = "handoff_substrate_invalid"
    else:
        construction_mode = norm(manifest.get("coverage_construction_mode"))
        surface_ready = (
            norm(surface.get("status")) == "PASS"
            and float(surface.get("surface_export_success_rate_pct") or 0.0) >= 80.0
            and float(surface.get("canonical_in_candidate_rate_pct") or 0.0) >= 80.0
        )
        discovery_ready = (
            norm(first_fix.get("execution_status")) == "executed"
            and float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0) >= 80.0
            and float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0) >= 70.0
            and float(first_fix.get("patch_applied_rate_pct") or 0.0) >= 70.0
            and float(first_fix.get("signature_advance_rate_pct") or 0.0) >= 50.0
            and float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) <= 10.0
        )
        dual_ready = (
            norm(dual.get("execution_status")) == "executed"
            and float(dual.get("pipe_slice_second_residual_rate_pct") or 0.0) >= 60.0
            and float(dual.get("pipe_slice_second_residual_medium_redeclare_retained_rate_pct") or 0.0) >= 60.0
            and float(dual.get("pipe_slice_dual_full_resolution_rate_pct") or 0.0) >= 40.0
        )
        pipe_slice_authority_confidence = (
            "supported"
            if int(manifest.get("active_dual_task_count") or 0) >= 10 and float(dual.get("pipe_slice_dual_full_resolution_rate_pct") or 0.0) >= 50.0
            else "directional_only"
        )
        boundary_supported = _subtype_supported(v0331, "boundary_like")
        vessel_supported = _subtype_supported(v0331, "vessel_or_volume_like")
        if construction_mode == "insufficient":
            version_decision = "stage2_medium_redeclare_pipe_slice_boundary_regressed"
            third_family_status = "pipe_slice_boundary_regressed"
            next_phase_recommendation = "continue_pipe_slice_confirmation"
            primary_bottleneck = "coverage_construction_feasibility"
        elif not surface_ready:
            version_decision = "stage2_medium_redeclare_pipe_slice_boundary_regressed"
            third_family_status = "pipe_slice_boundary_regressed"
            next_phase_recommendation = "continue_pipe_slice_confirmation"
            primary_bottleneck = "surface_export_substrate"
        elif not discovery_ready:
            version_decision = "stage2_medium_redeclare_pipe_slice_partially_ready"
            third_family_status = "still_partial_due_to_pipe_slice"
            next_phase_recommendation = "continue_pipe_slice_confirmation"
            if float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0) < 80.0:
                primary_bottleneck = "candidate_source_failure"
            elif float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0) < 70.0:
                primary_bottleneck = "candidate_ranking_failure"
            elif float(first_fix.get("patch_applied_rate_pct") or 0.0) < 70.0:
                primary_bottleneck = "patch_application_failure"
            else:
                primary_bottleneck = "signature_advance_failure"
        elif not dual_ready:
            version_decision = "stage2_medium_redeclare_pipe_slice_partially_ready"
            third_family_status = "still_partial_due_to_pipe_slice"
            next_phase_recommendation = "continue_pipe_slice_confirmation"
            primary_bottleneck = "dual_retention_or_resolution"
        elif not (boundary_supported and vessel_supported):
            version_decision = "stage2_medium_redeclare_pipe_slice_partially_ready"
            third_family_status = "still_partial_due_to_pipe_slice"
            next_phase_recommendation = "run_final_v0_3_phase_synthesis"
            primary_bottleneck = "third_family_prerequisite_reference_invalid"
        elif pipe_slice_authority_confidence != "supported":
            version_decision = "stage2_medium_redeclare_pipe_slice_partially_ready"
            third_family_status = "still_partial_due_to_pipe_slice"
            next_phase_recommendation = "continue_pipe_slice_confirmation"
            primary_bottleneck = "pipe_slice_authority_confidence"
        else:
            version_decision = "stage2_medium_redeclare_pipe_slice_coverage_ready"
            third_family_status = "full_widened_authority_ready"
            next_phase_recommendation = "run_final_v0_3_phase_synthesis"
            primary_bottleneck = "none"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_MEDIUM_REDECLARE_PIPE_SLICE_WIDENED_CLOSEOUT_READY",
        "conclusion": {
            "version_decision": version_decision,
            "third_family_recomposition_status": third_family_status,
            "pipe_slice_authority_confidence": pipe_slice_authority_confidence,
            "primary_bottleneck": primary_bottleneck,
            "next_phase_recommendation": next_phase_recommendation,
            "v0_3_34_handoff_spec": str((DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json").resolve()),
            "v0331_cross_reference": str(Path(v0331_closeout_path).resolve()),
        },
        "coverage_manifest": manifest,
        "surface_export_audit": surface,
        "first_fix_evidence": first_fix,
        "dual_recheck": dual,
        "v0331_reference": {
            "version_decision": norm(((v0331.get("conclusion") or {}).get("version_decision"))),
            "authority_confidence": norm(((v0331.get("conclusion") or {}).get("authority_confidence"))),
            "boundary_like_supported": _subtype_supported(v0331, "boundary_like"),
            "vessel_or_volume_like_supported": _subtype_supported(v0331, "vessel_or_volume_like"),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.33 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- third_family_recomposition_status: `{(payload.get('conclusion') or {}).get('third_family_recomposition_status')}`",
                f"- pipe_slice_authority_confidence: `{(payload.get('conclusion') or {}).get('pipe_slice_authority_confidence')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.33 closeout.")
    parser.add_argument("--v0331-closeout", default=str(DEFAULT_V0331_CLOSEOUT_PATH))
    parser.add_argument("--v0332-closeout", default=str(DEFAULT_V0332_CLOSEOUT_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--surface-audit", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0333_closeout(
        v0331_closeout_path=str(args.v0331_closeout),
        v0332_closeout_path=str(args.v0332_closeout),
        manifest_path=str(args.manifest),
        surface_audit_path=str(args.surface_audit),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision"), "third_family_recomposition_status": (payload.get("conclusion") or {}).get("third_family_recomposition_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
