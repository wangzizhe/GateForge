from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_family_coverage_v0_46_0 import (
    CANDIDATE_FAMILY_TERMS,
    TARGET_CASE_IDS,
    detect_candidate_families,
)
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl
from .agent_modelica_semantic_candidate_failure_audit_v0_45_0 import (
    classify_candidate_failure_mode,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUBSTRATE = REPO_ROOT / "artifacts" / "hard_core_training_substrate_v0_43_0" / "trajectory_records.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "residual_candidate_training_schema_v0_47_0"

OMC_SIGNAL_PATTERNS = (
    ("successful_omc_evidence", ("resultfile = \"/workspace/",)),
    ("empty_simulation_result", ("resultfile = \"\"",)),
    ("simulation_build_failed", ("failed to build model",)),
    ("over_determined", ("too many equations", "over-determined")),
    ("under_determined", ("too few equations", "under-determined")),
    ("index_reduction_failed", ("index reduction",)),
    ("structural_singularity", ("structurally singular", "singular")),
    ("model_check_pass", ("check of", "completed successfully")),
    ("model_check_error", ("translation error", "error:")),
)


def _compact_text(text: str, *, max_chars: int = 1200) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def classify_omc_signal(text: str) -> str:
    lowered = text.lower()
    for signal, terms in OMC_SIGNAL_PATTERNS:
        if signal == "model_check_pass":
            if all(term in lowered for term in terms):
                return signal
            continue
        if any(term in lowered for term in terms):
            return signal
    return "tool_feedback" if text.strip() else "empty_feedback"


def _raw_rows_by_case(substrate_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in substrate_records:
        case_id = str(record.get("case_id") or "")
        result_path = str(record.get("result_path") or "")
        key = (case_id, result_path)
        if not case_id or not result_path or key in seen:
            continue
        seen.add(key)
        for row in load_jsonl(Path(result_path)):
            if str(row.get("case_id") or "") != case_id:
                continue
            if row.get("provider_error") or row.get("final_verdict") == "PASS":
                continue
            rows.append(row)
    return rows


def _tool_result_signals(row: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    for step in row.get("steps") or []:
        for result in step.get("tool_results") or []:
            signals.append(classify_omc_signal(str(result.get("result") or "")))
    return signals


def _candidate_family_sequence(row: dict[str, Any]) -> list[list[str]]:
    sequence: list[list[str]] = []
    for step in row.get("steps") or []:
        step_row = {"steps": [step]}
        families = detect_candidate_families(step_row)
        if families:
            sequence.append(families)
    return sequence


def _candidate_action_count(row: dict[str, Any]) -> int:
    count = 0
    for step in row.get("steps") or []:
        for call in step.get("tool_calls") or []:
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            if str(args.get("model_text") or "").strip():
                count += 1
    return count


def classify_mapping_gap(row: dict[str, Any]) -> str:
    signals = _tool_result_signals(row)
    families = {family for step_families in _candidate_family_sequence(row) for family in step_families}
    failure_mode = classify_candidate_failure_mode(row)
    if "successful_omc_evidence" in signals and not row.get("submitted"):
        return "submit_decision_gap"
    if failure_mode == "compiler_limitation_or_matching_algorithm_belief":
        return "residual_misread_as_compiler_limitation"
    if {"under_determined", "over_determined"} <= set(signals):
        return "delta_overshoot_or_direction_flip"
    if "empty_simulation_result" in signals and len(families) >= 2:
        return "multi_family_balanced_empty_result_stall"
    if "interface_contract_flow_ownership_confusion" == failure_mode:
        return "contract_flow_ownership_mapping_gap"
    return "unresolved_residual_to_candidate_mapping"


def build_residual_candidate_training_examples(
    *,
    substrate_records: list[dict[str, Any]],
    target_case_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    targets = target_case_ids or TARGET_CASE_IDS
    examples: list[dict[str, Any]] = []
    for row in _raw_rows_by_case(substrate_records):
        case_id = str(row.get("case_id") or "")
        if case_id not in targets:
            continue
        signals = _tool_result_signals(row)
        family_sequence = _candidate_family_sequence(row)
        detected_families = sorted({family for step_families in family_sequence for family in step_families})
        examples.append(
            {
                "case_id": case_id,
                "dataset_role": "residual_to_candidate_mapping_training_target",
                "input_contract": {
                    "contains_model_text": False,
                    "contains_reference_solution": False,
                    "contains_hidden_oracle": False,
                    "contains_wrapper_repair": False,
                },
                "residual_signal_sequence": signals,
                "candidate_family_sequence": family_sequence,
                "detected_candidate_families": detected_families,
                "untried_candidate_families": sorted(set(CANDIDATE_FAMILY_TERMS) - set(detected_families)),
                "candidate_action_count": _candidate_action_count(row),
                "final_verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "failure_mode": classify_candidate_failure_mode(row),
                "mapping_gap_label": classify_mapping_gap(row),
                "training_target": (
                    "Teach the Agent to interpret the residual sequence and choose the next semantic candidate "
                    "family. This record is not a reference solution and must not be used as wrapper routing."
                ),
                "trajectory_excerpt": _compact_text("\n".join(str(step.get("text") or "") for step in row.get("steps") or [])),
            }
        )
    return sorted(examples, key=lambda item: item["case_id"])


def build_residual_candidate_training_summary(
    *,
    substrate_records: list[dict[str, Any]],
    version: str = "v0.47.0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    examples = build_residual_candidate_training_examples(substrate_records=substrate_records)
    label_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for example in examples:
        label = str(example["mapping_gap_label"])
        label_counts[label] = label_counts.get(label, 0) + 1
        for family in example["detected_candidate_families"]:
            family_counts[str(family)] = family_counts.get(str(family), 0) + 1
    summary = {
        "version": version,
        "analysis_scope": "residual_candidate_training_schema",
        "status": "PASS" if examples else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "training_example_count": len(examples),
        "case_count": len({str(example["case_id"]) for example in examples}),
        "mapping_gap_label_counts": dict(sorted(label_counts.items())),
        "detected_candidate_family_counts": dict(sorted(family_counts.items())),
        "dataset_contract": {
            "contains_reference_solution": False,
            "contains_hidden_oracle": False,
            "contains_wrapper_repair": False,
            "live_runner_integration": False,
            "purpose": "offline_training_target_design",
        },
        "decision": "use_as_training_schema_not_live_repair_logic",
        "scope_note": (
            "This artifact converts failed trajectories into residual-to-candidate mapping targets. It does not "
            "generate patches, select candidates, route cases, submit, or prove an ability improvement."
        ),
    }
    return summary, examples


def write_residual_candidate_training_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    examples: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "training_examples.jsonl").open("w", encoding="utf-8") as fh:
        for example in examples:
            fh.write(json.dumps(example, sort_keys=True) + "\n")


def run_residual_candidate_training_schema(
    *,
    substrate_path: Path = DEFAULT_SUBSTRATE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, examples = build_residual_candidate_training_summary(
        substrate_records=load_jsonl(substrate_path),
    )
    write_residual_candidate_training_outputs(out_dir=out_dir, summary=summary, examples=examples)
    return summary
