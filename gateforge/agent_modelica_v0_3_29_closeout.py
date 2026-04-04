from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_29_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_ENTRY_TASKSET_OUT_DIR,
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    DEFAULT_TRIAGE_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_29_entry_family_spec import build_v0329_entry_family_spec
from .agent_modelica_v0_3_29_entry_taskset import build_v0329_entry_taskset
from .agent_modelica_v0_3_29_patch_contract import build_v0329_patch_contract
from .agent_modelica_v0_3_29_viability_triage import build_v0329_viability_triage


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0329_closeout(
    *,
    triage_path: str = str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"),
    entry_spec_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"),
    taskset_path: str = str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"),
    patch_contract_path: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(triage_path).exists():
        build_v0329_viability_triage(out_dir=str(Path(triage_path).parent))
    if not Path(entry_spec_path).exists():
        build_v0329_entry_family_spec(out_dir=str(Path(entry_spec_path).parent))
    if not Path(taskset_path).exists():
        build_v0329_entry_taskset(out_dir=str(Path(taskset_path).parent))
    if not Path(patch_contract_path).exists():
        build_v0329_patch_contract(out_dir=str(Path(patch_contract_path).parent))

    triage = load_json(triage_path)
    entry_spec = load_json(entry_spec_path)
    taskset = load_json(taskset_path)
    contract = load_json(patch_contract_path)

    selected_family = norm(triage.get("selected_family"))
    entry_ready = (
        selected_family == "medium_redeclare_alignment"
        and norm(taskset.get("status")) == "PASS"
        and norm(contract.get("status")) == "PASS"
        and int(taskset.get("entry_source_count") or 0) >= 3
        and int(taskset.get("entry_single_task_count") or 0) >= 6
        and int(taskset.get("entry_dual_sidecar_count") or 0) >= 4
    )
    if selected_family == "medium_redeclare_alignment" and entry_ready:
        version_decision = "stage2_third_family_entry_ready"
    elif selected_family:
        version_decision = "stage2_third_family_entry_partially_ready"
    else:
        version_decision = "stage2_third_family_boundary_rejected"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_THIRD_FAMILY_ENTRY_FREEZE_READY",
        "triage": {
            "status": norm(triage.get("status")),
            "local_connection_accepted_pattern_count": int(triage.get("local_connection_accepted_pattern_count") or 0),
            "fallback_triggered": bool(triage.get("fallback_triggered")),
            "fallback_target_bucket_hit_count": int(triage.get("fallback_target_bucket_hit_count") or 0),
            "selected_family": selected_family,
        },
        "entry_family_spec": {
            "status": norm(entry_spec.get("status")),
            "selected_family": norm(entry_spec.get("selected_family")),
            "target_subtype": norm(entry_spec.get("target_subtype")),
            "allowed_patch_types": list(entry_spec.get("allowed_patch_types") or []),
            "allowed_patch_scope": norm(entry_spec.get("allowed_patch_scope")),
        },
        "entry_taskset": {
            "status": norm(taskset.get("status")),
            "entry_source_count": int(taskset.get("entry_source_count") or 0),
            "entry_single_task_count": int(taskset.get("entry_single_task_count") or 0),
            "entry_dual_sidecar_count": int(taskset.get("entry_dual_sidecar_count") or 0),
            "post_first_fix_target_bucket_hit_rate_pct": float(taskset.get("post_first_fix_target_bucket_hit_rate_pct") or 0.0),
            "allowed_patch_types": list(taskset.get("allowed_patch_types") or []),
        },
        "patch_contract": {
            "status": norm(contract.get("status")),
            "selected_family": norm(contract.get("selected_family")),
            "allowed_patch_types": list(contract.get("allowed_patch_types") or []),
            "max_patch_count_per_round": int(contract.get("max_patch_count_per_round") or 0),
            "allowed_patch_scope": norm(contract.get("allowed_patch_scope")),
        },
        "conclusion": {
            "version_decision": version_decision,
            "local_connection_fix_status": "accepted" if selected_family == "local_connection_fix" else "rejected_or_not_selected",
            "fallback_selected": selected_family == "medium_redeclare_alignment",
            "v0_3_30_target_family": selected_family,
            "v0_3_30_handoff_spec": str(Path(entry_spec_path).resolve()) if Path(entry_spec_path).exists() else str(entry_spec_path),
            "summary": (
                "Local-connection viability stayed too weak at spec-time, so v0.3.29 froze a narrower medium-redeclare alignment entry that is ready for v0.3.30 first-fix/discovery."
                if version_decision == "stage2_third_family_entry_ready"
                else (
                    "A third-family direction exists, but the frozen entry slice still needs further narrowing before v0.3.30."
                    if version_decision == "stage2_third_family_entry_partially_ready"
                    else "Both the primary and fallback third-family candidates remain too topology-heavy or too broad for bounded entry freeze."
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
                "# v0.3.29 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- v0.3.30_target_family: `{(payload.get('conclusion') or {}).get('v0_3_30_target_family')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.29 closeout.")
    parser.add_argument("--triage", default=str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-spec", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--taskset", default=str(DEFAULT_ENTRY_TASKSET_OUT_DIR / "summary.json"))
    parser.add_argument("--patch-contract", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0329_closeout(
        triage_path=str(args.triage),
        entry_spec_path=str(args.entry_spec),
        taskset_path=str(args.taskset),
        patch_contract_path=str(args.patch_contract),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
