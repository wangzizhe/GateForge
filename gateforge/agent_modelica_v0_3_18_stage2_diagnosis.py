from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_18_stage2_common import (
    DEFAULT_DIAGNOSIS_OUT_DIR,
    DEFAULT_SAMPLE_MANIFEST_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_stage2_diagnosis"


DRAFT_DIAGNOSIS = {
    "gen_simple_rc_lowpass_filter": {
        "proposed_action_type": "component_api_alignment",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "low",
            "rationale": "This is a local cross-version API hallucination: in MSL 4.x SineVoltage uses `f`, not `freqHz`. A human with MSL docs can correct the parameter name without changing topology.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "agent_repairable_with_context_injection",
            "high_level_judgment": "agent_repairable",
            "rationale": "The fix is local and documentation-driven. The current loop would likely need component-interface retrieval, but no global topology reasoning is required.",
        },
        "required_information": [
            "component parameter documentation for Modelica.Electrical.Analog.Sources.SineVoltage",
        ],
        "agent_accessible_information": [
            "compiler error excerpt",
            "generated model text",
            "retrievable MSL component docs",
        ],
        "agent_missing_information": [],
        "targeting_recommendation": "target",
    },
    "gen_simple_thermal_heated_mass": {
        "proposed_action_type": "component_api_alignment",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "low",
            "rationale": "The generated class name does not exist in the referenced package. A human can replace it with the correct ambient/fixed-temperature source once the intended thermal boundary condition is recognized.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "agent_repairable_with_context_injection",
            "high_level_judgment": "agent_repairable",
            "rationale": "This is still a local API/class-path problem. The agent needs library lookup support, but not a redesigned repair loop.",
        },
        "required_information": [
            "HeatTransfer source/component class reference",
            "intent that the model needs a fixed ambient boundary",
        ],
        "agent_accessible_information": [
            "compiler error excerpt",
            "generated model text",
            "retrievable MSL component docs",
        ],
        "agent_missing_information": [],
        "targeting_recommendation": "target",
    },
    "gen_simple_two_inertia_shaft": {
        "proposed_action_type": "local_connection_fix",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "medium",
            "rationale": "The model is structurally underconstrained because the second inertia is left without a closing rotational reference. A human can repair it by adding the missing fixed/support closure and restoring a square topology.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "human_only",
            "high_level_judgment": "human_only",
            "rationale": "The compiler only says the system is underdetermined. Choosing the right missing structural closure requires topology intent, not just local API lookup.",
        },
        "required_information": [
            "rotational topology intent",
            "whether the actuator should prescribe torque through a signal or a fixed source",
            "whether the system should include a grounded reference/support",
        ],
        "agent_accessible_information": [
            "underconstrained-system diagnostic",
            "generated model text",
        ],
        "agent_missing_information": [
            "authoritative topology intent",
        ],
        "targeting_recommendation": "exclude",
    },
    "gen_simple_sine_driven_mass": {
        "proposed_action_type": "component_api_alignment",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "low",
            "rationale": "This is the same local parameter-surface mistake as the RC lowpass case: in MSL 4.x `Modelica.Blocks.Sources.Sine` uses `f`, not `freqHz`.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "agent_repairable_with_context_injection",
            "high_level_judgment": "agent_repairable",
            "rationale": "The correction is local and documentable. The current loop needs block-parameter retrieval, but not topology reconstruction.",
        },
        "required_information": [
            "component parameter documentation for Modelica.Blocks.Sources.Sine",
        ],
        "agent_accessible_information": [
            "compiler error excerpt",
            "generated model text",
            "retrievable MSL block docs",
        ],
        "agent_missing_information": [],
        "targeting_recommendation": "target",
    },
    "gen_medium_dc_motor_pi_speed": {
        "proposed_action_type": "component_api_alignment",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "medium",
            "rationale": "The generator chose the wrong DC machine class path. A human can switch from the hallucinated path to the real `BasicMachines.DCMachines` path and then finish any follow-up local interface cleanup if needed.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "agent_repairable_with_context_injection",
            "high_level_judgment": "agent_repairable",
            "rationale": "This still looks like local component-path alignment rather than global model redesign. However, the agent needs library navigation and machine-family documentation.",
        },
        "required_information": [
            "Electrical Machines package/class inventory",
            "expected DC permanent-magnet motor component path",
        ],
        "agent_accessible_information": [
            "compiler error excerpt",
            "generated model text",
            "retrievable library docs",
        ],
        "agent_missing_information": [],
        "targeting_recommendation": "target",
    },
    "gen_medium_pump_tank_pipe_loop": {
        "proposed_action_type": "medium_redeclare_alignment",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "medium",
            "rationale": "This is a classic Modelica.Fluid medium-consistency error. A human familiar with the library can redeclare a shared `package Medium` across the pump, pipe, tank, and boundaries, but it is not a one-line local fix.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "human_only",
            "high_level_judgment": "human_only",
            "rationale": "The current loop would need to propagate a package-level redeclare consistently across several fluid components. That is broader than the local API-fix cases and likely needs stronger structure-aware assistance.",
        },
        "required_information": [
            "Modelica.Fluid medium redeclare conventions",
            "which components in the loop must share the same medium package",
        ],
        "agent_accessible_information": [
            "compiler error excerpt",
            "generated model text",
            "component docs for each fluid class",
        ],
        "agent_missing_information": [
            "cross-component medium consistency policy inside the repair loop",
        ],
        "targeting_recommendation": "exclude",
    },
    "gen_complex_liquid_cooling_loop": {
        "proposed_action_type": "component_api_alignment",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "high",
            "rationale": "The first visible error is still a local Pump API mismatch, but the model also hallucinates non-MSL heat-exchanger classes. A human can repair it, but only with high context load and likely multiple successive interface fixes.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "human_only",
            "high_level_judgment": "human_only",
            "rationale": "Even though the first error is local, the model spans multiple fluid/thermal components and likely contains more hidden incompatibilities. The current loop is unlikely to stabilize it with only local one-shot fixes.",
        },
        "required_information": [
            "Pump component parameter documentation",
            "heat-exchanger and fluid connector docs",
            "overall cooling-loop intent",
        ],
        "agent_accessible_information": [
            "compiler error excerpt",
            "generated model text",
            "retrievable docs",
        ],
        "agent_missing_information": [
            "robust multi-component follow-up strategy",
        ],
        "targeting_recommendation": "exclude",
    },
    "gen_complex_coupled_motor_drive_cooling": {
        "proposed_action_type": "topology_reconstruction",
        "human_full_context_view": {
            "proposed_repairability": "repairable",
            "information_load": "high",
            "rationale": "A human can eventually repair this model, but only by reconciling fluid-medium declarations and re-establishing the missing electrical-mechanical-thermal coupling topology.",
        },
        "agent_realistic_context_view": {
            "proposed_repairability_mode": "human_only",
            "high_level_judgment": "human_only",
            "rationale": "The first visible error is a medium redeclare issue, but the model likely needs broader restructuring. This is beyond the current local repair loop.",
        },
        "required_information": [
            "fluid-medium redeclare conventions",
            "valid coolant-loop component interfaces",
            "intended motor-drive thermal coupling topology",
        ],
        "agent_accessible_information": [
            "compiler error excerpt",
            "generated model text",
            "retrievable library docs",
        ],
        "agent_missing_information": [
            "global structure-edit policy",
            "loop-level topology intent",
        ],
        "targeting_recommendation": "exclude",
    },
}


