from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_20_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_20_dual_recheck import build_v0320_dual_recheck
from .agent_modelica_v0_3_20_first_fix_evidence import build_v0320_first_fix_evidence
from .agent_modelica_v0_3_20_patch_contract import build_v0320_patch_contract
from .agent_modelica_v0_3_20_taskset import build_v0320_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0320_closeout(
    *,
    patch_contract_path: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"),
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "summary.json"),
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    dual_recheck_path: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(patch_contract_path).exists():
        build_v0320_patch_contract(out_dir=str(Path(patch_contract_path).parent))
    if not Path(taskset_path).exists():
        build_v0320_taskset(out_dir=str(Path(taskset_path).parent))
    if not Path(first_fix_path).exists():
        build_v0320_first_fix_evidence(out_dir=str(Path(first_fix_path).parent))
    if not Path(dual_recheck_path).exists():
        build_v0320_dual_recheck(out_dir=str(Path(dual_recheck_path).parent))

    patch_contract = load_json(patch_contract_path)
    taskset = load_json(taskset_path)
    first_fix = load_json(first_fix_path)
    dual_recheck = load_json(dual_recheck_path)

    patch_applied_rate = float(first_fix.get("patch_applied_rate_pct") or 0.0)
    signature_advance_rate = float(first_fix.get("signature_advance_rate_pct") or 0.0)
    first_fix_ready = patch_applied_rate >= 70.0 and signature_advance_rate >= 50.0
    dual_ready = bool(first_fix_ready and int(dual_recheck.get("second_residual_exposed_count") or 0) > 0)
    if first_fix_ready and dual_ready:
        version_decision = "stage2_first_fix_execution_ready"
    elif first_fix_ready:
        version_decision = "stage2_first_fix_execution_partially_ready"
    else:
        version_decision = "stage2_first_fix_execution_not_ready"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_FIRST_FIX_EXECUTION_CLOSEOUT_READY",
        "patch_contract": {
            "status": norm(patch_contract.get("status")),
            "selection_mode": norm(patch_contract.get("selection_mode")),
        },
        "taskset": {
            "status": norm(taskset.get("status")),
            "single_task_count": int(taskset.get("single_task_count") or 0),
            "dual_sidecar_task_count": int(taskset.get("dual_sidecar_task_count") or 0),
        },
        "first_fix_evidence": {
            "status": norm(first_fix.get("status")),
            "patch_applied_rate_pct": patch_applied_rate,
            "signature_advance_rate_pct": signature_advance_rate,
            "admitted_task_count": int(first_fix.get("admitted_task_count") or 0),
            "advance_mode_counts": dict(first_fix.get("advance_mode_counts") or {}),
            "signature_advance_not_fired_reason_counts": dict(first_fix.get("signature_advance_not_fired_reason_counts") or {}),
        },
        "dual_recheck": {
            "status": norm(dual_recheck.get("status")),
            "first_fix_execution_ready": bool(dual_recheck.get("first_fix_execution_ready")),
            "second_residual_exposed_count": int(dual_recheck.get("second_residual_exposed_count") or 0),
            "full_dual_resolution_count": int(dual_recheck.get("full_dual_resolution_count") or 0),
        },
        "conclusion": {
            "version_decision": version_decision,
            "single_mismatch_first_fix_ready": first_fix_ready,
            "dual_mismatch_multiround_ready": dual_ready,
            "summary": (
                "Static authoritative candidates convert stage-2 API diagnosis into applied first-fix execution, and the dual-mismatch sidecar now exposes second residuals."
                if version_decision == "stage2_first_fix_execution_ready"
                else (
                    "Single-mismatch first-fix execution is ready, but the dual-mismatch multiround lane is not yet stable."
                    if version_decision == "stage2_first_fix_execution_partially_ready"
                    else "The current constrained first-fix path still does not convert diagnosis into reliable patch execution."
                )
            ),
            "claim_boundary": "This version establishes constrained API recovery from static authoritative candidates; it does not yet establish free-form API discovery.",
            "next_version_target": "If single-fix execution is ready, the next version should re-open stage-2 dual-mismatch multiround lane design on top of the constrained patch substrate.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.20 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- single_mismatch_first_fix_ready: `{(payload.get('conclusion') or {}).get('single_mismatch_first_fix_ready')}`",
                f"- dual_mismatch_multiround_ready: `{(payload.get('conclusion') or {}).get('dual_mismatch_multiround_ready')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.20 closeout.")
    parser.add_argument("--patch-contract", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"))
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--dual-recheck", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0320_closeout(
        patch_contract_path=str(args.patch_contract),
        taskset_path=str(args.taskset),
        first_fix_path=str(args.first_fix),
        dual_recheck_path=str(args.dual_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
