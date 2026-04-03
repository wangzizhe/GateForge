from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_22_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_MANIFEST_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_22_coverage_manifest import build_v0322_coverage_manifest
from .agent_modelica_v0_3_22_dual_recheck import build_v0322_dual_recheck
from .agent_modelica_v0_3_22_first_fix_evidence import build_v0322_first_fix_evidence
from .agent_modelica_v0_3_22_surface_export_audit import build_v0322_surface_export_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def _primary_bottleneck(audit: dict, first_fix: dict, dual: dict) -> str:
    if float(audit.get("surface_export_success_rate_pct") or 0.0) < 80.0:
        return "surface_export"
    if float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0) < 80.0:
        return "candidate_recall"
    if float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0) < 70.0:
        return "top1_ranking"
    if float(first_fix.get("patch_applied_rate_pct") or 0.0) < 70.0 or float(first_fix.get("signature_advance_rate_pct") or 0.0) < 50.0:
        return "patch_execution"
    if float(dual.get("same_component_second_residual_rate_pct") or 0.0) < 60.0:
        return "dual_multiround"
    if int(audit.get("export_excluded_count") or 0) > 0:
        return "surface_export_degraded"
    return "none"


def build_v0322_closeout(
    *,
    manifest_path: str = str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"),
    surface_audit_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(manifest_path).exists():
        build_v0322_coverage_manifest(out_dir=str(Path(manifest_path).parent))
    if not Path(surface_audit_path).exists():
        build_v0322_surface_export_audit(out_dir=str(Path(surface_audit_path).parent))
    if not Path(first_fix_path).exists():
        build_v0322_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0322_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))
    manifest = load_json(manifest_path)
    audit = load_json(surface_audit_path)
    first_fix = load_json(first_fix_path)
    dual = load_json(dual_recheck_path)

    export_ready = float(audit.get("surface_export_success_rate_pct") or 0.0) >= 100.0 and float(audit.get("fixture_fallback_rate_pct") or 0.0) <= 0.0 and int(audit.get("export_excluded_count") or 0) == 0
    recall_ready = float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0) >= 80.0
    top1_ready = float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0) >= 70.0
    patch_ready = float(first_fix.get("patch_applied_rate_pct") or 0.0) >= 70.0 and float(first_fix.get("signature_advance_rate_pct") or 0.0) >= 50.0
    dual_ready = float(dual.get("same_component_second_residual_rate_pct") or 0.0) >= 60.0
    if export_ready and recall_ready and top1_ready and patch_ready and dual_ready:
        version_decision = "stage2_api_discovery_coverage_ready"
    elif float(audit.get("surface_export_success_rate_pct") or 0.0) >= 80.0 and (recall_ready or top1_ready or patch_ready):
        version_decision = "stage2_api_discovery_coverage_partial"
    else:
        version_decision = "stage2_api_discovery_coverage_not_ready"
    bottleneck = _primary_bottleneck(audit, first_fix, dual)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_API_DISCOVERY_COVERAGE_CLOSEOUT_READY",
        "manifest": {
            "status": norm(manifest.get("status")),
            "single_task_count": int(manifest.get("single_task_count") or 0),
            "dual_sidecar_task_count": int(manifest.get("dual_sidecar_task_count") or 0),
        },
        "surface_export_audit": {
            "status": norm(audit.get("status")),
            "execution_mode": norm(audit.get("execution_mode")),
            "surface_export_success_rate_pct": float(audit.get("surface_export_success_rate_pct") or 0.0),
            "surface_contains_expected_symbol_rate_pct": float(audit.get("surface_contains_expected_symbol_rate_pct") or 0.0),
            "inherited_parameter_retention_rate_pct": float(audit.get("inherited_parameter_retention_rate_pct") or 0.0),
            "fixture_fallback_rate_pct": float(audit.get("fixture_fallback_rate_pct") or 0.0),
            "export_excluded_count": int(audit.get("export_excluded_count") or 0),
            "export_excluded_family_mix": dict(audit.get("export_excluded_family_mix") or {}),
        },
        "single_mismatch_evidence": {
            "status": norm(first_fix.get("status")),
            "candidate_contains_canonical_rate_pct": float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0),
            "candidate_top1_canonical_rate_pct": float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0),
            "parameter_discovery_top1_canonical_rate_pct": float(first_fix.get("parameter_discovery_top1_canonical_rate_pct") or 0.0),
            "class_path_discovery_top1_canonical_rate_pct": float(first_fix.get("class_path_discovery_top1_canonical_rate_pct") or 0.0),
            "patch_applied_rate_pct": float(first_fix.get("patch_applied_rate_pct") or 0.0),
            "signature_advance_rate_pct": float(first_fix.get("signature_advance_rate_pct") or 0.0),
            "secondary_error_exposed_early_rate_pct": float(first_fix.get("secondary_error_exposed_early_rate_pct") or 0.0),
            "signature_advance_not_fired_reason_counts": dict(first_fix.get("signature_advance_not_fired_reason_counts") or {}),
        },
        "dual_recheck": {
            "status": norm(dual.get("status")),
            "same_component_second_residual_rate_pct": float(dual.get("same_component_second_residual_rate_pct") or 0.0),
            "same_component_full_resolution_rate_pct": float(dual.get("same_component_full_resolution_rate_pct") or 0.0),
            "second_residual_exposed_count": int(dual.get("second_residual_exposed_count") or 0),
            "full_dual_resolution_count": int(dual.get("full_dual_resolution_count") or 0),
        },
        "conclusion": {
            "version_decision": version_decision,
            "surface_export_ready": export_ready,
            "discovery_recall_ready": recall_ready,
            "top1_ranking_ready": top1_ready,
            "single_patch_execution_ready": patch_ready,
            "dual_multiround_ready": dual_ready,
            "primary_bottleneck_layer": bottleneck,
            "summary": (
                "The local API discovery lane now expands beyond the v0.3.21 slice without losing export, ranking, or same-component dual-mismatch stability."
                if version_decision == "stage2_api_discovery_coverage_ready"
                else (
                    "The discovery lane remains viable under wider coverage, but at least one bottleneck layer is now visible and should guide the next version."
                    if version_decision == "stage2_api_discovery_coverage_partial"
                    else "The v0.3.21 discovery lane does not yet generalize across the expanded component_api_alignment coverage."
                )
            ),
            "claim_boundary": "This version only measures wider local component_api_alignment coverage; it does not establish free-form package search, topology-heavy stage-2 repair, or product-grade API discovery.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.22 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- primary_bottleneck_layer: `{(payload.get('conclusion') or {}).get('primary_bottleneck_layer')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.22 closeout.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--surface-audit", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0322_closeout(
        manifest_path=str(args.manifest),
        surface_audit_path=str(args.surface_audit),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