def _sample_rows(manifest_payload: dict) -> list[dict]:
    rows = manifest_payload.get("samples")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_stage2_diagnosis(
    *,
    sample_manifest_path: str = str(DEFAULT_SAMPLE_MANIFEST_OUT_DIR / "manifest.json"),
    authority_confirmation_status: str = "PENDING_USER_CONFIRMATION",
    out_dir: str = str(DEFAULT_DIAGNOSIS_OUT_DIR),
) -> dict:
    confirmation_status = norm(authority_confirmation_status).upper() or "PENDING_USER_CONFIRMATION"
    sample_manifest = load_json(sample_manifest_path)
    records = []
    missing_templates = []
    for sample in _sample_rows(sample_manifest):
        task_id = norm(sample.get("task_id"))
        draft = DRAFT_DIAGNOSIS.get(task_id)
        if not isinstance(draft, dict):
            missing_templates.append(task_id)
            continue
        record = {
            "task_id": task_id,
            "complexity_tier": norm(sample.get("complexity_tier")),
            "model_name": norm(sample.get("model_name")),
            "proposed_action_type": norm(draft.get("proposed_action_type")),
            "first_failure": dict(sample.get("first_failure") or {}),
            "second_residual": dict(sample.get("second_residual") or {}),
            "repair_action_type": norm(sample.get("repair_action_type")),
            "second_residual_actionability": norm(sample.get("second_residual_actionability")),
            "natural_language_spec": norm(sample.get("natural_language_spec")),
            "source_model_text": norm(sample.get("source_model_text")),
            "one_step_log_excerpt": norm(sample.get("one_step_log_excerpt")),
            "human_full_context_view": {
                **dict(draft.get("human_full_context_view") or {}),
                "authority_confirmation_status": confirmation_status,
            },
            "agent_realistic_context_view": dict(draft.get("agent_realistic_context_view") or {}),
            "required_information": list(draft.get("required_information") or []),
            "agent_accessible_information": list(draft.get("agent_accessible_information") or []),
            "agent_missing_information": list(draft.get("agent_missing_information") or []),
            "targeting_recommendation": norm(draft.get("targeting_recommendation")),
            "provisional_actionability_judgment": norm(((draft.get("agent_realistic_context_view") or {}).get("high_level_judgment"))),
        }
        records.append(record)

    judgment_counts: dict[str, int] = {}
    for row in records:
        key = norm(row.get("provisional_actionability_judgment")) or "unknown"
        judgment_counts[key] = judgment_counts.get(key, 0) + 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if not missing_templates and records else "FAIL",
        "authority_confirmation_status": confirmation_status,
        "sample_manifest_path": str(Path(sample_manifest_path).resolve()) if Path(sample_manifest_path).exists() else str(sample_manifest_path),
        "record_count": len(records),
        "missing_templates": missing_templates,
        "provisional_actionability_counts": judgment_counts,
        "records": records,
    }
    out_root = Path(out_dir)
    write_json(out_root / "records.json", payload)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.18 Stage_2 Diagnosis",
                "",
                f"- status: `{payload.get('status')}`",
                f"- authority_confirmation_status: `{payload.get('authority_confirmation_status')}`",
                f"- record_count: `{payload.get('record_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.18 stage_2 diagnosis draft.")
    parser.add_argument("--sample-manifest", default=str(DEFAULT_SAMPLE_MANIFEST_OUT_DIR / "manifest.json"))
    parser.add_argument("--authority-confirmation-status", default="PENDING_USER_CONFIRMATION")
    parser.add_argument("--out-dir", default=str(DEFAULT_DIAGNOSIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_stage2_diagnosis(
        sample_manifest_path=str(args.sample_manifest),
        authority_confirmation_status=str(args.authority_confirmation_status),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "record_count": payload.get("record_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
