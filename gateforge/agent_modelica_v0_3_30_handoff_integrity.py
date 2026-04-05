from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_30_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V0329_CLOSEOUT_PATH,
    DEFAULT_V0329_ENTRY_SPEC_PATH,
    DEFAULT_V0329_ENTRY_TASKSET_PATH,
    DEFAULT_V0329_PATCH_CONTRACT_PATH,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def build_v0330_handoff_integrity(
    *,
    v0329_closeout_path: str = str(DEFAULT_V0329_CLOSEOUT_PATH),
    v0329_entry_spec_path: str = str(DEFAULT_V0329_ENTRY_SPEC_PATH),
    v0329_entry_taskset_path: str = str(DEFAULT_V0329_ENTRY_TASKSET_PATH),
    v0329_patch_contract_path: str = str(DEFAULT_V0329_PATCH_CONTRACT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v0329_closeout_path)
    entry_spec = load_json(v0329_entry_spec_path)
    taskset_payload = load_json(v0329_entry_taskset_path)
    patch_contract = load_json(v0329_patch_contract_path)
    taskset = taskset_payload.get("summary") if isinstance(taskset_payload.get("summary"), dict) else taskset_payload

    selected_family = norm((closeout.get("conclusion") or {}).get("v0_3_30_target_family")) or norm(entry_spec.get("selected_family"))
    handoff_valid = (
        selected_family == "medium_redeclare_alignment"
        and norm(entry_spec.get("selected_family")) == "medium_redeclare_alignment"
        and norm(taskset.get("status")) == "PASS"
        and norm(patch_contract.get("status")) == "PASS"
        and int(taskset.get("entry_source_count") or 0) >= 3
        and int(taskset.get("entry_single_task_count") or 0) >= 6
        and int(taskset.get("entry_dual_sidecar_count") or 0) >= 4
        and "insert_redeclare_package_medium" in [norm(x) for x in (entry_spec.get("allowed_patch_types") or [])]
        and norm(entry_spec.get("allowed_patch_scope")) == "single_component_redeclare_clause_only"
    )
    failure_reasons: list[str] = []
    if selected_family != "medium_redeclare_alignment":
        failure_reasons.append("selected_family_mismatch")
    if norm(entry_spec.get("selected_family")) != "medium_redeclare_alignment":
        failure_reasons.append("entry_spec_family_mismatch")
    if norm(taskset.get("status")) != "PASS":
        failure_reasons.append("entry_taskset_not_pass")
    if norm(patch_contract.get("status")) != "PASS":
        failure_reasons.append("patch_contract_not_pass")
    if int(taskset.get("entry_source_count") or 0) < 3:
        failure_reasons.append("entry_source_count_below_floor")
    if int(taskset.get("entry_single_task_count") or 0) < 6:
        failure_reasons.append("entry_single_count_below_floor")
    if int(taskset.get("entry_dual_sidecar_count") or 0) < 4:
        failure_reasons.append("entry_dual_count_below_floor")
    if "insert_redeclare_package_medium" not in [norm(x) for x in (entry_spec.get("allowed_patch_types") or [])]:
        failure_reasons.append("missing_promoted_patch_type")
    if norm(entry_spec.get("allowed_patch_scope")) != "single_component_redeclare_clause_only":
        failure_reasons.append("patch_scope_drifted")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if handoff_valid else "FAIL",
        "selected_family": selected_family,
        "entry_source_count": int(taskset.get("entry_source_count") or 0),
        "entry_single_task_count": int(taskset.get("entry_single_task_count") or 0),
        "entry_dual_sidecar_count": int(taskset.get("entry_dual_sidecar_count") or 0),
        "allowed_patch_types": list(entry_spec.get("allowed_patch_types") or []),
        "allowed_patch_scope": norm(entry_spec.get("allowed_patch_scope")),
        "handoff_substrate_valid": handoff_valid,
        "handoff_failure_reasons": failure_reasons,
        "v0_3_30_handoff_spec": str(Path(v0329_entry_spec_path).resolve()) if Path(v0329_entry_spec_path).exists() else str(v0329_entry_spec_path),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.30 Handoff Integrity",
                "",
                f"- status: `{summary.get('status')}`",
                f"- selected_family: `{summary.get('selected_family')}`",
                f"- handoff_substrate_valid: `{summary.get('handoff_substrate_valid')}`",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.30 handoff integrity check.")
    parser.add_argument("--v0329-closeout", default=str(DEFAULT_V0329_CLOSEOUT_PATH))
    parser.add_argument("--v0329-entry-spec", default=str(DEFAULT_V0329_ENTRY_SPEC_PATH))
    parser.add_argument("--v0329-entry-taskset", default=str(DEFAULT_V0329_ENTRY_TASKSET_PATH))
    parser.add_argument("--v0329-patch-contract", default=str(DEFAULT_V0329_PATCH_CONTRACT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0330_handoff_integrity(
        v0329_closeout_path=str(args.v0329_closeout),
        v0329_entry_spec_path=str(args.v0329_entry_spec),
        v0329_entry_taskset_path=str(args.v0329_entry_taskset),
        v0329_patch_contract_path=str(args.v0329_patch_contract),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_substrate_valid": payload.get("handoff_substrate_valid")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
