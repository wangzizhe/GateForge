from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_21_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_21_dual_recheck import build_v0321_dual_recheck
from .agent_modelica_v0_3_21_first_fix_evidence import build_v0321_first_fix_evidence
from .agent_modelica_v0_3_21_surface_index import build_v0321_surface_index
from .agent_modelica_v0_3_21_taskset import build_v0321_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0321_closeout(
    *,
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "summary.json"),
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(surface_index_path).exists():
        build_v0321_surface_index(out_dir=str(Path(surface_index_path).parent))
    if not Path(taskset_path).exists():
        build_v0321_taskset(out_dir=str(Path(taskset_path).parent))
    if not Path(first_fix_path).exists():
        build_v0321_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0321_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))

    surface_index = load_json(surface_index_path)
    taskset = load_json(taskset_path)
    first_fix = load_json(first_fix_path)
    dual_recheck = load_json(dual_recheck_path)

    candidate_contains_rate = float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0)
    patch_applied_rate = float(first_fix.get("patch_applied_rate_pct") or 0.0)
    signature_advance_rate = float(first_fix.get("signature_advance_rate_pct") or 0.0)
    first_fix_ready = candidate_contains_rate >= 80.0 and patch_applied_rate >= 70.0 and signature_advance_rate >= 50.0
    dual_ready = bool(
        first_fix_ready
        and int(dual_recheck.get("second_residual_undefined_symbol_count") or 0) > 0
        and int(dual_recheck.get("full_dual_resolution_count") or 0) > 0
    )
    if first_fix_ready and dual_ready:
        version_decision = "stage2_api_discovery_ready"
    elif first_fix_ready:
        version_decision = "stage2_api_discovery_partially_ready"
    else:
        version_decision = "stage2_api_discovery_not_ready"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_API_DISCOVERY_CLOSEOUT_READY",
        "surface_index": {
            "status": norm(surface_index.get("status")),
            "source_mode": norm(surface_index.get("source_mode")),
            "modelica_version": norm(surface_index.get("modelica_version")),
        },
        "taskset": {
            "status": norm(taskset.get("status")),
            "single_task_count": int(taskset.get("single_task_count") or 0),
            "dual_sidecar_task_count": int(taskset.get("dual_sidecar_task_count") or 0),
        },
        "first_fix_evidence": {
            "status": norm(first_fix.get("status")),
            "candidate_contains_canonical_rate_pct": candidate_contains_rate,
            "candidate_top1_canonical_rate_pct": float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0),
            "parameter_discovery_top1_canonical_rate_pct": float(first_fix.get("parameter_discovery_top1_canonical_rate_pct") or 0.0),
            "class_path_discovery_top1_canonical_rate_pct": float(first_fix.get("class_path_discovery_top1_canonical_rate_pct") or 0.0),
            "patch_applied_rate_pct": patch_applied_rate,
            "signature_advance_rate_pct": signature_advance_rate,
            "admitted_task_count": int(first_fix.get("admitted_task_count") or 0),
            "advance_mode_counts": dict(first_fix.get("advance_mode_counts") or {}),
            "signature_advance_not_fired_reason_counts": dict(first_fix.get("signature_advance_not_fired_reason_counts") or {}),
        },
        "dual_recheck": {
            "status": norm(dual_recheck.get("status")),
            "first_fix_discovery_ready": bool(dual_recheck.get("first_fix_discovery_ready")),
            "second_residual_exposed_count": int(dual_recheck.get("second_residual_exposed_count") or 0),
            "second_residual_undefined_symbol_count": int(dual_recheck.get("second_residual_undefined_symbol_count") or 0),
            "full_dual_resolution_count": int(dual_recheck.get("full_dual_resolution_count") or 0),
        },
        "conclusion": {
            "version_decision": version_decision,
            "single_mismatch_api_discovery_ready": first_fix_ready,
            "dual_mismatch_multiround_ready": dual_ready,
            "summary": (
                "Authoritative local surface discovery now preserves first-fix execution and keeps the dual-mismatch stage-2 API lane operational."
                if version_decision == "stage2_api_discovery_ready"
                else (
                    "Single-mismatch local API discovery is viable, but the dual-mismatch multiround lane is not yet stable under discovery-mode selection."
                    if version_decision == "stage2_api_discovery_partially_ready"
                    else "Without pre-baked one-to-one mappings, the current local API discovery path does not yet preserve reliable first-fix execution."
                )
            ),
            "claim_boundary": "This version only establishes authoritative local API discovery within the fixed simple+medium component surface; it does not establish free-form API discovery or topology-level structural repair.",
            "next_version_target": "If discovery is ready, the next version should expand the component_api_alignment lane toward broader API discovery coverage while holding first-fix execution stable.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.21 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- single_mismatch_api_discovery_ready: `{(payload.get('conclusion') or {}).get('single_mismatch_api_discovery_ready')}`",
                f"- dual_mismatch_multiround_ready: `{(payload.get('conclusion') or {}).get('dual_mismatch_multiround_ready')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.21 closeout.")
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "summary.json"))
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0321_closeout(
        surface_index_path=str(args.surface_index),
        taskset_path=str(args.taskset),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
