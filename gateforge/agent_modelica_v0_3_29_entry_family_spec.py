from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_29_common import (
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_TRIAGE_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_29_viability_triage import build_v0329_viability_triage


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_entry_family_spec"


def build_v0329_entry_family_spec(
    *,
    triage_path: str = str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"),
    triage_records_path: str = str(DEFAULT_TRIAGE_OUT_DIR / "records.json"),
    out_dir: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR),
) -> dict:
    if not Path(triage_path).exists() or not Path(triage_records_path).exists():
        build_v0329_viability_triage(out_dir=str(Path(triage_path).parent))
    triage = load_json(triage_path)
    triage_records = load_json(triage_records_path)
    selected_family = norm(triage.get("selected_family"))
    if selected_family == "medium_redeclare_alignment":
        allowed_patch_types = [
            "insert_redeclare_package_medium",
            "replace_redeclare_clause",
            "replace_medium_package_symbol",
        ]
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "PASS",
            "selected_family": selected_family,
            "target_subtype": "stage_2_medium_redeclare_alignment_entry",
            "expected_first_failure": "stage_2_structural_balance_reference|compile_failure_unknown",
            "expected_post_first_fix_residual": "stage_2_structural_balance_reference|compile_failure_unknown",
            "allowed_patch_types": allowed_patch_types,
            "allowed_patch_scope": "single_component_redeclare_clause_only",
            "max_patch_count_per_round": 1,
            "disallowed_widening_directions": [
                "cross_loop_medium_propagation",
                "multi_component_redeclare_fanout",
                "fluid_topology_regeneration",
            ],
            "triage_basis": {
                "selected_family": selected_family,
                "fallback_triggered": bool(triage.get("fallback_triggered")),
                "local_connection_accepted_pattern_count": int(triage.get("local_connection_accepted_pattern_count") or 0),
                "fallback_target_bucket_hit_count": int(triage.get("fallback_target_bucket_hit_count") or 0),
            },
        }
    elif selected_family == "local_connection_fix":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "PASS",
            "selected_family": selected_family,
            "target_subtype": "stage_2_local_connection_fix_entry",
            "expected_first_failure": "stage_2_structural_balance_reference|underconstrained_system",
            "expected_post_first_fix_residual": "stage_2_structural_balance_reference|underconstrained_system",
            "allowed_patch_types": ["add_connect_statement", "replace_local_reference_symbol", "insert_component_declaration"],
            "allowed_patch_scope": "single_local_connection_restoration_only",
            "max_patch_count_per_round": 1,
            "disallowed_widening_directions": [
                "full_topology_rewrite",
                "global_equation_regeneration",
            ],
            "triage_basis": {
                "selected_family": selected_family,
                "fallback_triggered": bool(triage.get("fallback_triggered")),
            },
        }
    else:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "selected_family": "",
            "target_subtype": "",
            "expected_first_failure": "",
            "expected_post_first_fix_residual": "",
            "allowed_patch_types": [],
            "allowed_patch_scope": "",
            "max_patch_count_per_round": 1,
            "disallowed_widening_directions": [],
            "triage_basis": {
                "selected_family": selected_family,
                "fallback_triggered": bool(triage.get("fallback_triggered")),
            },
        }
    payload["triage_records_path"] = str(Path(triage_records_path).resolve()) if Path(triage_records_path).exists() else str(triage_records_path)
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.29 Entry Family Spec",
                "",
                f"- status: `{payload.get('status')}`",
                f"- selected_family: `{payload.get('selected_family')}`",
                f"- target_subtype: `{payload.get('target_subtype')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.29 entry family spec.")
    parser.add_argument("--triage", default=str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"))
    parser.add_argument("--triage-records", default=str(DEFAULT_TRIAGE_OUT_DIR / "records.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0329_entry_family_spec(
        triage_path=str(args.triage),
        triage_records_path=str(args.triage_records),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "selected_family": payload.get("selected_family")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
