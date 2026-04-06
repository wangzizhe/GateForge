from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .agent_modelica_v0_6_2_common import (
    DEFAULT_AUTHORITY_SLICE_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V060_SUBSTRATE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_2_handoff_integrity import build_v062_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_authority_slice"


_EXTRA_ROWS: list[dict[str, Any]] = [
    {
        "task_id": "v062_simple_pump_secondary_loop",
        "family_id": "medium_redeclare_alignment",
        "complexity_tier": "simple",
        "slice_class": "already-covered",
        "qualitative_bucket": "none",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_medium_dual_coil_air_handler",
        "family_id": "medium_redeclare_alignment",
        "complexity_tier": "medium",
        "slice_class": "boundary-adjacent",
        "qualitative_bucket": "fluid_network_medium_surface_pressure",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_complex_branch_pump_header",
        "family_id": "medium_redeclare_alignment",
        "complexity_tier": "complex",
        "slice_class": "boundary-adjacent",
        "qualitative_bucket": "fluid_network_medium_surface_pressure",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_complex_chiller_primary_secondary",
        "family_id": "medium_redeclare_alignment",
        "complexity_tier": "complex",
        "slice_class": "undeclared-but-bounded-candidate",
        "qualitative_bucket": "fluid_network_medium_surface_pressure",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_simple_sensor_fusion_bus",
        "family_id": "local_interface_alignment",
        "complexity_tier": "simple",
        "slice_class": "already-covered",
        "qualitative_bucket": "none",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_medium_two_zone_signal_crossfeed",
        "family_id": "local_interface_alignment",
        "complexity_tier": "medium",
        "slice_class": "boundary-adjacent",
        "qualitative_bucket": "cross_domain_interface_pressure",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_complex_ev_aux_actuator_chain",
        "family_id": "local_interface_alignment",
        "complexity_tier": "complex",
        "slice_class": "boundary-adjacent",
        "qualitative_bucket": "cross_domain_interface_pressure",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_complex_multi_sensor_feedback_mesh",
        "family_id": "local_interface_alignment",
        "complexity_tier": "complex",
        "slice_class": "already-covered",
        "qualitative_bucket": "none",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_simple_pwm_fan_driver",
        "family_id": "component_api_alignment",
        "complexity_tier": "simple",
        "slice_class": "already-covered",
        "qualitative_bucket": "none",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_medium_converter_sensor_feedback",
        "family_id": "component_api_alignment",
        "complexity_tier": "medium",
        "slice_class": "boundary-adjacent",
        "qualitative_bucket": "cross_domain_interface_pressure",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_complex_battery_charger_supervisor",
        "family_id": "component_api_alignment",
        "complexity_tier": "complex",
        "slice_class": "already-covered",
        "qualitative_bucket": "none",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
    {
        "task_id": "v062_complex_converter_protection_matrix",
        "family_id": "component_api_alignment",
        "complexity_tier": "complex",
        "slice_class": "boundary-adjacent",
        "qualitative_bucket": "cross_domain_interface_pressure",
        "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
    },
]


def build_v062_authority_slice(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    substrate_path: str = str(DEFAULT_V060_SUBSTRATE_PATH),
    out_dir: str = str(DEFAULT_AUTHORITY_SLICE_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v062_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    substrate = load_json(substrate_path)
    base_rows = substrate.get("task_rows") if isinstance(substrate.get("task_rows"), list) else []
    task_rows = [row for row in base_rows if isinstance(row, dict)] + list(_EXTRA_ROWS)

    family_breakdown = dict(Counter(str(r.get("family_id") or "") for r in task_rows))
    complexity_breakdown = dict(Counter(str(r.get("complexity_tier") or "") for r in task_rows))
    profile_subregion_breakdown = dict(Counter(str(r.get("slice_class") or "") for r in task_rows))
    fluid_network_extension_observable_case_count = sum(
        1 for r in task_rows if "fluid_network_medium_surface_pressure" in str(r.get("qualitative_bucket") or "")
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if integrity.get("status") == "PASS" else "FAIL",
        "slice_extension_mode": "widened",
        "authority_slice_frozen": bool(integrity.get("status") == "PASS"),
        "distribution_logic_preserved": True,
        "case_count": len(task_rows),
        "family_breakdown": family_breakdown,
        "complexity_breakdown": complexity_breakdown,
        "profile_subregion_breakdown": profile_subregion_breakdown,
        "why_same_distribution_logic_is_preserved": (
            "The slice extends the v0.6.0 representative real-distribution substrate "
            "without reintroducing boundary-pressure-driven case selection; added cases "
            "preserve the same family-balanced, mixed-complexity, stage_2-focused logic."
        ),
        "fluid_network_extension_observable_case_count": fluid_network_extension_observable_case_count,
        "task_rows": task_rows,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.2 Authority Slice",
                "",
                "- slice_extension_mode: `widened`",
                f"- case_count: `{len(task_rows)}`",
                f"- fluid_network_extension_observable_case_count: `{fluid_network_extension_observable_case_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.2 authority slice.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--substrate", default=str(DEFAULT_V060_SUBSTRATE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_AUTHORITY_SLICE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v062_authority_slice(
        handoff_integrity_path=str(args.handoff_integrity),
        substrate_path=str(args.substrate),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "case_count": payload.get("case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
