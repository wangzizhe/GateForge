from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_memory_units_v0_34_0"
DEFAULT_SUCCESS_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "library_semantic_migration_probe_v0_33_3_sem19",
    REPO_ROOT / "artifacts" / "library_semantic_migration_probe_v0_33_3_sem19_repeat_run_02",
]

SEMANTIC_MEMORY_UNITS: list[dict[str, Any]] = [
    {
        "unit_id": "arrayed_measurement_flow_ownership",
        "boundary": "arrayed measurement connectors with reusable probe or adapter contracts",
        "failure_symptoms": [
            "OMC alternates between underdetermined flow variables and overdetermined connector equations.",
            "The LLM repeatedly adds local current equations but the connection-set balance remains structurally singular.",
            "The task requires preserving reported measurements and the reusable measurement abstraction.",
        ],
        "transferable_strategy": [
            "Reason about flow ownership at the connection-set level before adding equations.",
            "Treat a non-invasive measurement contract as a semantic contract, not as another physical branch.",
            "Prefer the smallest ownership change that preserves both topology and required readings.",
            "After each candidate, verify the exact submitted model with OMC rather than trusting equation counts alone.",
        ],
        "non_goals": [
            "Do not collapse the measurement abstraction just to balance equations.",
            "Do not add symmetric current constraints by default.",
            "Do not remove required output readings.",
        ],
        "evidence_source": "successful_tool_use_trajectory",
    },
    {
        "unit_id": "standard_library_semantic_substitution",
        "boundary": "custom connector contracts that emulate standard electrical connector semantics",
        "failure_symptoms": [
            "A local connector contract keeps producing structurally singular flow equations.",
            "The required behavior resembles a standard physical-domain network.",
            "The task constraints preserve behavior and topology but do not require the local connector implementation.",
        ],
        "transferable_strategy": [
            "Consider replacing fragile local connector semantics with equivalent standard library component semantics.",
            "Preserve the top-level model identity, required outputs, and physical topology when migrating semantics.",
            "Use standard sources, references, passive elements, and sensors as semantic building blocks when appropriate.",
            "Validate the migrated candidate with check and simulation before submission.",
        ],
        "non_goals": [
            "Do not use library substitution as a default repair.",
            "Do not rename the top-level model.",
            "Do not discard required outputs or topology to make the model easier.",
        ],
        "evidence_source": "successful_tool_use_trajectory",
    },
]


def validate_memory_unit(unit: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["unit_id", "boundary", "failure_symptoms", "transferable_strategy", "non_goals", "evidence_source"]
    for key in required:
        if key not in unit:
            errors.append(f"missing:{key}")
    for key in ["failure_symptoms", "transferable_strategy", "non_goals"]:
        if not isinstance(unit.get(key), list) or not unit.get(key):
            errors.append(f"empty_list:{key}")
    rendered = json.dumps(unit, sort_keys=True).lower()
    forbidden_terms = [
        "sem_",
        "case_id",
        "final model",
        "submit this",
        "replace this line",
        "exact patch",
        "p[1].i = 0",
        "n[1].i = 0",
        "high[1].i = 0",
        "low[1].i = 0",
    ]
    for term in forbidden_terms:
        if term in rendered:
            errors.append(f"forbidden_term:{term}")
    return errors


def _successful_rows(run_dirs: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        for row in load_jsonl(run_dir / "results.jsonl"):
            if row.get("final_verdict") == "PASS" and row.get("submitted"):
                rows.append(
                    {
                        "source_run": run_dir.name,
                        "step_count": int(row.get("step_count") or 0),
                        "token_used": int(row.get("token_used") or 0),
                        "tool_sequence": [
                            call.get("name")
                            for step in row.get("steps", [])
                            if isinstance(step, dict)
                            for call in step.get("tool_calls", [])
                            if isinstance(call, dict)
                        ],
                    }
                )
    return rows


def render_memory_units(units: list[dict[str, Any]] | None = None) -> str:
    active_units = units or SEMANTIC_MEMORY_UNITS
    lines = [
        "# Modelica Semantic Memory Units",
        "",
        "These memory units are transparent external semantic context. They summarize reusable reasoning boundaries from successful trajectories.",
        "They do not include model text, exact equations, a final answer, candidate selection, or auto-submit behavior.",
        "",
    ]
    for unit in active_units:
        lines.extend(
            [
                f"## {unit['unit_id']}",
                "",
                f"- boundary: {unit['boundary']}",
                f"- evidence_source: {unit['evidence_source']}",
                "",
                "Failure symptoms:",
            ]
        )
        lines.extend(f"- {item}" for item in unit["failure_symptoms"])
        lines.append("")
        lines.append("Transferable strategy:")
        lines.extend(f"- {item}" for item in unit["transferable_strategy"])
        lines.append("")
        lines.append("Non-goals:")
        lines.extend(f"- {item}" for item in unit["non_goals"])
        lines.append("")
    lines.extend(
        [
            "## Harness boundary",
            "",
            "- The LLM must still write candidates itself.",
            "- The LLM must still call OMC tools itself.",
            "- The LLM must still call submit_final itself.",
            "- The wrapper must not generate patches, choose candidates, or auto-submit.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_semantic_memory_units(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    units: list[dict[str, Any]] | None = None,
    success_run_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    active_units = units or SEMANTIC_MEMORY_UNITS
    invalid_units = {
        str(unit.get("unit_id") or index): errors
        for index, unit in enumerate(active_units)
        if (errors := validate_memory_unit(unit))
    }
    successful_rows = _successful_rows(success_run_dirs or DEFAULT_SUCCESS_RUN_DIRS)
    context_text = render_memory_units(active_units)
    summary = {
        "version": "v0.34.0",
        "status": "PASS" if active_units and successful_rows and not invalid_units else "REVIEW",
        "analysis_scope": "semantic_memory_units",
        "unit_count": len(active_units),
        "invalid_unit_count": len(invalid_units),
        "invalid_units": invalid_units,
        "successful_trajectory_count": len(successful_rows),
        "successful_trajectory_summaries": successful_rows,
        "context_chars": len(context_text),
        "context_path": str(out_dir / "semantic_memory_units_context.md"),
        "decision": (
            "semantic_memory_units_ready_for_live_probe"
            if active_units and successful_rows and not invalid_units
            else "semantic_memory_units_need_review"
        ),
        "discipline": {
            "model_text_exported": False,
            "exact_patch_exported": False,
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary, context_text=context_text)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], context_text: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "semantic_memory_units_context.md").write_text(context_text, encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
