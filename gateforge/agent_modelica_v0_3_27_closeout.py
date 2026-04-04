from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_27_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_MANIFEST_OUT_DIR,
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    DEFAULT_SURFACE_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_27_coverage_manifest import build_v0327_coverage_manifest
from .agent_modelica_v0_3_27_dual_recheck import build_v0327_dual_recheck
from .agent_modelica_v0_3_27_first_fix_evidence import build_v0327_first_fix_evidence
from .agent_modelica_v0_3_27_patch_contract import build_v0327_patch_contract
from .agent_modelica_v0_3_27_surface_export_audit import build_v0327_surface_export_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0327_closeout(
    *,
    manifest_path: str = str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"),
    surface_audit_path: str = str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"),
    patch_contract_path: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(manifest_path).exists():
        build_v0327_coverage_manifest(out_dir=str(Path(manifest_path).parent))
    if not Path(surface_audit_path).exists():
        build_v0327_surface_export_audit(out_dir=str(Path(surface_audit_path).parent))
    if not Path(patch_contract_path).exists():
        build_v0327_patch_contract(out_dir=str(Path(patch_contract_path).parent))
    if not Path(first_fix_path).exists():
        build_v0327_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0327_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))
    manifest = load_json(manifest_path)
    surface = load_json(surface_audit_path)
    contract = load_json(patch_contract_path)
    first_fix = load_json(first_fix_path)
    dual = load_json(dual_recheck_path)

    export_ready = (
        float(surface.get("surface_export_success_rate_pct") or 0.0) >= 80.0
        and float(surface.get("fixture_fallback_rate_pct") or 0.0) <= 0.0
        and int(surface.get("active_single_task_count") or 0) >= 12
        and int(surface.get("active_dual_sidecar_task_count") or 0) >= 10
    )
    boundary_rejected = (
        float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) < 50.0
        or float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) > 50.0
    )
    first_fix_ready = (
        float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) >= 80.0
        and float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0) >= 80.0
        and float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0) >= 70.0
        and float(first_fix.get("patch_applied_rate_pct") or 0.0) >= 70.0
        and float(first_fix.get("focal_patch_hit_rate_pct") or 0.0) >= 80.0
        and float(first_fix.get("signature_advance_rate_pct") or 0.0) >= 50.0
        and float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) <= 10.0
    )
    dual_ready = (
        float(dual.get("neighbor_component_second_residual_rate_pct") or 0.0) >= 50.0
        and float(dual.get("neighbor_component_second_residual_local_interface_retained_rate_pct") or 0.0) >= 50.0
        and float(dual.get("neighbor_component_dual_full_resolution_rate_pct") or 0.0) >= 40.0
    )
    if boundary_rejected:
        version_decision = "stage2_neighbor_component_local_interface_family_boundary_rejected"
    elif export_ready and first_fix_ready and dual_ready:
        version_decision = "stage2_neighbor_component_local_interface_discovery_ready"
    elif export_ready and first_fix_ready:
        version_decision = "stage2_neighbor_component_local_interface_discovery_partially_ready"
    else:
        version_decision = "stage2_neighbor_component_local_interface_discovery_not_ready"
    dual_task_count = int(dual.get("task_count") or 0)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_NEIGHBOR_COMPONENT_LOCAL_INTERFACE_DISCOVERY_CLOSEOUT_READY",
        "coverage_manifest": {
            "status": norm(manifest.get("status")),
            "single_task_count": int(manifest.get("single_task_count") or 0),
            "dual_sidecar_task_count": int(manifest.get("dual_sidecar_task_count") or 0),
            "source_count": int(manifest.get("source_count") or 0),
        },
        "surface_export_audit": {
            "status": norm(surface.get("status")),
            "execution_mode": norm(surface.get("execution_mode")),
            "source_mode": norm(surface.get("source_mode")),
            "surface_export_success_rate_pct": float(surface.get("surface_export_success_rate_pct") or 0.0),
            "fixture_fallback_rate_pct": float(surface.get("fixture_fallback_rate_pct") or 0.0),
            "export_excluded_count": int(surface.get("export_excluded_count") or 0),
            "export_excluded_task_ids": list(surface.get("export_excluded_task_ids") or []),
            "export_excluded_family_mix": dict(surface.get("export_excluded_family_mix") or {}),
        },
        "patch_contract": {
            "status": norm(contract.get("status")),
            "selection_mode": norm(contract.get("selection_mode")),
            "max_patch_count_per_round": int(contract.get("max_patch_count_per_round") or 0),
            "patch_scope_definition": norm(contract.get("patch_scope_definition")),
            "cross_component_candidate_pooling_allowed": bool(contract.get("cross_component_candidate_pooling_allowed")),
        },
        "first_fix_evidence": {
            "status": norm(first_fix.get("status")),
            "candidate_contains_canonical_rate_pct": float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0),
            "candidate_top1_canonical_rate_pct": float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0),
            "patch_applied_rate_pct": float(first_fix.get("patch_applied_rate_pct") or 0.0),
            "focal_patch_hit_rate_pct": float(first_fix.get("focal_patch_hit_rate_pct") or 0.0),
            "signature_advance_rate_pct": float(first_fix.get("signature_advance_rate_pct") or 0.0),
            "drift_to_compile_failure_unknown_rate_pct": float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0),
            "drift_task_count": int(first_fix.get("drift_task_count") or 0),
            "drift_reason_counts": dict(first_fix.get("drift_reason_counts") or {}),
            "signature_advance_not_fired_reason_counts": dict(first_fix.get("signature_advance_not_fired_reason_counts") or {}),
        },
        "dual_recheck": {
            "status": norm(dual.get("status")),
            "neighbor_component_second_residual_rate_pct": float(dual.get("neighbor_component_second_residual_rate_pct") or 0.0),
            "neighbor_component_second_residual_local_interface_retained_rate_pct": float(
                dual.get("neighbor_component_second_residual_local_interface_retained_rate_pct") or 0.0
            ),
            "second_residual_local_interface_retained_count": int(dual.get("second_residual_local_interface_retained_count") or 0),
            "neighbor_component_dual_full_resolution_rate_pct": float(dual.get("neighbor_component_dual_full_resolution_rate_pct") or 0.0),
            "full_dual_resolution_count": int(dual.get("full_dual_resolution_count") or 0),
            "task_count": dual_task_count,
        },
        "conclusion": {
            "version_decision": version_decision,
            "surface_export_ready": export_ready,
            "first_fix_ready": first_fix_ready,
            "dual_multiround_ready": dual_ready,
            "family_boundary_rejected": boundary_rejected,
            "dual_result_confidence": "directional_only" if dual_task_count < 12 else "normal",
            "summary": (
                "Neighbor-component local interface discovery holds once per-round candidates are restricted to the touched component type: first-fix and second-residual retention remain stable across adjacent components."
                if version_decision == "stage2_neighbor_component_local_interface_discovery_ready"
                else (
                    "Neighbor-component local interface discovery works at first-fix level, but one downstream layer drops before the lane can be promoted as stable."
                    if version_decision == "stage2_neighbor_component_local_interface_discovery_partially_ready"
                    else (
                        "The neighbor-component family crossed into topology-heavy or compile-failure drift; the next version should retreat to a narrower cross-component local subtype."
                        if version_decision == "stage2_neighbor_component_local_interface_family_boundary_rejected"
                        else "The neighbor-component local interface discovery lane does not yet hold once the same-component locality scaffold is removed."
                    )
                )
            ),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.27 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.27 closeout.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--surface-audit", default=str(DEFAULT_SURFACE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--patch-contract", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0327_closeout(
        manifest_path=str(args.manifest),
        surface_audit_path=str(args.surface_audit),
        patch_contract_path=str(args.patch_contract),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
