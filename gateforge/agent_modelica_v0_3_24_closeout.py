from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_24_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_24_dual_recheck import build_v0324_dual_recheck
from .agent_modelica_v0_3_24_first_fix_evidence import build_v0324_first_fix_evidence
from .agent_modelica_v0_3_24_patch_contract import build_v0324_patch_contract
from .agent_modelica_v0_3_24_surface_index import build_v0324_surface_index
from .agent_modelica_v0_3_24_taskset import build_v0324_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0324_closeout(
    *,
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "summary.json"),
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "summary.json"),
    patch_contract_path: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(surface_index_path).exists():
        build_v0324_surface_index(out_dir=str(Path(surface_index_path).parent))
    if not Path(taskset_path).exists():
        build_v0324_taskset(out_dir=str(Path(taskset_path).parent))
    if not Path(patch_contract_path).exists():
        build_v0324_patch_contract(out_dir=str(Path(patch_contract_path).parent))
    if not Path(first_fix_path).exists():
        build_v0324_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0324_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))
    surface_index = load_json(surface_index_path)
    taskset = load_json(taskset_path)
    contract = load_json(patch_contract_path)
    first_fix = load_json(first_fix_path)
    dual = load_json(dual_recheck_path)

    export_ready = (
        float(surface_index.get("surface_export_success_rate_pct") or 0.0) >= 80.0
        and float(surface_index.get("fixture_fallback_rate_pct") or 0.0) <= 0.0
        and int(taskset.get("active_single_task_count") or 0) >= 6
        and int(taskset.get("active_dual_task_count") or 0) >= 6
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
        float(dual.get("same_cluster_second_residual_rate_pct") or 0.0) >= 60.0
        and float(dual.get("dual_full_resolution_rate_pct") or 0.0) >= 50.0
    )
    if boundary_rejected:
        version_decision = "stage2_local_interface_discovery_family_boundary_rejected"
    elif export_ready and first_fix_ready and dual_ready:
        version_decision = "stage2_local_interface_discovery_ready"
    elif export_ready and first_fix_ready:
        version_decision = "stage2_local_interface_discovery_partially_ready"
    else:
        version_decision = "stage2_local_interface_discovery_not_ready"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_LOCAL_INTERFACE_DISCOVERY_CLOSEOUT_READY",
        "surface_index": {
            "status": norm(surface_index.get("status")),
            "source_mode": norm(surface_index.get("source_mode")),
            "surface_export_success_rate_pct": float(surface_index.get("surface_export_success_rate_pct") or 0.0),
            "fixture_fallback_rate_pct": float(surface_index.get("fixture_fallback_rate_pct") or 0.0),
            "export_failure_count": int(surface_index.get("export_failure_count") or 0),
        },
        "taskset": {
            "status": norm(taskset.get("status")),
            "execution_mode": norm(taskset.get("execution_mode")),
            "active_single_task_count": int(taskset.get("active_single_task_count") or 0),
            "active_dual_task_count": int(taskset.get("active_dual_task_count") or 0),
            "export_excluded_count": int(taskset.get("export_excluded_count") or 0),
            "export_excluded_task_ids": list(taskset.get("export_excluded_task_ids") or []),
        },
        "patch_contract": {
            "status": norm(contract.get("status")),
            "selection_mode": norm(contract.get("selection_mode")),
            "max_patch_count_per_round": int(contract.get("max_patch_count_per_round") or 0),
            "patch_scope_definition": norm(contract.get("patch_scope_definition")),
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
            "same_cluster_second_residual_rate_pct": float(dual.get("same_cluster_second_residual_rate_pct") or 0.0),
            "second_residual_local_interface_retained_count": int(dual.get("second_residual_local_interface_retained_count") or 0),
            "dual_full_resolution_rate_pct": float(dual.get("dual_full_resolution_rate_pct") or 0.0),
            "full_dual_resolution_count": int(dual.get("full_dual_resolution_count") or 0),
        },
        "conclusion": {
            "version_decision": version_decision,
            "surface_export_ready": export_ready,
            "first_fix_ready": first_fix_ready,
            "dual_multiround_ready": dual_ready,
            "family_boundary_rejected": boundary_rejected,
            "summary": (
                "The local_interface_alignment lane now survives the first discovery step: authoritative local interface surfaces recover the correct endpoint without relying on a static one-to-one answer table, and the dual lane still exposes the second residual."
                if version_decision == "stage2_local_interface_discovery_ready"
                else (
                    "Local interface discovery is viable at first-fix level, but one downstream layer still drops before the family can be promoted as a stable multiround lane."
                    if version_decision == "stage2_local_interface_discovery_partially_ready"
                    else (
                        "The current local interface discovery boundary is too broad and collapses toward compile-failure or topology-heavy drift; the next version should retreat to a narrower local subtype."
                        if version_decision == "stage2_local_interface_discovery_family_boundary_rejected"
                        else "The current local interface discovery lane does not yet hold once the static endpoint answer table is removed."
                    )
                )
            ),
            "next_family_hint": "If ready, the next step should widen interface-discovery coverage or open the first limited discovery-like layer beyond local source-model surfaces without allowing topology-heavy rewrites.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.24 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- family_boundary_rejected: `{(payload.get('conclusion') or {}).get('family_boundary_rejected')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.24 closeout.")
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "summary.json"))
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--patch-contract", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0324_closeout(
        surface_index_path=str(args.surface_index),
        taskset_path=str(args.taskset),
        patch_contract_path=str(args.patch_contract),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
