from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_23_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    DEFAULT_TARGET_MANIFEST_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_23_dual_recheck import build_v0323_dual_recheck
from .agent_modelica_v0_3_23_first_fix_evidence import build_v0323_first_fix_evidence
from .agent_modelica_v0_3_23_patch_contract import build_v0323_patch_contract
from .agent_modelica_v0_3_23_target_manifest import build_v0323_target_manifest


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0323_closeout(
    *,
    manifest_path: str = str(DEFAULT_TARGET_MANIFEST_OUT_DIR / "summary.json"),
    patch_contract_path: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(manifest_path).exists():
        build_v0323_target_manifest(out_dir=str(Path(manifest_path).parent))
    if not Path(patch_contract_path).exists():
        build_v0323_patch_contract(out_dir=str(Path(patch_contract_path).parent))
    if not Path(first_fix_path).exists():
        build_v0323_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0323_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))
    manifest = load_json(manifest_path)
    contract = load_json(patch_contract_path)
    first_fix = load_json(first_fix_path)
    dual = load_json(dual_recheck_path)

    boundary_rejected = (
        float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) < 50.0
        or float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) > 50.0
    )
    first_fix_ready = (
        float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) >= 80.0
        and float(first_fix.get("patch_applied_rate_pct") or 0.0) >= 70.0
        and float(first_fix.get("signature_advance_rate_pct") or 0.0) >= 50.0
        and float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) <= 20.0
    )
    dual_ready = float(dual.get("same_cluster_second_residual_rate_pct") or 0.0) >= 50.0
    if boundary_rejected:
        version_decision = "stage2_local_interface_alignment_family_boundary_rejected"
    elif first_fix_ready and dual_ready:
        version_decision = "stage2_local_interface_alignment_ready"
    elif first_fix_ready:
        version_decision = "stage2_local_interface_alignment_partially_ready"
    else:
        version_decision = "stage2_local_interface_alignment_not_ready"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_LOCAL_INTERFACE_ALIGNMENT_CLOSEOUT_READY",
        "target_manifest": {
            "status": norm(manifest.get("status")),
            "active_single_task_count": int(manifest.get("active_single_task_count") or 0),
            "active_dual_task_count": int(manifest.get("active_dual_task_count") or 0),
            "frozen_source_pattern_count": int(manifest.get("frozen_source_pattern_count") or 0),
        },
        "patch_contract": {
            "status": norm(contract.get("status")),
            "selection_mode": norm(contract.get("selection_mode")),
            "max_patch_count_per_round": int(contract.get("max_patch_count_per_round") or 0),
            "patch_scope_definition": norm(contract.get("patch_scope_definition")),
        },
        "first_fix_evidence": {
            "status": norm(first_fix.get("status")),
            "target_first_failure_hit_rate_pct": float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0),
            "patch_applied_rate_pct": float(first_fix.get("patch_applied_rate_pct") or 0.0),
            "focal_patch_hit_rate_pct": float(first_fix.get("focal_patch_hit_rate_pct") or 0.0),
            "signature_advance_rate_pct": float(first_fix.get("signature_advance_rate_pct") or 0.0),
            "drift_to_compile_failure_unknown_rate_pct": float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0),
            "signature_advance_not_fired_reason_counts": dict(first_fix.get("signature_advance_not_fired_reason_counts") or {}),
        },
        "dual_recheck": {
            "status": norm(dual.get("status")),
            "same_cluster_second_residual_rate_pct": float(dual.get("same_cluster_second_residual_rate_pct") or 0.0),
            "second_residual_local_interface_retained_count": int(dual.get("second_residual_local_interface_retained_count") or 0),
            "full_dual_resolution_count": int(dual.get("full_dual_resolution_count") or 0),
        },
        "conclusion": {
            "version_decision": version_decision,
            "first_fix_ready": first_fix_ready,
            "dual_multiround_ready": dual_ready,
            "family_boundary_rejected": boundary_rejected,
            "summary": (
                "The first local_interface_alignment family is now formed: first failure stays local, first-fix executes as a single endpoint patch, and the dual lane exposes the second residual."
                if version_decision == "stage2_local_interface_alignment_ready"
                else (
                    "The first local_interface_alignment family is locally viable at first-fix level, but the multiround lane is not yet fully stable."
                    if version_decision == "stage2_local_interface_alignment_partially_ready"
                    else (
                        "The current local_interface_alignment family boundary is too broad and collapses toward topology-heavy failure; the next version should retreat to a narrower local interface subtype."
                        if version_decision == "stage2_local_interface_alignment_family_boundary_rejected"
                        else "The current local_interface_alignment family does not yet form a stable local first-fix lane."
                    )
                )
            ),
            "next_family_hint": "If ready, the next step should widen within local interface alignment or open the first discovery-like interface candidate layer without allowing topology-heavy rewrites.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.23 Closeout",
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
    parser = argparse.ArgumentParser(description="Build the v0.3.23 closeout.")
    parser.add_argument("--manifest", default=str(DEFAULT_TARGET_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--patch-contract", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0323_closeout(
        manifest_path=str(args.manifest),
        patch_contract_path=str(args.patch_contract),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
