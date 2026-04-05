from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_31_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_MANIFEST_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_V0330_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_31_coverage_manifest import build_v0331_coverage_manifest
from .agent_modelica_v0_3_31_dual_recheck import build_v0331_dual_recheck
from .agent_modelica_v0_3_31_first_fix_evidence import build_v0331_first_fix_evidence
from .agent_modelica_v0_3_31_surface_export_audit import build_v0331_surface_export_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0331_closeout(
    *,
    v0330_closeout_path: str = str(DEFAULT_V0330_CLOSEOUT_PATH),
    manifest_path: str = str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"),
    surface_audit_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(manifest_path).exists():
        build_v0331_coverage_manifest(v0330_closeout_path=v0330_closeout_path, out_dir=str(Path(manifest_path).parent))
    if not Path(surface_audit_path).exists():
        build_v0331_surface_export_audit(manifest_path=str(DEFAULT_MANIFEST_OUT_DIR / "taskset.json"), out_dir=str(Path(surface_audit_path).parent))
    if not Path(first_fix_path).exists():
        build_v0331_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0331_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))

    v0330 = load_json(v0330_closeout_path)
    manifest = load_json(manifest_path)
    surface = load_json(surface_audit_path)
    first_fix = load_json(first_fix_path)
    dual = load_json(dual_recheck_path)

    handoff_valid = norm(((v0330.get("conclusion") or {}).get("version_decision"))) == "stage2_medium_redeclare_discovery_ready"
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
        and float(dual.get("post_first_fix_target_bucket_hit_rate_pct") or 0.0) >= 60.0
        and float(dual.get("second_residual_medium_redeclare_retained_rate_pct") or 0.0) >= 60.0
        and float(dual.get("dual_full_resolution_rate_pct") or 0.0) >= 40.0
    )
    authority_confidence = (
        "supported"
        if int(manifest.get("active_dual_task_count") or 0) >= 10 and float(dual.get("dual_full_resolution_rate_pct") or 0.0) >= 50.0
        else "directional_only"
    )
    subtype_breakdown = dual.get("subtype_breakdown") if isinstance(dual.get("subtype_breakdown"), dict) else {}
    required_subtypes = (
        "boundary_like",
        "vessel_or_volume_like",
        "pipe_or_local_fluid_interface_like",
    )
    first_fix_subtypes = first_fix.get("subtype_breakdown") if isinstance(first_fix.get("subtype_breakdown"), dict) else {}
    manifest_single_subtypes = manifest.get("single_subtype_counts") if isinstance(manifest.get("single_subtype_counts"), dict) else {}
    subtype_partial = any(
        int(manifest_single_subtypes.get(subtype) or 0) <= 0
        or int((first_fix_subtypes.get(subtype) or {}).get("task_count") or 0) <= 0
        or int((subtype_breakdown.get(subtype) or {}).get("task_count") or 0) <= 0
        or float((subtype_breakdown.get(subtype) or {}).get("second_residual_medium_redeclare_retained_rate_pct") or 0.0) < 60.0
        or float((subtype_breakdown.get(subtype) or {}).get("dual_full_resolution_rate_pct") or 0.0) < 40.0
        for subtype in required_subtypes
    )

    if not handoff_valid:
        version_decision = "handoff_substrate_invalid"
        primary_bottleneck = "handoff_substrate_invalid"
    elif not surface_ready:
        version_decision = "stage2_medium_redeclare_discovery_not_ready"
        if construction_mode == "insufficient":
            primary_bottleneck = "coverage_construction_feasibility"
        elif float(surface.get("surface_export_success_rate_pct") or 0.0) < 80.0 or float(surface.get("canonical_in_candidate_rate_pct") or 0.0) < 80.0:
            primary_bottleneck = "surface_export_substrate"
        else:
            primary_bottleneck = "surface_export_gate"
    elif not discovery_ready:
        version_decision = "stage2_medium_redeclare_discovery_not_ready"
        if float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0) < 80.0:
            primary_bottleneck = "candidate_source_failure"
        elif float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0) < 70.0:
            primary_bottleneck = "candidate_ranking_failure"
        elif float(first_fix.get("patch_applied_rate_pct") or 0.0) < 70.0:
            primary_bottleneck = "patch_application_failure"
        else:
            primary_bottleneck = "signature_advance_failure"
    elif not dual_ready or subtype_partial or authority_confidence != "supported":
        version_decision = "stage2_medium_redeclare_discovery_coverage_partially_ready"
        primary_bottleneck = "dual_confidence_or_subtype_partial"
    else:
        version_decision = "stage2_medium_redeclare_discovery_coverage_ready"
        primary_bottleneck = "none"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_MEDIUM_REDECLARE_DISCOVERY_COVERAGE_CLOSEOUT_READY",
        "conclusion": {
            "version_decision": version_decision,
            "coverage_construction_mode": construction_mode,
            "authority_confidence": authority_confidence,
            "surface_export_ready": surface_ready,
            "discovery_ready": discovery_ready,
            "dual_ready": dual_ready,
            "primary_bottleneck": primary_bottleneck,
            "v0_3_32_handoff_spec": str((DEFAULT_SURFACE_AUDIT_OUT_DIR / "active_taskset.json").resolve()),
        },
        "coverage_manifest": {
            "status": norm(manifest.get("status")),
            "handoff_substrate_valid": bool(manifest.get("handoff_substrate_valid")),
            "coverage_construction_mode": construction_mode,
            "source_count": int(manifest.get("source_count") or 0),
            "active_single_task_count": int(manifest.get("active_single_task_count") or 0),
            "active_dual_task_count": int(manifest.get("active_dual_task_count") or 0),
            "single_subtype_counts": dict(manifest.get("single_subtype_counts") or {}),
            "dual_subtype_counts": dict(manifest.get("dual_subtype_counts") or {}),
        },
        "surface_export_audit": {
            "status": norm(surface.get("status")),
            "execution_mode": norm(surface.get("execution_mode")),
            "surface_export_success_rate_pct": float(surface.get("surface_export_success_rate_pct") or 0.0),
            "canonical_in_candidate_rate_pct": float(surface.get("canonical_in_candidate_rate_pct") or 0.0),
            "export_excluded_count": int(surface.get("export_excluded_count") or 0),
            "canonical_miss_excluded_count": int(surface.get("canonical_miss_excluded_count") or 0),
        },
        "first_fix_evidence": {
            "status": norm(first_fix.get("status")),
            "execution_status": norm(first_fix.get("execution_status")),
            "candidate_contains_canonical_rate_pct": float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0),
            "candidate_top1_canonical_rate_pct": float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0),
            "patch_applied_rate_pct": float(first_fix.get("patch_applied_rate_pct") or 0.0),
            "signature_advance_rate_pct": float(first_fix.get("signature_advance_rate_pct") or 0.0),
            "drift_to_compile_failure_unknown_rate_pct": float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0),
            "subtype_breakdown": dict(first_fix.get("subtype_breakdown") or {}),
        },
        "dual_recheck": {
            "status": norm(dual.get("status")),
            "execution_status": norm(dual.get("execution_status")),
            "post_first_fix_target_bucket_hit_rate_pct": float(dual.get("post_first_fix_target_bucket_hit_rate_pct") or 0.0),
            "second_residual_medium_redeclare_retained_rate_pct": float(dual.get("second_residual_medium_redeclare_retained_rate_pct") or 0.0),
            "dual_full_resolution_rate_pct": float(dual.get("dual_full_resolution_rate_pct") or 0.0),
            "subtype_breakdown": subtype_breakdown,
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.31 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- authority_confidence: `{(payload.get('conclusion') or {}).get('authority_confidence')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.31 closeout.")
    parser.add_argument("--v0330-closeout", default=str(DEFAULT_V0330_CLOSEOUT_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--surface-audit", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0331_closeout(
        v0330_closeout_path=str(args.v0330_closeout),
        manifest_path=str(args.manifest),
        surface_audit_path=str(args.surface_audit),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision"), "authority_confidence": (payload.get("conclusion") or {}).get("authority_confidence")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
