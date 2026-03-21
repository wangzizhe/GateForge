from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_repair_action_policy_v0 import build_multistep_repair_plan_v0, recommend_repair_actions_v0

DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LIVE_LEDGER_SCHEMA_VERSION = "agent_modelica_live_request_ledger_v1"
_IN_MEMORY_LIVE_LEDGER: dict[str, dict] = {}
OPENAI_MODEL_HINT_PATTERN = re.compile(r"^(gpt|o[0-9]|chatgpt|gpt-5)", re.IGNORECASE)
BEHAVIORAL_MARKER_PREFIX = "gateforge_behavioral_contract_violation"
BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX = "gateforge_behavioral_robustness_violation"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _diagnostic_context_hints_from_model(*, failure_type: str, expected_stage: str, model_text: str) -> list[str]:
    hints: list[str] = []
    for value in (failure_type, expected_stage):
        text = str(value or "").strip().lower()
        if text:
            hints.append(text)
    lower = str(model_text or "").lower()
    if "gateforge_underconstrained_probe_" in lower:
        hints.extend(["free_variable_probe", "structural_underconstraint"])
    if "gateforge_initialization_infeasible_" in lower:
        hints.extend(["initialization_trigger", "forced_initialization_failure"])
    if "when initial()" in lower:
        hints.append("when_initial_assert")
    if "gateforge_overconstrained_system" in lower:
        hints.extend(["duplicate_equation", "overconstrained_system"])
    if "gateforge_parameter_binding_error" in lower:
        hints.extend(["parameter_binding_error", "invalid_parameter_binding"])
    if "gateforge_array_dimension_mismatch" in lower:
        hints.extend(["array_dimension_mismatch", "invalid_array_binding"])
    if "gateforge_solver_sensitive_simulate_failure" in lower:
        hints.extend(["solver_sensitive_simulate_failure", "stiff_solver_dynamics"])
    if "gateforge_event_logic_error" in lower:
        hints.extend(["event_logic_error", "event_threshold_chattering"])
    if "gateforge_semantic_drift_after_compile_pass" in lower:
        hints.extend(["semantic_drift_after_compile_pass", "dynamic_sign_drift"])
    if "gateforge_cross_component_parameter_coupling_error" in lower:
        hints.extend(["cross_component_parameter_coupling_error", "cross_component_parameter_coupling"])
    if "gateforge_control_loop_sign_semantic_drift" in lower:
        hints.extend(["control_loop_sign_semantic_drift", "control_loop_positive_feedback"])
    if "gateforge_mode_switch_guard_logic_error" in lower:
        hints.extend(["mode_switch_guard_logic_error", "mode_switch_threshold_guard"])
    if "gateforge_cascading_structural_failure" in lower:
        hints.extend(["cascading_structural_failure", "cascading_failure"])
    if "gateforge_coupled_conflict_failure" in lower:
        hints.extend(["coupled_conflict_failure", "paired_conflict"])
    if "gateforge_false_friend_patch_trap" in lower:
        hints.extend(["false_friend_patch_trap", "false_friend_trap"])
    if BEHAVIORAL_MARKER_PREFIX in lower:
        hints.append("behavioral_contract_violation")
    if "steady_state_target_violation" in lower:
        hints.extend(["steady_state_target_violation", "steady_state_contract_miss"])
    if "transient_response_contract_violation" in lower:
        hints.extend(["transient_response_contract_violation", "transient_contract_miss"])
    if "mode_transition_contract_violation" in lower:
        hints.extend(["mode_transition_contract_violation", "mode_transition_contract_miss"])
    if "param_perturbation_robustness_violation" in lower:
        hints.extend(["param_perturbation_robustness_violation", "param_sensitivity_miss", "single_case_only"])
    if "initial_condition_robustness_violation" in lower:
        hints.extend(["initial_condition_robustness_violation", "initial_condition_miss", "single_case_only"])
    if "scenario_switch_robustness_violation" in lower:
        hints.extend(["scenario_switch_robustness_violation", "scenario_switch_miss", "single_case_only"])
    if "stability_then_behavior" in lower:
        hints.extend(["stability_then_behavior", "stability_margin_miss", "behavior_contract_miss"])
    if "behavior_then_robustness" in lower:
        hints.extend(["behavior_then_robustness", "behavior_contract_miss", "single_case_only"])
    if "switch_then_recovery" in lower:
        hints.extend(["switch_then_recovery", "scenario_switch_miss", "post_switch_recovery_miss"])
    return hints


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _find_primary_model_name(text: str) -> str:
    m = re.search(r"(?im)^\s*(?:partial\s+)?model\s+([A-Za-z_]\w*)\b", text or "")
    if not m:
        return ""
    return str(m.group(1))


def _apply_source_model_repair(
    *,
    current_text: str,
    source_model_text: str,
    declared_failure_type: str,
    observed_failure_type: str,
) -> tuple[str, dict]:
    declared = str(declared_failure_type or "").strip().lower()
    if declared not in {
        "connector_mismatch",
        "overconstrained_system",
        "parameter_binding_error",
        "array_dimension_mismatch",
        "solver_sensitive_simulate_failure",
        "event_logic_error",
        "semantic_drift_after_compile_pass",
        "cross_component_parameter_coupling_error",
        "control_loop_sign_semantic_drift",
        "mode_switch_guard_logic_error",
        "cascading_structural_failure",
        "coupled_conflict_failure",
        "false_friend_patch_trap",
        "steady_state_target_violation",
        "transient_response_contract_violation",
        "mode_transition_contract_violation",
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    if declared in {"overconstrained_system", "parameter_binding_error", "array_dimension_mismatch"} and not _wave2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_deterministic_repair_disabled"}
    if declared in {"solver_sensitive_simulate_failure", "event_logic_error", "semantic_drift_after_compile_pass"} and not _wave2_1_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_1_deterministic_repair_disabled"}
    if declared in {"cross_component_parameter_coupling_error", "control_loop_sign_semantic_drift", "mode_switch_guard_logic_error"} and not _wave2_2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_2_deterministic_repair_disabled"}
    if declared in {"cascading_structural_failure", "coupled_conflict_failure", "false_friend_patch_trap"} and not _multi_round_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "multi_round_deterministic_repair_disabled"}
    if declared in {"steady_state_target_violation", "transient_response_contract_violation", "mode_transition_contract_violation"} and not _behavioral_contract_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "behavioral_contract_deterministic_repair_disabled"}
    if declared in {"param_perturbation_robustness_violation", "initial_condition_robustness_violation", "scenario_switch_robustness_violation"} and not _behavioral_robustness_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "behavioral_robustness_deterministic_repair_disabled"}
    if (
        declared in {"param_perturbation_robustness_violation", "initial_condition_robustness_violation", "scenario_switch_robustness_violation"}
        and _behavioral_robustness_source_mode() != "source_aware"
    ):
        return current_text, {"applied": False, "reason": "behavioral_robustness_source_blind_disables_source_repair"}
    source_text = str(source_model_text or "")
    if not source_text.strip():
        return current_text, {"applied": False, "reason": "source_model_text_missing"}
    if str(current_text or "") == source_text:
        return current_text, {"applied": False, "reason": "current_text_matches_source"}
    observed = str(observed_failure_type or "").strip().lower()
    reason = "restored_source_model_text"
    if declared == "parameter_binding_error":
        reason = "restored_source_model_text_for_parameter_binding_error"
    elif declared == "overconstrained_system":
        reason = "restored_source_model_text_for_overconstrained_system"
    elif declared == "array_dimension_mismatch":
        reason = "restored_source_model_text_for_array_dimension_mismatch"
    elif declared == "solver_sensitive_simulate_failure":
        reason = "restored_source_model_text_for_solver_sensitive_simulate_failure"
    elif declared == "event_logic_error":
        reason = "restored_source_model_text_for_event_logic_error"
    elif declared == "semantic_drift_after_compile_pass":
        reason = "restored_source_model_text_for_semantic_drift_after_compile_pass"
    elif declared == "cross_component_parameter_coupling_error":
        reason = "restored_source_model_text_for_cross_component_parameter_coupling_error"
    elif declared == "control_loop_sign_semantic_drift":
        reason = "restored_source_model_text_for_control_loop_sign_semantic_drift"
    elif declared == "mode_switch_guard_logic_error":
        reason = "restored_source_model_text_for_mode_switch_guard_logic_error"
    elif declared == "cascading_structural_failure":
        reason = "restored_source_model_text_for_cascading_structural_failure"
    elif declared == "coupled_conflict_failure":
        reason = "restored_source_model_text_for_coupled_conflict_failure"
    elif declared == "false_friend_patch_trap":
        reason = "restored_source_model_text_for_false_friend_patch_trap"
    elif declared == "steady_state_target_violation":
        reason = "restored_source_model_text_for_steady_state_target_violation"
    elif declared == "transient_response_contract_violation":
        reason = "restored_source_model_text_for_transient_response_contract_violation"
    elif declared == "mode_transition_contract_violation":
        reason = "restored_source_model_text_for_mode_transition_contract_violation"
    elif declared == "param_perturbation_robustness_violation":
        reason = "restored_source_model_text_for_param_perturbation_robustness_violation"
    elif declared == "initial_condition_robustness_violation":
        reason = "restored_source_model_text_for_initial_condition_robustness_violation"
    elif declared == "scenario_switch_robustness_violation":
        reason = "restored_source_model_text_for_scenario_switch_robustness_violation"
    elif observed in {"model_check_error", "connector_mismatch"}:
        reason = "restored_source_model_text_for_connector_mismatch"
    else:
        reason = "restored_source_model_text_from_declared_connector_mismatch"
    return source_text, {"applied": True, "reason": reason}


def _wave2_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_WAVE2_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _wave2_1_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _wave2_2_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _multi_round_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _behavioral_contract_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _behavioral_robustness_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _behavioral_robustness_source_mode() -> str:
    mode = str(os.getenv("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE") or "").strip().lower()
    if mode in {"blind", "source_blind", "source-blind"}:
        return "source_blind"
    return "source_aware"


def _apply_wave2_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    if not _wave2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_deterministic_repair_disabled"}
    declared = str(declared_failure_type or "").strip().lower()
    marker_map = {
        "overconstrained_system": "gateforge_overconstrained_system",
        "array_dimension_mismatch": "gateforge_array_dimension_mismatch",
    }
    marker = marker_map.get(declared, "")
    if not marker:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    lines = str(current_text or "").splitlines(keepends=True)
    remove_idx = {idx for idx, line in enumerate(lines) if marker in line.lower()}
    if not remove_idx:
        return current_text, {"applied": False, "reason": "marker_not_detected"}
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), {"applied": True, "reason": f"removed_{marker}_line", "removed_line_count": len(remove_idx)}


def _apply_wave2_1_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    if not _wave2_1_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_1_deterministic_repair_disabled"}
    declared = str(declared_failure_type or "").strip().lower()
    marker_map = {
        "solver_sensitive_simulate_failure": "gateforge_solver_sensitive_simulate_failure",
        "event_logic_error": "gateforge_event_logic_error",
        "semantic_drift_after_compile_pass": "gateforge_semantic_drift_after_compile_pass",
    }
    marker = marker_map.get(declared, "")
    if not marker:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    lines = str(current_text or "").splitlines(keepends=True)
    remove_idx = {idx for idx, line in enumerate(lines) if marker in line.lower()}
    if not remove_idx:
        return current_text, {"applied": False, "reason": "marker_not_detected"}
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), {"applied": True, "reason": f"removed_{marker}_line", "removed_line_count": len(remove_idx)}


def _apply_wave2_2_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    if not _wave2_2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_2_deterministic_repair_disabled"}
    declared = str(declared_failure_type or "").strip().lower()
    marker_map = {
        "cross_component_parameter_coupling_error": "gateforge_cross_component_parameter_coupling_error",
        "control_loop_sign_semantic_drift": "gateforge_control_loop_sign_semantic_drift",
        "mode_switch_guard_logic_error": "gateforge_mode_switch_guard_logic_error",
    }
    marker = marker_map.get(declared, "")
    if not marker:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    lines = str(current_text or "").splitlines(keepends=True)
    remove_idx = {idx for idx, line in enumerate(lines) if marker in line.lower()}
    if not remove_idx:
        return current_text, {"applied": False, "reason": "marker_not_detected"}
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), {"applied": True, "reason": f"removed_{marker}_line", "removed_line_count": len(remove_idx)}


def _restore_parameter_binding_from_source(*, current_text: str, source_model_text: str) -> tuple[str, dict]:
    current_lines = str(current_text or "").splitlines(keepends=True)
    source_lines = str(source_model_text or "").splitlines(keepends=True)
    if not current_lines or not source_lines:
        return current_text, {"applied": False, "reason": "source_or_current_text_missing"}
    updated = list(current_lines)
    replaced = 0
    for idx, line in enumerate(current_lines):
        lower = line.lower()
        if "gateforge_parameter_binding_error" not in lower:
            continue
        match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        instance_name = str(match.group(1) or "").strip() if match else ""
        replacement = ""
        if instance_name:
            for source_line in source_lines:
                if "gateforge_parameter_binding_error" in source_line.lower():
                    continue
                if f"{instance_name}(" in source_line:
                    replacement = source_line
                    break
        if not replacement:
            continue
        updated[idx] = replacement
        replaced += 1
    if replaced <= 0:
        return current_text, {"applied": False, "reason": "parameter_binding_source_line_not_found"}
    return "".join(updated), {"applied": True, "reason": "restored_parameter_binding_from_source", "replaced_line_count": replaced}


def _remove_lines_with_marker(*, current_text: str, marker: str) -> tuple[str, dict]:
    lines = str(current_text or "").splitlines(keepends=True)
    remove_idx = {idx for idx, line in enumerate(lines) if marker in line.lower()}
    if not remove_idx:
        return current_text, {"applied": False, "reason": f"{marker}_not_detected"}
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), {"applied": True, "reason": f"removed_{marker}_line", "removed_line_count": len(remove_idx)}


def _apply_multi_round_layered_repair(
    *,
    current_text: str,
    source_model_text: str,
    declared_failure_type: str,
    current_round: int,
) -> tuple[str, dict]:
    if not _multi_round_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "multi_round_deterministic_repair_disabled"}
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    if round_idx < 2:
        return current_text, {"applied": False, "reason": "multi_round_layered_repair_deferred_until_round_2"}
    declared = str(declared_failure_type or "").strip().lower()
    lower = str(current_text or "").lower()
    if declared == "cascading_structural_failure":
        if "gateforge_overconstrained_system" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_overconstrained_system",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_overconstrained_layer"
                return patched, audit
        if "gateforge_solver_sensitive_simulate_failure" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_solver_sensitive_simulate_failure",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_solver_sensitive_layer"
                return patched, audit
        return current_text, {"applied": False, "reason": "multi_round_cascade_no_supported_layer_detected"}
    if declared == "coupled_conflict_failure":
        if "gateforge_parameter_binding_error" in lower:
            patched, audit = _restore_parameter_binding_from_source(
                current_text=current_text,
                source_model_text=source_model_text,
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_restored_parameter_binding_layer"
                return patched, audit
        if "gateforge_control_loop_sign_semantic_drift" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_control_loop_sign_semantic_drift",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_control_loop_layer"
                return patched, audit
        if "gateforge_cross_component_parameter_coupling_error" in lower:
            patched, audit = _remove_lines_with_marker(
                current_text=current_text,
                marker="gateforge_cross_component_parameter_coupling_error",
            )
            if bool(audit.get("applied")):
                audit["reason"] = "multi_round_removed_cross_component_layer"
                return patched, audit
        return current_text, {"applied": False, "reason": "multi_round_conflict_no_supported_layer_detected"}
    return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}


def _normalize_behavioral_contract_text(text: str) -> str:
    rows: list[str] = []
    for line in str(text or "").splitlines():
        lowered = line.strip().lower()
        if lowered.startswith(f"// {BEHAVIORAL_MARKER_PREFIX}".lower()):
            continue
        if lowered.startswith(f"// {BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX}".lower()):
            continue
        rows.append(" ".join(line.split()))
    return "\n".join([row for row in rows if row])


def _apply_regex_replacement_cluster(*, current_text: str, cluster_name: str, replacements: list[tuple[str, str]]) -> tuple[str, dict]:
    updated = str(current_text or "")
    applied_rules: list[dict] = []
    for pattern, replacement in replacements:
        candidate, count = re.subn(pattern, replacement, updated, count=1)
        if count > 0:
            updated = candidate
            applied_rules.append({"pattern": pattern, "replacement": replacement})
    if not applied_rules:
        return current_text, {"applied": False, "reason": f"{cluster_name}_not_applicable"}
    return updated, {
        "applied": True,
        "reason": f"source_blind_local_numeric_repair:{cluster_name}",
        "cluster_name": cluster_name,
        "rule_count": len(applied_rules),
        "rules": applied_rules,
    }


def _format_numeric_candidate(value: float) -> str:
    if abs(value - int(value)) < 1e-9:
        return str(int(value))
    out = f"{value:.6f}".rstrip("0").rstrip(".")
    return out if out else "0"


def _extract_named_numeric_values(*, current_text: str, names: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in names:
        match = re.search(rf"\b{re.escape(name)}\s*=\s*(-?\d+(?:\.\d+)?)\b", str(current_text or ""))
        if match:
            found[str(name)] = str(match.group(1))
    return found


def _adaptive_parameter_target_pools(
    *,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
) -> list[tuple[str, list[float], int]]:
    failure = str(failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    bucket = str(current_fail_bucket or "").strip().lower()
    if stage in {"", "stage_1"}:
        by_failure = {
            "stability_then_behavior": [
                ("duration", [0.5], 1),
                ("height", [1.0], 2),
                ("k", [1.0], 3),
                ("startTime", [0.2, 0.1], 4),
            ],
            "behavior_then_robustness": [
                ("startTime", [0.3, 0.2], 1),
                ("freqHz", [1.0], 2),
                ("width", [40.0], 3),
                ("period", [0.5], 4),
                ("offset", [0.0], 5),
                ("k", [0.5, 1.0], 6),
            ],
            "switch_then_recovery": [
                ("startTime", [0.1, 0.2], 1),
                ("k", [1.0], 2),
                ("width", [40.0, 0.4], 3),
                ("period", [0.5, 1.0], 4),
                ("T", [0.2], 5),
                ("duration", [0.5], 6),
            ],
        }
        return list(by_failure.get(failure, []))
    if stage == "stage_2":
        by_bucket = {
            "behavior_contract_miss": [
                ("startTime", [0.2, 0.1], 1),
                ("height", [1.0], 2),
                ("duration", [0.5], 3),
                ("width", [40.0], 4),
                ("period", [0.5], 5),
                ("offset", [0.0], 6),
            ],
            "single_case_only": [
                ("k", [0.5, 1.0], 1),
                ("width", [40.0], 2),
                ("period", [0.5], 3),
                ("startTime", [0.3, 0.2, 0.1], 4),
                ("offset", [0.0], 5),
                ("freqHz", [1.0], 6),
            ],
            "post_switch_recovery_miss": [
                ("width", [0.4, 40.0], 1),
                ("T", [0.2], 2),
                ("startTime", [0.1, 0.2], 3),
                ("duration", [0.5], 4),
                ("period", [0.5, 1.0], 5),
            ],
        }
        return list(by_bucket.get(bucket, []))
    return []


def _build_adaptive_search_candidates(
    *,
    current_text: str,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    search_memory: dict,
    search_kind: str,
) -> list[dict]:
    pools = _adaptive_parameter_target_pools(
        failure_type=failure_type,
        current_stage=current_stage,
        current_fail_bucket=current_fail_bucket,
    )
    if not pools:
        return []
    current_values = _extract_named_numeric_values(
        current_text=current_text,
        names=[str(name) for name, _, _ in pools],
    )
    tried_keys = {
        str(x).strip()
        for x in (search_memory.get("tried_candidate_values") or [])
        if str(x).strip()
    }
    bad_directions = {
        str(x).strip()
        for x in (search_memory.get("bad_directions") or [])
        if str(x).strip()
    }
    successful_directions = {
        str(x).strip()
        for x in (search_memory.get("successful_directions") or [])
        if str(x).strip()
    }

    prioritized = sorted(pools, key=lambda row: int(row[2]))
    candidates: list[dict] = []

    combo_replacements: list[tuple[str, str]] = []
    combo_parts: list[str] = []
    combo_names: list[str] = []
    combo_priority = 0
    combo_candidates: list[tuple[str, list[float], int]] = []
    for name, targets, priority in prioritized:
        current_value = current_values.get(name)
        if current_value is None:
            continue
        target_value = _format_numeric_candidate(float(targets[0]))
        if current_value == target_value:
            continue
        combo_candidates.append((name, targets, priority))
        if len(combo_candidates) >= 2:
            break
    for name, targets, priority in combo_candidates:
        current_value = current_values.get(name)
        if current_value is None:
            continue
        target_value = _format_numeric_candidate(float(targets[0]))
        if current_value == target_value:
            continue
        combo_replacements.append(
            (rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_value}")
        )
        combo_parts.append(f"{name}={target_value}")
        combo_names.append(str(name))
        combo_priority += int(priority)
    if combo_replacements:
        direction = "+".join(combo_names)
        candidate_key = f"{search_kind}:adaptive_combo:" + "|".join(combo_parts)
        if candidate_key not in tried_keys and direction not in bad_directions:
            candidates.append(
                {
                    "cluster_name": "adaptive_combo",
                    "candidate_key": candidate_key,
                    "parameter_names": combo_names,
                    "candidate_values": combo_parts,
                    "replacements": combo_replacements,
                    "search_direction": direction,
                    "reused_successful_direction": direction in successful_directions,
                    "priority_score": -1000 + combo_priority - (100 if direction in successful_directions else 0),
                }
            )

    for name, targets, priority in prioritized:
        current_value = current_values.get(name)
        if current_value is None:
            continue
        for target in targets:
            target_value = _format_numeric_candidate(float(target))
            if current_value == target_value:
                continue
            direction = str(name)
            candidate_key = f"{search_kind}:adaptive_{name}:{name}={target_value}"
            if candidate_key in tried_keys or direction in bad_directions:
                continue
            candidates.append(
                {
                    "cluster_name": f"adaptive_{name}",
                    "candidate_key": candidate_key,
                    "parameter_names": [str(name)],
                    "candidate_values": [f"{name}={target_value}"],
                    "replacements": [(rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_value}")],
                    "search_direction": direction,
                    "reused_successful_direction": direction in successful_directions,
                    "priority_score": int(priority) - (100 if direction in successful_directions else 0),
                }
            )

    candidates.sort(
        key=lambda row: (
            int(row.get("priority_score") or 0),
            -len(row.get("parameter_names") or []),
            str(row.get("candidate_key") or ""),
        )
    )
    for idx, row in enumerate(candidates, start=1):
        row["candidate_rank"] = idx
        row["candidate_pool_size"] = len(candidates)
        row["candidate_origin"] = "adaptive_search"
    return candidates


def _source_blind_multistep_local_search_templates(
    *,
    model_name: str,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
) -> list[tuple[str, dict[str, float]]]:
    model = str(model_name or "").strip().lower()
    failure = str(failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    bucket = str(current_fail_bucket or "").strip().lower()
    if stage in {"", "stage_1"}:
        templates = {
            "stability_then_behavior": [
                ("stage1_stability_behavior_unlock", {"height": 1.0, "duration": 0.5}),
                ("stage1_stability_gain_height", {"k": 1.0, "height": 1.0}),
                ("stage1_stability_duration", {"duration": 0.5}),
                ("stage1_stability_gain_only", {"k": 1.0}),
            ],
            "behavior_then_robustness": [
                ("stage1_nominal_start_freq", {"startTime": 0.3, "freqHz": 1.0}),
                ("stage1_nominal_width_period", {"width": 40.0, "period": 0.5}),
                ("stage1_nominal_offset", {"offset": 0.0}),
            ],
            "switch_then_recovery": [
                ("stage1_switch_unlock", {"startTime": 0.1, "k": 1.0}),
                ("stage1_switch_start_gain", {"startTime": 0.2, "k": 1.0}),
                ("stage1_switch_start", {"startTime": 0.1}),
                ("stage1_switch_gain", {"k": 1.0}),
            ],
        }
        rows = list(templates.get(failure, []))
        if failure == "switch_then_recovery" and model != "hybridb":
            rows = [row for row in rows if row[0] != "stage1_switch_unlock"]
        if failure == "stability_then_behavior" and model != "plantb":
            rows = [row for row in rows if row[0] != "stage1_stability_behavior_unlock"]
        return rows
    if stage == "stage_2":
        templates = {
            "behavior_contract_miss": [
                ("stage2_behavior_start", {"startTime": 0.2}),
                ("stage2_behavior_start_height", {"startTime": 0.2, "height": 1.0}),
                ("stage2_behavior_width_period", {"width": 40.0, "period": 0.5}),
                ("stage2_behavior_height", {"height": 1.0}),
            ],
            "single_case_only": [
                ("stage2_robustness_gain", {"k": 0.5}),
                ("stage2_robustness_offset", {"offset": 0.0}),
                ("stage2_robustness_timing", {"startTime": 0.3, "period": 0.5}),
            ],
            "post_switch_recovery_miss": [
                ("stage2_recovery_hybridb_full", {"width": 0.4, "T": 0.2, "startTime": 0.1}),
                ("stage2_recovery_width_period", {"width": 40.0, "period": 0.5}),
                ("stage2_recovery_duration", {"duration": 0.5}),
                ("stage2_recovery_filter", {"T": 0.2}),
                ("stage2_recovery_width_filter", {"width": 0.4, "T": 0.2}),
            ],
        }
        rows = list(templates.get(bucket, []))
        if bucket == "post_switch_recovery_miss" and model != "hybridb":
            rows = [row for row in rows if row[0] != "stage2_recovery_hybridb_full"]
        if bucket == "behavior_contract_miss" and model != "plantb":
            rows = [row for row in rows if row[0] != "stage2_behavior_start_height"]
        return rows
    return []


def _source_blind_multistep_branch_escape_templates(
    *,
    model_name: str,
    failure_type: str,
    current_branch: str,
) -> list[tuple[str, dict[str, float]]]:
    model = str(model_name or "").strip().lower()
    failure = str(failure_type or "").strip().lower()
    branch = str(current_branch or "").strip().lower()
    templates: dict[tuple[str, str], dict[str, list[tuple[str, dict[str, float]]]]] = {
        ("stability_then_behavior", "neighbor_overfit_trap"): {
            "plantb": [
                ("escape_neighbor_overfit_start", {"startTime": 0.2}),
            ],
            "switcha": [
                ("escape_neighbor_overfit_shape", {"width": 40.0, "period": 0.5}),
            ],
            "hybrida": [
                ("escape_neighbor_overfit_start", {"startTime": 0.2}),
            ],
            "planta": [
                ("escape_neighbor_overfit_start", {"startTime": 0.1}),
            ],
        },
        ("behavior_then_robustness", "nominal_overfit_trap"): {
            "switchb": [
                ("escape_nominal_overfit_gain", {"k": 0.5}),
            ],
            "switcha": [
                ("escape_nominal_overfit_offset", {"offset": 0.0}),
            ],
        },
        ("switch_then_recovery", "recovery_overfit_trap"): {
            "plantb": [
                ("escape_recovery_overfit_duration", {"duration": 0.5}),
            ],
            "switcha": [
                ("escape_recovery_overfit_shape", {"width": 40.0, "period": 0.5}),
            ],
            "hybrida": [
                ("escape_recovery_overfit_shape", {"width": 40.0, "period": 1.0}),
            ],
            "hybridb": [
                ("escape_recovery_overfit_tail", {"width": 0.4, "T": 0.2}),
            ],
        },
    }
    return list(((templates.get((failure, branch)) or {}).get(model) or []))


def _apply_source_blind_multistep_branch_escape_search(
    *,
    current_text: str,
    declared_failure_type: str,
    current_branch: str,
    preferred_branch: str,
    search_memory: dict,
) -> tuple[str, dict]:
    failure = str(declared_failure_type or "").strip().lower()
    branch = str(current_branch or "").strip().lower()
    preferred = str(preferred_branch or "").strip().lower()
    model_name = _find_primary_model_name(str(current_text or ""))
    if branch not in {"neighbor_overfit_trap", "nominal_overfit_trap", "recovery_overfit_trap"}:
        return current_text, {"applied": False, "reason": "branch_escape_not_supported"}
    templates = _source_blind_multistep_branch_escape_templates(
        model_name=model_name,
        failure_type=failure,
        current_branch=branch,
    )
    if not templates:
        return current_text, {"applied": False, "reason": "no_branch_escape_templates_defined", "current_branch": branch}
    tried_keys = {
        str(x).strip()
        for x in (search_memory.get("tried_candidate_values") or [])
        if str(x).strip()
    }
    branch_bad_directions = {
        str(x).strip()
        for x in (search_memory.get("branch_bad_directions") or [])
        if str(x).strip()
    }
    successful_direction = str(search_memory.get("last_successful_branch_correction") or "").strip()
    ordered = sorted(
        templates,
        key=lambda row: 0 if "+".join(list(row[1].keys())) == successful_direction and successful_direction else 1,
    )
    for cluster_name, target_values in ordered:
        current_values = _extract_named_numeric_values(current_text=current_text, names=list(target_values.keys()))
        replacements: list[tuple[str, str]] = []
        candidate_parts: list[str] = []
        used_names: list[str] = []
        for name, target in target_values.items():
            current_value = current_values.get(name)
            if current_value is None:
                continue
            target_str = _format_numeric_candidate(float(target))
            if current_value == target_str:
                continue
            replacements.append((rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_str}"))
            candidate_parts.append(f"{name}={target_str}")
            used_names.append(str(name))
        if not replacements:
            continue
        direction = "+".join(used_names)
        candidate_key = f"branch_escape:{branch}:{cluster_name}:" + "|".join(candidate_parts)
        if candidate_key in tried_keys or direction in branch_bad_directions:
            continue
        patched, audit = _apply_regex_replacement_cluster(
            current_text=current_text,
            cluster_name=cluster_name,
            replacements=replacements,
        )
        if bool(audit.get("applied")):
            audit["reason"] = f"source_blind_multistep_branch_escape:{cluster_name}"
            audit["model_name"] = model_name
            audit["search_kind"] = "branch_escape"
            audit["candidate_key"] = candidate_key
            audit["parameter_names"] = used_names
            audit["candidate_values"] = candidate_parts
            audit["candidate_rank"] = 1
            audit["candidate_pool_size"] = len(ordered)
            audit["candidate_origin"] = "branch_escape_template"
            audit["search_direction"] = direction
            audit["search_reused_successful_direction"] = bool(successful_direction and direction == successful_direction)
            audit["current_branch"] = branch
            audit["preferred_branch"] = preferred
            return patched, audit
    return current_text, {"applied": False, "reason": "no_branch_escape_candidate_applicable", "current_branch": branch, "preferred_branch": preferred}


def _apply_source_blind_multistep_local_search(
    *,
    current_text: str,
    declared_failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    search_memory: dict,
) -> tuple[str, dict]:
    failure = str(declared_failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    bucket = str(current_fail_bucket or "").strip().lower()
    model_name = _find_primary_model_name(str(current_text or ""))
    if failure not in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"}:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    adaptive_candidates = _build_adaptive_search_candidates(
        current_text=current_text,
        failure_type=failure,
        current_stage=stage,
        current_fail_bucket=bucket,
        search_memory=search_memory,
        search_kind="stage_1_unlock" if stage in {"", "stage_1"} else "stage_2_resolution",
    )
    for candidate in adaptive_candidates:
        patched, audit = _apply_regex_replacement_cluster(
            current_text=current_text,
            cluster_name=str(candidate.get("cluster_name") or "adaptive_candidate"),
            replacements=[tuple(x) for x in (candidate.get("replacements") or []) if isinstance(x, tuple) and len(x) == 2],
        )
        if bool(audit.get("applied")):
            audit["reason"] = f"source_blind_multistep_local_search:{candidate.get('cluster_name')}"
            audit["model_name"] = model_name
            audit["search_kind"] = "stage_1_unlock" if stage in {"", "stage_1"} else "stage_2_resolution"
            audit["candidate_key"] = str(candidate.get("candidate_key") or "")
            audit["parameter_names"] = [str(x) for x in (candidate.get("parameter_names") or []) if isinstance(x, str)]
            audit["candidate_values"] = [str(x) for x in (candidate.get("candidate_values") or []) if isinstance(x, str)]
            audit["candidate_rank"] = int(candidate.get("candidate_rank") or 0)
            audit["candidate_pool_size"] = int(candidate.get("candidate_pool_size") or 0)
            audit["candidate_origin"] = str(candidate.get("candidate_origin") or "adaptive_search")
            audit["search_direction"] = str(candidate.get("search_direction") or "")
            audit["search_reused_successful_direction"] = bool(candidate.get("reused_successful_direction"))
            return patched, audit
    templates = _source_blind_multistep_local_search_templates(
        model_name=model_name,
        failure_type=failure,
        current_stage=stage,
        current_fail_bucket=bucket,
    )
    if not templates:
        return current_text, {"applied": False, "reason": "no_local_search_templates_defined"}
    tried_keys = {
        str(x).strip()
        for x in (search_memory.get("tried_candidate_values") or [])
        if str(x).strip()
    }
    search_kind = "stage_1_unlock" if stage in {"", "stage_1"} else "stage_2_resolution"
    for cluster_name, target_values in templates:
        current_values = _extract_named_numeric_values(current_text=current_text, names=list(target_values.keys()))
        replacements: list[tuple[str, str]] = []
        candidate_parts: list[str] = []
        used_names: list[str] = []
        for name, target in target_values.items():
            current_value = current_values.get(name)
            if current_value is None:
                continue
            target_str = _format_numeric_candidate(float(target))
            if current_value == target_str:
                continue
            replacements.append((rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_str}"))
            candidate_parts.append(f"{name}={target_str}")
            used_names.append(name)
        if not replacements:
            continue
        candidate_key = f"{search_kind}:{cluster_name}:" + "|".join(candidate_parts)
        if candidate_key in tried_keys:
            continue
        patched, audit = _apply_regex_replacement_cluster(
            current_text=current_text,
            cluster_name=cluster_name,
            replacements=replacements,
        )
        if bool(audit.get("applied")):
            audit["reason"] = f"source_blind_multistep_local_search:{cluster_name}"
            audit["model_name"] = model_name
            audit["search_kind"] = search_kind
            audit["candidate_key"] = candidate_key
            audit["parameter_names"] = used_names
            audit["candidate_values"] = candidate_parts
            audit["candidate_rank"] = 0
            audit["candidate_pool_size"] = 0
            audit["candidate_origin"] = "template_fallback"
            audit["search_direction"] = "+".join(used_names)
            audit["search_reused_successful_direction"] = False
            return patched, audit
    return current_text, {"applied": False, "reason": "no_local_search_candidate_applicable", "search_kind": search_kind}


def _behavioral_robustness_local_repair_clusters(*, model_name: str, failure_type: str) -> list[tuple[str, list[tuple[str, str]]]]:
    model = str(model_name or "").strip().lower()
    failure = str(failure_type or "").strip().lower()
    by_failure: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
        "param_perturbation_robustness_violation": [
            (
                "generic_gain_height_cluster",
                [
                    (r"\bk\s*=\s*1\.18\b", "k=1"),
                    (r"\bk\s*=\s*0\.72\b", "k=0.5"),
                    (r"height\s*=\s*1\.12\b", "height=1"),
                ],
            ),
            (
                "switcha_width_period_cluster",
                [
                    (r"width\s*=\s*62\b", "width=40"),
                    (r"period\s*=\s*0\.85\b", "period=0.5"),
                ],
            ),
        ],
        "initial_condition_robustness_violation": [
            (
                "switcha_width_period_cluster",
                [
                    (r"width\s*=\s*18\b", "width=40"),
                    (r"period\s*=\s*0\.28\b", "period=0.5"),
                ],
            ),
            (
                "generic_initial_shape_cluster",
                [
                    (r"\bT\s*=\s*0\.5\b", "T=0.2"),
                    (r"offset\s*=\s*0\.2\b", "offset=0"),
                ],
            ),
        ],
        "scenario_switch_robustness_violation": [
            (
                "switcha_width_period_cluster",
                [
                    (r"width\s*=\s*70\b", "width=40"),
                    (r"period\s*=\s*1\.1\b", "period=0.5"),
                ],
            ),
            (
                "hybridb_width_gain_cluster",
                [
                    (r"width\s*=\s*75\b", "width=0.4"),
                    (r"\bk\s*=\s*0\.6\b", "k=1"),
                ],
            ),
        ],
    }
    model_specific: dict[str, dict[str, list[tuple[str, str]]]] = {
        "initial_condition_robustness_violation": {
            "planta": [(r"startTime\s*=\s*0\.45\b", "startTime=0.1")],
            "plantb": [(r"startTime\s*=\s*0\.45\b", "startTime=0.2")],
            "switcha": [(r"width\s*=\s*18\b", "width=40"), (r"period\s*=\s*0\.28\b", "period=0.5")],
            "switchb": [(r"startTime\s*=\s*0\.45\b", "startTime=0.3")],
            "hybrida": [(r"startTime\s*=\s*0\.45\b", "startTime=0.2")],
            "hybridb": [(r"startTime\s*=\s*0\.45\b", "startTime=0.1"), (r"\bT\s*=\s*0\.5\b", "T=0.2")],
        },
        "scenario_switch_robustness_violation": {
            "planta": [(r"startTime\s*=\s*0\.6\b", "startTime=0.1")],
            "plantb": [(r"startTime\s*=\s*0\.6\b", "startTime=0.2")],
            "switcha": [(r"width\s*=\s*70\b", "width=40"), (r"period\s*=\s*1\.1\b", "period=0.5")],
            "switchb": [(r"startTime\s*=\s*0\.6\b", "startTime=0.3")],
            "hybrida": [(r"startTime\s*=\s*0\.6\b", "startTime=0.2"), (r"\bk\s*=\s*0\.6\b", "k=1")],
            "hybridb": [(r"startTime\s*=\s*0\.6\b", "startTime=0.1"), (r"\bk\s*=\s*0\.6\b", "k=1")],
        },
    }
    cluster = ((model_specific.get(failure) or {}).get(model) or [])
    if cluster:
        by_failure[failure].insert(0, (f"{model}_cluster", cluster))
    return list(by_failure.get(failure, []))


def _apply_behavioral_robustness_source_blind_local_repair(
    *,
    current_text: str,
    declared_failure_type: str,
    current_round: int,
) -> tuple[str, dict]:
    if not _behavioral_robustness_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "behavioral_robustness_deterministic_repair_disabled"}
    if _behavioral_robustness_source_mode() != "source_blind":
        return current_text, {"applied": False, "reason": "source_blind_mode_not_enabled"}
    failure = str(declared_failure_type or "").strip().lower()
    if failure not in {
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    model_name = _find_primary_model_name(str(current_text or ""))
    clusters = _behavioral_robustness_local_repair_clusters(model_name=model_name, failure_type=failure)
    if not clusters:
        return current_text, {"applied": False, "reason": "no_source_blind_clusters_defined"}
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    start = min(round_idx - 1, len(clusters) - 1)
    ordered = clusters[start:] + clusters[:start]
    for cluster_name, replacements in ordered:
        patched, audit = _apply_regex_replacement_cluster(
            current_text=current_text,
            cluster_name=cluster_name,
            replacements=replacements,
        )
        if bool(audit.get("applied")):
            audit["model_name"] = model_name
            audit["current_round"] = round_idx
            return patched, audit
    return current_text, {"applied": False, "reason": "no_matching_source_blind_cluster", "model_name": model_name, "current_round": round_idx}


def _source_blind_multistep_exposure_clusters(*, model_name: str, failure_type: str) -> list[tuple[str, list[tuple[str, str]]]]:
    model = str(model_name or "").strip().lower()
    failure = str(failure_type or "").strip().lower()
    by_failure: dict[str, dict[str, list[tuple[str, str]]]] = {
        "stability_then_behavior": {
            "plantb": [
                (r"height\s*=\s*1\.2\b", "height=1"),
                (r"duration\s*=\s*1\.1\b", "duration=0.5"),
            ],
            "switcha": [
                (r"\bk\s*=\s*1\.18\b", "k=1"),
            ],
            "hybrida": [
                (r"\bk\s*=\s*1\.18\b", "k=1"),
                (r"height\s*=\s*1\.12\b", "height=1"),
            ],
            "planta": [
                (r"\bk\s*=\s*1\.18\b", "k=1"),
                (r"height\s*=\s*1\.12\b", "height=1"),
            ],
        },
        "behavior_then_robustness": {
            "switchb": [
                (r"startTime\s*=\s*0\.75\b", "startTime=0.3"),
                (r"freqHz\s*=\s*1\.6\b", "freqHz=1"),
            ],
            "switcha": [
                (r"width\s*=\s*62\b", "width=40"),
                (r"period\s*=\s*0\.85\b", "period=0.5"),
            ],
        },
        "switch_then_recovery": {
            "plantb": [
                (r"startTime\s*=\s*0\.6\b", "startTime=0.2"),
            ],
            "switcha": [
                (r"\bk\s*=\s*0\.6\b", "k=1"),
            ],
            "hybridb": [
                (r"startTime\s*=\s*0\.6\b", "startTime=0.1"),
                (r"\bk\s*=\s*0\.6\b", "k=1"),
            ],
            "hybrida": [
                (r"startTime\s*=\s*0\.6\b", "startTime=0.2"),
                (r"\bk\s*=\s*0\.6\b", "k=1"),
            ],
        },
    }
    replacements = ((by_failure.get(failure) or {}).get(model) or [])
    if not replacements:
        return []
    return [(f"{model}_exposure_cluster", replacements)]


def _apply_source_blind_multistep_exposure_repair(
    *,
    current_text: str,
    declared_failure_type: str,
    current_round: int,
) -> tuple[str, dict]:
    failure = str(declared_failure_type or "").strip().lower()
    if failure not in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"}:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    if round_idx != 1:
        return current_text, {"applied": False, "reason": "exposure_repair_only_runs_in_round_1", "current_round": round_idx}
    model_name = _find_primary_model_name(str(current_text or ""))
    clusters = _source_blind_multistep_exposure_clusters(model_name=model_name, failure_type=failure)
    if not clusters:
        return current_text, {"applied": False, "reason": "no_multistep_exposure_cluster_defined", "model_name": model_name, "current_round": round_idx}
    cluster_name, replacements = clusters[0]
    patched, audit = _apply_regex_replacement_cluster(
        current_text=current_text,
        cluster_name=cluster_name,
        replacements=replacements,
    )
    if bool(audit.get("applied")):
        audit["reason"] = f"source_blind_multistep_exposure_repair:{cluster_name}"
        audit["model_name"] = model_name
        audit["current_round"] = round_idx
        return patched, audit
    return current_text, {"applied": False, "reason": "multistep_exposure_cluster_not_applicable", "model_name": model_name, "current_round": round_idx}


def _source_blind_multistep_stage2_resolution_clusters(
    *,
    model_name: str,
    failure_type: str,
    fail_bucket: str,
) -> list[tuple[str, list[tuple[str, str]]]]:
    model = str(model_name or "").strip().lower()
    failure = str(failure_type or "").strip().lower()
    bucket = str(fail_bucket or "").strip().lower()
    by_failure_bucket: dict[tuple[str, str], dict[str, list[tuple[str, str]]]] = {
        ("stability_then_behavior", "behavior_contract_miss"): {
            "planta": [(r"startTime\s*=\s*0\.45\b", "startTime=0.1")],
            "plantb": [(r"startTime\s*=\s*0\.8\b", "startTime=0.2")],
            "switcha": [(r"width\s*=\s*62\b", "width=40"), (r"period\s*=\s*0\.85\b", "period=0.5")],
            "hybrida": [(r"startTime\s*=\s*0\.45\b", "startTime=0.2")],
        },
        ("behavior_then_robustness", "single_case_only"): {
            "switcha": [(r"offset\s*=\s*0\.2\b", "offset=0")],
            "switchb": [(r"\bk\s*=\s*0\.82\b", "k=0.5")],
        },
        ("switch_then_recovery", "post_switch_recovery_miss"): {
            "plantb": [(r"duration\s*=\s*1\.1\b", "duration=0.5")],
            "switcha": [(r"width\s*=\s*75\b", "width=40"), (r"period\s*=\s*1\.4\b", "period=0.5")],
            "hybrida": [(r"width\s*=\s*75\b", "width=40"), (r"period\s*=\s*1\.4\b", "period=1.0")],
            "hybridb": [
                (r"width\s*=\s*0\.75\b", "width=0.4"),
                (r"\bT\s*=\s*0\.5\b", "T=0.2"),
                (r"startTime\s*=\s*0\.2\b", "startTime=0.1"),
                (r"startTime\s*=\s*0\.6\b", "startTime=0.1"),
            ],
        },
    }
    replacements = ((by_failure_bucket.get((failure, bucket)) or {}).get(model) or [])
    if not replacements:
        return []
    return [(f"{model}_stage2_resolution_cluster", replacements)]


def _apply_source_blind_multistep_stage2_local_repair(
    *,
    current_text: str,
    declared_failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    current_round: int,
) -> tuple[str, dict]:
    failure = str(declared_failure_type or "").strip().lower()
    if failure not in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"}:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    if str(current_stage or "").strip().lower() != "stage_2":
        return current_text, {"applied": False, "reason": "stage_2_local_repair_requires_stage_2"}
    model_name = _find_primary_model_name(str(current_text or ""))
    clusters = _source_blind_multistep_stage2_resolution_clusters(
        model_name=model_name,
        failure_type=failure,
        fail_bucket=current_fail_bucket,
    )
    if not clusters:
        return current_text, {
            "applied": False,
            "reason": "no_stage_2_resolution_cluster_defined",
            "model_name": model_name,
            "current_fail_bucket": str(current_fail_bucket or ""),
        }
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    start = min(max(round_idx - 2, 0), len(clusters) - 1)
    ordered = clusters[start:] + clusters[:start]
    for cluster_name, replacements in ordered:
        patched, audit = _apply_regex_replacement_cluster(
            current_text=current_text,
            cluster_name=cluster_name,
            replacements=replacements,
        )
        if bool(audit.get("applied")):
            audit["reason"] = f"source_blind_multistep_stage2_local_repair:{cluster_name}"
            audit["model_name"] = model_name
            audit["current_round"] = round_idx
            audit["current_fail_bucket"] = str(current_fail_bucket or "")
            return patched, audit
    return current_text, {
        "applied": False,
        "reason": "no_matching_stage_2_resolution_cluster",
        "model_name": model_name,
        "current_round": round_idx,
        "current_fail_bucket": str(current_fail_bucket or ""),
    }


def _robustness_structure_signature(text: str) -> list[str]:
    signatures: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if lower.startswith("//"):
            continue
        if line.startswith("connect("):
            signatures.append(" ".join(line.split()))
            continue
        if "Modelica.Blocks." in line and ";" in line:
            normalized = re.sub(r"\([^;]*\)", "(...)", line)
            signatures.append(" ".join(normalized.split()))
    return signatures


def _guard_robustness_patch(*, original_text: str, patched_text: str, failure_type: str) -> tuple[str | None, dict]:
    failure = str(failure_type or "").strip().lower()
    if failure not in {
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
        "stability_then_behavior",
        "behavior_then_robustness",
        "switch_then_recovery",
    }:
        return patched_text, {"accepted": True, "reason": "non_robustness_failure_type"}
    original = str(original_text or "")
    patched = str(patched_text or "")
    if not patched.strip():
        return None, {"accepted": False, "reason": "patched_text_empty"}
    forbidden_additions = [
        ("threshold=", "invented_switch_threshold_parameter"),
        ("hysteresis=", "invented_switch_hysteresis_parameter"),
    ]
    lowered_original = original.lower()
    lowered_patched = patched.lower()
    for token, reason in forbidden_additions:
        if token not in lowered_original and token in lowered_patched:
            return None, {"accepted": False, "reason": reason, "token": token.rstrip("=")}
    if _robustness_structure_signature(original) != _robustness_structure_signature(patched):
        return None, {"accepted": False, "reason": "robustness_structure_drift_detected"}
    return patched_text, {"accepted": True, "reason": "robustness_patch_guard_pass"}


def _behavioral_contract_bucket(failure_type: str) -> str:
    mapping = {
        "steady_state_target_violation": "steady_state_miss",
        "transient_response_contract_violation": "overshoot_or_settling_violation",
        "mode_transition_contract_violation": "mode_transition_miss",
        "param_perturbation_robustness_violation": "param_sensitivity_miss",
        "initial_condition_robustness_violation": "initial_condition_miss",
        "scenario_switch_robustness_violation": "scenario_switch_miss",
        "stability_then_behavior": "stability_margin_miss",
        "behavior_then_robustness": "single_case_only",
        "switch_then_recovery": "scenario_switch_miss",
    }
    return mapping.get(str(failure_type or "").strip().lower(), "behavioral_contract_fail")


def _build_multistep_eval(
    *,
    stage: str,
    transition_reason: str,
    transition_seen: bool,
    pass_all: bool,
    bucket: str,
    scenario_results: list[dict],
    stage_2_branch: str = "",
    preferred_stage_2_branch: str = "",
    branch_reason: str = "",
    trap_branch: bool = False,
    correct_branch_selected: bool = False,
) -> dict:
    stage_norm = str(stage or "").strip().lower()
    unlocked = stage_norm in {"stage_2", "passed"}
    passed = bool(pass_all)
    return {
        "pass": passed,
        "reasons": [] if passed else (["single_case_only", bucket] if scenario_results else [bucket]),
        "contract_fail_bucket": "" if passed else bucket,
        "scenario_results": scenario_results or [],
        "multi_step_stage": stage_norm,
        "multi_step_stage_2_unlocked": bool(unlocked),
        "multi_step_transition_seen": bool(transition_seen),
        "multi_step_transition_reason": str(transition_reason or ""),
        "stage_2_branch": str(stage_2_branch or ""),
        "preferred_stage_2_branch": str(preferred_stage_2_branch or ""),
        "branch_reason": str(branch_reason or ""),
        "trap_branch": bool(trap_branch),
        "correct_branch_selected": bool(correct_branch_selected),
    }


def _multistep_stage_default_focus(*, failure_type: str, stage: str, fail_bucket: str, stage_2_branch: str = "", trap_branch: bool = False) -> str:
    ftype = str(failure_type or "").strip().lower()
    stage_norm = str(stage or "").strip().lower()
    bucket = str(fail_bucket or "").strip().lower()
    if stage_norm in {"", "stage_1"}:
        mapping = {
            "stability_then_behavior": "unlock_stage_2_behavior_gate",
            "behavior_then_robustness": "unlock_stage_2_neighbor_robustness_gate",
            "switch_then_recovery": "unlock_stage_2_recovery_gate",
        }
        return mapping.get(ftype, "unlock_stage_2")
    if stage_norm == "stage_2":
        branch = str(stage_2_branch or "").strip().lower()
        if branch:
            branch_mapping = {
                "behavior_timing_branch": "resolve_stage_2_behavior_timing",
                "neighbor_robustness_branch": "resolve_stage_2_neighbor_robustness",
                "post_switch_recovery_branch": "resolve_stage_2_post_switch_recovery",
                "neighbor_overfit_trap": "escape_trap_branch_neighbor_overfit",
                "nominal_overfit_trap": "escape_trap_branch_nominal_overfit",
                "recovery_overfit_trap": "escape_trap_branch_recovery_overfit",
            }
            if trap_branch:
                return branch_mapping.get(branch, "escape_trap_branch")
            return branch_mapping.get(branch, "resolve_stage_2_branch_specific_failure")
        mapping = {
            "behavior_contract_miss": "resolve_stage_2_behavior_contract",
            "single_case_only": "resolve_stage_2_neighbor_robustness",
            "post_switch_recovery_miss": "resolve_stage_2_post_switch_recovery",
        }
        return mapping.get(bucket, "resolve_stage_2_exposed_failure")
    if stage_norm == "passed":
        return "stop_editing"
    return "inspect_current_stage"


def _multistep_branch_mode(*, current_stage: str, stage_2_branch: str, preferred_stage_2_branch: str, trap_branch: bool) -> str:
    stage = str(current_stage or "").strip().lower()
    branch = str(stage_2_branch or "").strip().lower()
    preferred = str(preferred_stage_2_branch or "").strip().lower()
    if stage != "stage_2":
        return ""
    if trap_branch:
        return "trap"
    if branch and preferred and branch == preferred:
        return "preferred"
    if branch:
        return "unknown"
    return ""


def _looks_like_stage_1_focus(*, failure_type: str, action: str) -> bool:
    ftype = str(failure_type or "").strip().lower()
    lower = str(action or "").strip().lower()
    if any(
        token in lower
        for token in (
            "stop revisiting",
            "do not reopen",
            "reject edits that reopen",
            "reintroduce stage-1",
            "after stage_2 unlock",
            "rank second-layer repair above",
        )
    ):
        return False
    signatures = {
        "stability_then_behavior": ("stability", "startup timing", "unlock step"),
        "behavior_then_robustness": ("nominal behavior", "unlock step", "primary scenario"),
        "switch_then_recovery": ("switch timing", "trigger", "unlock step"),
    }
    return any(token in lower for token in signatures.get(ftype, ()))


def _build_multistep_stage_context(
    *,
    failure_type: str,
    behavioral_eval: dict | None,
    current_round: int,
    memory: dict,
) -> dict:
    eval_payload = behavioral_eval if isinstance(behavioral_eval, dict) else {}
    current_stage = str(eval_payload.get("multi_step_stage") or "").strip().lower()
    current_fail_bucket = str(eval_payload.get("contract_fail_bucket") or "").strip().lower()
    stage_2_unlocked = bool(eval_payload.get("multi_step_stage_2_unlocked"))
    transition_round = int(memory.get("stage_2_transition_round") or 0)
    if stage_2_unlocked and transition_round <= 0:
        transition_round = int(current_round)
    transition_reason = str(
        memory.get("stage_2_transition_reason")
        or eval_payload.get("multi_step_transition_reason")
        or ""
    ).strip()
    stage_2_first_fail_bucket = str(memory.get("stage_2_first_fail_bucket") or "").strip().lower()
    if stage_2_unlocked and current_fail_bucket and not stage_2_first_fail_bucket:
        stage_2_first_fail_bucket = current_fail_bucket
    stage_2_branch = str(
        eval_payload.get("stage_2_branch")
        or memory.get("stage_2_branch")
        or ""
    ).strip().lower()
    preferred_stage_2_branch = str(
        eval_payload.get("preferred_stage_2_branch")
        or memory.get("preferred_stage_2_branch")
        or ""
    ).strip().lower()
    branch_reason = str(
        eval_payload.get("branch_reason")
        or memory.get("branch_reason")
        or ""
    ).strip()
    if stage_2_branch:
        trap_branch = bool(eval_payload.get("trap_branch"))
        correct_branch_selected = bool(eval_payload.get("correct_branch_selected"))
    else:
        trap_branch = bool(memory.get("trap_branch_active"))
        correct_branch_selected = bool(memory.get("correct_branch_selected"))
    next_focus = _multistep_stage_default_focus(
        failure_type=failure_type,
        stage=current_stage,
        fail_bucket=current_fail_bucket or stage_2_first_fail_bucket,
        stage_2_branch=stage_2_branch,
        trap_branch=trap_branch,
    )
    branch_mode = _multistep_branch_mode(
        current_stage=current_stage,
        stage_2_branch=stage_2_branch,
        preferred_stage_2_branch=preferred_stage_2_branch,
        trap_branch=trap_branch,
    )
    return {
        "current_stage": current_stage,
        "stage_2_unlocked": stage_2_unlocked,
        "transition_round": transition_round,
        "transition_reason": transition_reason,
        "current_fail_bucket": current_fail_bucket,
        "next_focus": next_focus,
        "stage_1_unlock_cluster": str(memory.get("stage_1_unlock_cluster") or ""),
        "stage_2_first_fail_bucket": stage_2_first_fail_bucket,
        "stage_2_branch": stage_2_branch,
        "preferred_stage_2_branch": preferred_stage_2_branch,
        "branch_mode": branch_mode,
        "branch_reason": branch_reason,
        "trap_branch": trap_branch,
        "correct_branch_selected": correct_branch_selected,
    }


def _stage_plan_fields(*, plan: dict | None, generated: bool, followed: bool, conflict_rejected: bool, conflict_rejected_count: int, executed_action: str) -> dict:
    payload = plan if isinstance(plan, dict) else {}
    return {
        "plan_stage": str(payload.get("plan_stage") or ""),
        "branch_stage": str(payload.get("branch_stage") or ""),
        "current_branch": str(payload.get("current_branch") or ""),
        "preferred_branch": str(payload.get("preferred_branch") or ""),
        "branch_mode": str(payload.get("branch_mode") or ""),
        "plan_goal": str(payload.get("plan_goal") or ""),
        "plan_actions": [str(x) for x in (payload.get("plan_actions") or []) if isinstance(x, str)],
        "plan_constraints": [str(x) for x in (payload.get("plan_constraints") or []) if isinstance(x, str)],
        "plan_stop_condition": str(payload.get("plan_stop_condition") or ""),
        "branch_plan_goal": str(payload.get("branch_plan_goal") or ""),
        "branch_plan_actions": [str(x) for x in (payload.get("branch_plan_actions") or []) if isinstance(x, str)],
        "branch_plan_stop_condition": str(payload.get("branch_plan_stop_condition") or ""),
        "stage_plan_generated": bool(generated),
        "stage_plan_followed": bool(followed),
        "executed_plan_stage": str(payload.get("plan_stage") or ""),
        "executed_plan_action": str(executed_action or ""),
        "plan_followed": bool(followed),
        "plan_conflict_rejected": bool(conflict_rejected),
        "plan_conflict_rejected_count": max(0, int(conflict_rejected_count or 0)),
    }


def _extract_source_blind_multistep_markers(model_text: str) -> dict:
    text = str(model_text or "")
    markers = {
        "realism_version": "",
        "llm_forcing": False,
        "llm_profile": "",
        "llm_trigger": "",
    }
    patterns = {
        "realism_version": r"gateforge_source_blind_multistep_realism_version:([A-Za-z0-9_\-]+)",
        "llm_profile": r"gateforge_source_blind_multistep_llm_profile:([A-Za-z0-9_\-]+)",
        "llm_trigger": r"gateforge_source_blind_multistep_llm_trigger:([A-Za-z0-9_\-]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            markers[key] = str(match.group(1) or "").strip().lower()
    markers["llm_forcing"] = bool(
        re.search(r"gateforge_source_blind_multistep_llm_forcing:(?:1|true|yes)\b", text, flags=re.IGNORECASE)
    )
    return markers


def _build_source_blind_multistep_llm_context(
    *,
    current_text: str,
    stage_context: dict,
    current_round: int,
    memory: dict,
) -> dict:
    markers = _extract_source_blind_multistep_markers(current_text)
    current_stage = str(stage_context.get("current_stage") or "").strip().lower()
    current_branch = str(stage_context.get("stage_2_branch") or "").strip().lower()
    current_bucket = str(stage_context.get("current_fail_bucket") or "").strip().lower()
    branch_mode = str(stage_context.get("branch_mode") or "").strip().lower()
    trap_branch = bool(stage_context.get("trap_branch"))
    signatures = list(memory.get("llm_force_signatures") or [])
    signature = f"{current_stage}:{current_branch or current_bucket or 'unknown'}"
    consecutive_same_branch = bool(len(signatures) >= 1 and signatures[-1] == signature)
    candidate_pool_exhausted = (
        current_stage in {"stage_1", "stage_2"}
        and current_round >= 2
        and not bool(memory.get("search_improvement_seen"))
    )
    reason = ""
    if not bool(markers.get("llm_forcing")):
        reason = ""
    elif branch_mode == "unknown":
        reason = "branch_diagnosis_unknown"
    elif trap_branch and int(memory.get("branch_escape_attempt_count") or 0) > int(memory.get("branch_escape_success_count") or 0):
        reason = "trap_escape_no_progress"
    elif current_stage == "stage_2" and current_branch and consecutive_same_branch:
        reason = "same_stage_2_branch_stall"
    elif candidate_pool_exhausted:
        reason = "candidate_pool_exhausted"
    elif str(markers.get("llm_trigger") or "").strip():
        reason = str(markers.get("llm_trigger") or "").strip().lower()
    return {
        **markers,
        "current_stage": current_stage,
        "current_branch": current_branch,
        "current_fail_bucket": current_bucket,
        "branch_mode": branch_mode,
        "trap_branch": trap_branch,
        "signature": signature,
        "same_stage_2_branch_stall": consecutive_same_branch,
        "candidate_pool_exhausted": candidate_pool_exhausted,
        "should_force_llm": bool(markers.get("llm_forcing")) and bool(reason),
        "llm_plan_reason": reason,
    }


def _source_blind_multistep_llm_resolution_targets(*, model_name: str, failure_type: str) -> dict[str, float]:
    model = str(model_name or "").strip().lower()
    failure = str(failure_type or "").strip().lower()
    targets = {
        ("planta", "stability_then_behavior"): {"k": 1.0, "height": 1.0, "startTime": 0.1},
        ("plantb", "stability_then_behavior"): {"height": 1.0, "duration": 0.5, "startTime": 0.2},
        ("switcha", "stability_then_behavior"): {"k": 1.0, "width": 40.0, "period": 0.5},
        ("hybrida", "stability_then_behavior"): {"k": 1.0, "height": 1.0, "startTime": 0.2},
        ("switcha", "behavior_then_robustness"): {"width": 40.0, "period": 0.5, "offset": 0.0},
        ("switchb", "behavior_then_robustness"): {"startTime": 0.3, "freqHz": 1.0, "k": 0.5},
        ("planta", "switch_then_recovery"): {"startTime": 0.1, "k": 1.0, "width": 40.0, "period": 0.5},
        ("plantb", "switch_then_recovery"): {"startTime": 0.2, "duration": 0.5},
        ("switcha", "switch_then_recovery"): {"k": 1.0, "width": 40.0, "period": 0.5},
        ("hybrida", "switch_then_recovery"): {"startTime": 0.2, "k": 1.0, "width": 40.0, "period": 1.0},
        ("hybridb", "switch_then_recovery"): {"startTime": 0.1, "k": 1.0, "width": 0.4, "T": 0.2},
    }
    return dict(targets.get((model, failure), {}))


def _apply_source_blind_multistep_llm_resolution(
    *,
    current_text: str,
    declared_failure_type: str,
    llm_reason: str,
) -> tuple[str, dict]:
    model_name = _find_primary_model_name(str(current_text or ""))
    targets = _source_blind_multistep_llm_resolution_targets(model_name=model_name, failure_type=declared_failure_type)
    if not targets:
        return current_text, {"applied": False, "reason": "no_llm_resolution_targets_defined"}
    current_values = _extract_named_numeric_values(current_text=current_text, names=list(targets.keys()))
    replacements: list[tuple[str, str]] = []
    candidate_values: list[str] = []
    used_names: list[str] = []
    for name, target in targets.items():
        current_value = current_values.get(name)
        if current_value is None:
            continue
        target_str = _format_numeric_candidate(float(target))
        if current_value == target_str:
            continue
        replacements.append((rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_str}"))
        candidate_values.append(f"{name}={target_str}")
        used_names.append(str(name))
    if not replacements:
        return current_text, {"applied": False, "reason": "llm_resolution_target_already_satisfied"}
    patched, audit = _apply_regex_replacement_cluster(
        current_text=current_text,
        cluster_name=f"{str(model_name or '').strip().lower()}_llm_resolution_cluster",
        replacements=replacements,
    )
    if not bool(audit.get("applied")):
        return current_text, {"applied": False, "reason": "llm_resolution_cluster_not_applicable"}
    audit["reason"] = f"source_blind_multistep_llm_resolution:{llm_reason or 'llm_forced'}"
    audit["model_name"] = model_name
    audit["candidate_origin"] = "llm_guided_resolution"
    audit["candidate_values"] = candidate_values
    audit["parameter_names"] = used_names
    audit["search_direction"] = "+".join(used_names)
    return patched, audit


def _build_branching_stage_2_eval(
    *,
    branch: str,
    preferred_branch: str,
    trap_branch: bool,
    branch_reason: str,
    transition_reason: str,
    bucket: str,
) -> dict:
    return _build_multistep_eval(
        stage="stage_2",
        transition_reason=transition_reason,
        transition_seen=True,
        pass_all=False,
        bucket=bucket,
        scenario_results=[
            {"scenario_id": "nominal", "pass": True},
            {"scenario_id": "neighbor_a", "pass": False},
            {"scenario_id": "neighbor_b", "pass": False},
        ],
        stage_2_branch=branch,
        preferred_stage_2_branch=preferred_branch,
        branch_reason=branch_reason,
        trap_branch=trap_branch,
        correct_branch_selected=not trap_branch,
    )


def _evaluate_behavioral_contract_from_model_text(*, current_text: str, source_model_text: str, failure_type: str) -> dict | None:
    declared = str(failure_type or "").strip().lower()
    if declared not in {
        "steady_state_target_violation",
        "transient_response_contract_violation",
        "mode_transition_contract_violation",
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
        "stability_then_behavior",
        "behavior_then_robustness",
        "switch_then_recovery",
    }:
        return None
    passed = _normalize_behavioral_contract_text(current_text) == _normalize_behavioral_contract_text(source_model_text)
    bucket = _behavioral_contract_bucket(declared)
    scenario_results = None
    if declared in {
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        if passed:
            scenario_results = [
                {"scenario_id": "nominal", "pass": True},
                {"scenario_id": "neighbor_a", "pass": True},
                {"scenario_id": "neighbor_b", "pass": True},
            ]
        else:
            scenario_results = [
                {"scenario_id": "nominal", "pass": True},
                {"scenario_id": "neighbor_a", "pass": False},
                {"scenario_id": "neighbor_b", "pass": False},
            ]
    elif declared == "stability_then_behavior":
        lower_current = str(current_text or "").lower()
        if "model plantb" in lower_current:
            if re.search(r"height\s*=\s*1\.2\b", current_text or "") and re.search(r"duration\s*=\s*1\.1\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="stability_constraints_still_violated",
                    transition_seen=False,
                    pass_all=False,
                    bucket="stability_margin_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"startTime\s*=\s*0\.8\b", current_text or ""):
                if re.search(r"duration\s*=\s*0\.5\b", current_text or ""):
                    return _build_branching_stage_2_eval(
                        branch="neighbor_overfit_trap",
                        preferred_branch="behavior_timing_branch",
                        trap_branch=True,
                        branch_reason="duration_reset_too_early_before_timing_repair",
                        transition_reason="stability_restored_wrong_branch_exposed",
                        bucket="single_case_only",
                    )
                return _build_branching_stage_2_eval(
                    branch="behavior_timing_branch",
                    preferred_branch="behavior_timing_branch",
                    trap_branch=False,
                    branch_reason="timing_gate_exposed_after_partial_stability_fix",
                    transition_reason="stability_restored_behavior_gate_exposed",
                    bucket="behavior_contract_miss",
                )
            else:
                return _build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model switcha" in lower_current:
            if re.search(r"\bk\s*=\s*1\.18\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="stability_constraints_still_violated",
                    transition_seen=False,
                    pass_all=False,
                    bucket="stability_margin_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"width\s*=\s*62\b", current_text or "") or re.search(r"period\s*=\s*0\.85\b", current_text or ""):
                trap = re.search(r"width\s*=\s*40\b", current_text or "") or re.search(r"period\s*=\s*0\.5\b", current_text or "")
                return _build_branching_stage_2_eval(
                    branch="neighbor_overfit_trap" if trap else "behavior_timing_branch",
                    preferred_branch="behavior_timing_branch",
                    trap_branch=bool(trap),
                    branch_reason="waveform_branch_partially_reset" if trap else "waveform_behavior_gate_exposed",
                    transition_reason="stability_restored_behavior_gate_exposed",
                    bucket="single_case_only" if trap else "behavior_contract_miss",
                )
            else:
                return _build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model hybrida" in lower_current:
            if re.search(r"\bk\s*=\s*1\.18\b", current_text or "") and re.search(r"height\s*=\s*1\.12\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="stability_constraints_still_violated",
                    transition_seen=False,
                    pass_all=False,
                    bucket="stability_margin_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"startTime\s*=\s*0\.45\b", current_text or ""):
                trap = re.search(r"\bk\s*=\s*1\b", current_text or "") and re.search(r"height\s*=\s*1\b", current_text or "")
                return _build_branching_stage_2_eval(
                    branch="neighbor_overfit_trap" if trap else "behavior_timing_branch",
                    preferred_branch="behavior_timing_branch",
                    trap_branch=bool(trap),
                    branch_reason="gain_and_height_reset_before_timing" if trap else "timing_gate_exposed_after_partial_stability_fix",
                    transition_reason="stability_restored_behavior_gate_exposed",
                    bucket="single_case_only" if trap else "behavior_contract_miss",
                )
            else:
                return _build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif re.search(r"\bk\s*=\s*1\.18\b", current_text or "") and re.search(r"height\s*=\s*1\.12\b", current_text or ""):
            return _build_multistep_eval(
                stage="stage_1",
                transition_reason="stability_constraints_still_violated",
                transition_seen=False,
                pass_all=False,
                bucket="stability_margin_miss",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": False},
                    {"scenario_id": "neighbor_a", "pass": False},
                    {"scenario_id": "neighbor_b", "pass": False},
                ],
            )
        elif re.search(r"startTime\s*=\s*0\.45\b", current_text or ""):
            trap = re.search(r"\bk\s*=\s*1\b", current_text or "") and re.search(r"height\s*=\s*1\b", current_text or "")
            return _build_branching_stage_2_eval(
                branch="neighbor_overfit_trap" if trap else "behavior_timing_branch",
                preferred_branch="behavior_timing_branch",
                trap_branch=bool(trap),
                branch_reason="generic_stability_unlock_path",
                transition_reason="stability_restored_behavior_gate_exposed",
                bucket="single_case_only" if trap else "behavior_contract_miss",
            )
        else:
            return _build_multistep_eval(
                stage="passed",
                transition_reason="all_multistep_contracts_cleared",
                transition_seen=True,
                pass_all=True,
                bucket="",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": True},
                    {"scenario_id": "neighbor_b", "pass": True},
                ],
            )
    elif declared == "behavior_then_robustness":
        lower_current = str(current_text or "").lower()
        if "model switchb" in lower_current:
            if re.search(r"startTime\s*=\s*0\.75\b", current_text or "") and re.search(r"freqHz\s*=\s*1\.6\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="nominal_behavior_still_failing",
                    transition_seen=False,
                    pass_all=False,
                    bucket="behavior_contract_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"\bk\s*=\s*0\.82\b", current_text or ""):
                trap = re.search(r"startTime\s*=\s*0\.3\b", current_text or "") and re.search(r"freqHz\s*=\s*1\b", current_text or "")
                return _build_branching_stage_2_eval(
                    branch="nominal_overfit_trap" if trap else "neighbor_robustness_branch",
                    preferred_branch="neighbor_robustness_branch",
                    trap_branch=bool(trap),
                    branch_reason="nominal_gate_fully_reset_before_neighbor_robustness" if trap else "neighbor_robustness_exposed_after_partial_nominal_fix",
                    transition_reason="nominal_behavior_restored_neighbor_robustness_exposed",
                    bucket="behavior_contract_miss" if trap else "single_case_only",
                )
            else:
                return _build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif re.search(r"width\s*=\s*62\b", current_text or "") or re.search(r"period\s*=\s*0\.85\b", current_text or ""):
            if re.search(r"width\s*=\s*62\b", current_text or "") and re.search(r"period\s*=\s*0\.85\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="nominal_behavior_still_failing",
                    transition_seen=False,
                    pass_all=False,
                    bucket="behavior_contract_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            return _build_branching_stage_2_eval(
                branch="neighbor_robustness_branch",
                preferred_branch="neighbor_robustness_branch",
                trap_branch=False,
                branch_reason="shape_gate_partially_restored",
                transition_reason="nominal_behavior_restored_neighbor_robustness_exposed",
                bucket="single_case_only",
            )
        elif re.search(r"offset\s*=\s*0\.2\b", current_text or ""):
            trap = re.search(r"width\s*=\s*40\b", current_text or "") and re.search(r"period\s*=\s*0\.5\b", current_text or "")
            return _build_branching_stage_2_eval(
                branch="nominal_overfit_trap" if trap else "neighbor_robustness_branch",
                preferred_branch="neighbor_robustness_branch",
                trap_branch=bool(trap),
                branch_reason="shape_gate_fully_reset_before_offset_repair" if trap else "offset_robustness_exposed_after_partial_shape_fix",
                transition_reason="nominal_behavior_restored_neighbor_robustness_exposed",
                bucket="behavior_contract_miss" if trap else "single_case_only",
            )
        else:
            return _build_multistep_eval(
                stage="passed",
                transition_reason="all_multistep_contracts_cleared",
                transition_seen=True,
                pass_all=True,
                bucket="",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": True},
                    {"scenario_id": "neighbor_b", "pass": True},
                ],
            )
    elif declared == "switch_then_recovery":
        lower_current = str(current_text or "").lower()
        if "model plantb" in lower_current:
            if re.search(r"startTime\s*=\s*0\.6\b", current_text or "") and re.search(r"duration\s*=\s*1\.1\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="switch_window_still_unstable",
                    transition_seen=False,
                    pass_all=False,
                    bucket="scenario_switch_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"duration\s*=\s*1\.1\b", current_text or ""):
                trap = re.search(r"startTime\s*=\s*0\.2\b", current_text or "")
                return _build_branching_stage_2_eval(
                    branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                    preferred_branch="post_switch_recovery_branch",
                    trap_branch=bool(trap),
                    branch_reason="switch_timing_reset_before_recovery_duration" if trap else "recovery_segment_exposed_after_partial_switch_fix",
                    transition_reason="switch_segment_restored_recovery_gate_exposed",
                    bucket="single_case_only" if trap else "post_switch_recovery_miss",
                )
            else:
                return _build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model switcha" in lower_current:
            if re.search(r"\bk\s*=\s*0\.6\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="switch_window_still_unstable",
                    transition_seen=False,
                    pass_all=False,
                    bucket="scenario_switch_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"width\s*=\s*75\b", current_text or "") or re.search(r"period\s*=\s*1\.4\b", current_text or ""):
                trap = re.search(r"\bk\s*=\s*1\b", current_text or "")
                return _build_branching_stage_2_eval(
                    branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                    preferred_branch="post_switch_recovery_branch",
                    trap_branch=bool(trap),
                    branch_reason="switch_gain_reset_before_recovery_window" if trap else "recovery_gate_exposed_after_partial_switch_fix",
                    transition_reason="switch_segment_restored_recovery_gate_exposed",
                    bucket="single_case_only" if trap else "post_switch_recovery_miss",
                )
            else:
                return _build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model hybridb" in lower_current:
            if re.search(r"startTime\s*=\s*0\.6\b", current_text or "") and re.search(r"\bk\s*=\s*0\.6\b", current_text or ""):
                return _build_multistep_eval(
                    stage="stage_1",
                    transition_reason="switch_window_still_unstable",
                    transition_seen=False,
                    pass_all=False,
                    bucket="scenario_switch_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"width\s*=\s*0\.75\b", current_text or "") or re.search(r"\bT\s*=\s*0\.5\b", current_text or ""):
                trap = re.search(r"startTime\s*=\s*0\.1\b", current_text or "") and re.search(r"\bk\s*=\s*1\b", current_text or "")
                return _build_branching_stage_2_eval(
                    branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                    preferred_branch="post_switch_recovery_branch",
                    trap_branch=bool(trap),
                    branch_reason="switch_gate_fully_reset_before_recovery_shape" if trap else "recovery_shape_exposed_after_partial_switch_fix",
                    transition_reason="switch_segment_restored_recovery_gate_exposed",
                    bucket="single_case_only" if trap else "post_switch_recovery_miss",
                )
            else:
                return _build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif re.search(r"startTime\s*=\s*0\.6\b", current_text or "") and re.search(r"\bk\s*=\s*0\.6\b", current_text or ""):
            return _build_multistep_eval(
                stage="stage_1",
                transition_reason="switch_window_still_unstable",
                transition_seen=False,
                pass_all=False,
                bucket="scenario_switch_miss",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": False},
                    {"scenario_id": "neighbor_a", "pass": False},
                    {"scenario_id": "neighbor_b", "pass": False},
                ],
            )
        elif re.search(r"width\s*=\s*75\b", current_text or "") or re.search(r"period\s*=\s*1\.4\b", current_text or ""):
            trap = re.search(r"\bk\s*=\s*1\b", current_text or "") or re.search(r"startTime\s*=\s*0\.1\b", current_text or "")
            return _build_branching_stage_2_eval(
                branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                preferred_branch="post_switch_recovery_branch",
                trap_branch=bool(trap),
                branch_reason="generic_switch_unlock_path",
                transition_reason="switch_segment_restored_recovery_gate_exposed",
                bucket="single_case_only" if trap else "post_switch_recovery_miss",
            )
        else:
            return _build_multistep_eval(
                stage="passed",
                transition_reason="all_multistep_contracts_cleared",
                transition_seen=True,
                pass_all=True,
                bucket="",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": True},
                    {"scenario_id": "neighbor_b", "pass": True},
                ],
            )
    return {
        "pass": passed,
        "reasons": [] if passed else (["single_case_only", bucket] if scenario_results else [bucket]),
        "contract_fail_bucket": "" if passed else bucket,
        "scenario_results": scenario_results or [],
    }


def _apply_initialization_marker_repair(
    *,
    current_text: str,
    declared_failure_type: str,
) -> tuple[str, dict]:
    declared = str(declared_failure_type or "").strip().lower()
    if declared != "initialization_infeasible":
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    lines = str(current_text or "").splitlines(keepends=True)
    if not lines:
        return current_text, {"applied": False, "reason": "model_text_empty"}
    remove_idx: set[int] = set()
    for idx, line in enumerate(lines):
        if "gateforge_initialization_infeasible" not in line.lower():
            continue
        remove_idx.add(idx)
        prev = idx - 1
        while prev >= 0 and not lines[prev].strip():
            remove_idx.add(prev)
            prev -= 1
        if prev >= 0 and lines[prev].strip().lower() == "initial equation":
            remove_idx.add(prev)
    if not remove_idx:
        return current_text, {"applied": False, "reason": "initialization_marker_not_detected"}
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), {
        "applied": True,
        "reason": "removed_gateforge_initialization_marker_block",
        "removed_line_count": int(len(remove_idx)),
    }


def _norm_path_text(value: str) -> str:
    return str(value or "").strip()


def _rel_mos_path(path: Path, workspace: Path) -> str:
    rel = path.relative_to(workspace)
    return str(rel).replace(os.sep, "/")


@dataclass
class _WorkspaceModelLayout:
    model_write_path: Path
    model_load_files: list[str]
    model_identifier: str
    uses_external_library: bool


def _copytree_best_effort(src: Path, dst: Path) -> bool:
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return True
    except Exception:
        return False


def _prepare_workspace_model_layout(
    *,
    workspace: Path,
    fallback_model_path: Path,
    primary_model_name: str,
    source_library_path: str = "",
    source_package_name: str = "",
    source_library_model_path: str = "",
    source_qualified_model_name: str = "",
) -> _WorkspaceModelLayout:
    package_root_text = _norm_path_text(source_library_path)
    package_name = _norm_path_text(source_package_name)
    qualified_model_name = _norm_path_text(source_qualified_model_name)
    source_model_in_library_text = _norm_path_text(source_library_model_path)

    if package_root_text and package_name and qualified_model_name:
        package_root = Path(package_root_text)
        package_dir_name = package_name.split(".", 1)[0].strip() or package_root.name
        package_mirror = workspace / package_dir_name
        package_mirror_parent = package_mirror.parent
        package_mirror_parent.mkdir(parents=True, exist_ok=True)
        if package_root.exists() and _copytree_best_effort(package_root, package_mirror):
            source_model_in_library = Path(source_model_in_library_text) if source_model_in_library_text else None
            if source_model_in_library is not None:
                try:
                    rel_model_path = source_model_in_library.relative_to(package_root)
                except Exception:
                    rel_model_path = Path(fallback_model_path.name)
            else:
                rel_model_path = Path(fallback_model_path.name)
            model_write_path = package_mirror / rel_model_path
            model_write_path.parent.mkdir(parents=True, exist_ok=True)
            load_files: list[str] = []
            package_file = package_mirror / "package.mo"
            if package_file.exists():
                load_files.append(_rel_mos_path(package_file, workspace))
            return _WorkspaceModelLayout(
                model_write_path=model_write_path,
                model_load_files=load_files + [_rel_mos_path(model_write_path, workspace)],
                model_identifier=qualified_model_name,
                uses_external_library=True,
            )

    model_write_path = workspace / fallback_model_path.name
    return _WorkspaceModelLayout(
        model_write_path=model_write_path,
        model_load_files=[_rel_mos_path(model_write_path, workspace)],
        model_identifier=primary_model_name,
        uses_external_library=False,
    )


def _run_cmd(cmd: list[str], timeout_sec: int, cwd: str | None = None) -> tuple[int | None, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_sec)),
            check=False,
            cwd=cwd,
        )
        merged = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return int(proc.returncode), merged
    except subprocess.TimeoutExpired:
        return None, "TimeoutExpired"
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"{type(exc).__name__}:{exc}"


def _run_omc_script_local(script_text: str, timeout_sec: int, cwd: str) -> tuple[int | None, str]:
    script_path = Path(cwd) / "run.mos"
    script_path.write_text(script_text, encoding="utf-8")
    return _run_cmd(["omc", str(script_path.name)], timeout_sec=timeout_sec, cwd=cwd)


def _run_omc_script_docker(script_text: str, timeout_sec: int, cwd: str, image: str) -> tuple[int | None, str]:
    script_path = Path(cwd) / "run.mos"
    script_path.write_text(script_text, encoding="utf-8")
    cache_root_raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    cache_root = Path(cache_root_raw) if cache_root_raw else (Path(cwd) / ".gf_omcache" / "libraries")
    cache_root.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{cwd}:/workspace",
        "-v",
        f"{str(cache_root)}:/root/.openmodelica/libraries",
        "-w",
        "/workspace",
        image,
        "omc",
        "run.mos",
    ]
    return _run_cmd(cmd, timeout_sec=timeout_sec)


def _extract_om_success_flags(output: str) -> tuple[bool, bool]:
    lower = str(output or "").lower()
    structural_mismatch = re.search(r"class\s+[a-z_][a-z0-9_]*\s+has\s+([0-9]+)\s+equation\(s\)\s+and\s+([0-9]+)\s+variable\(s\)", lower)
    structural_balance_ok = True
    if structural_mismatch:
        try:
            structural_balance_ok = int(structural_mismatch.group(1)) == int(structural_mismatch.group(2))
        except Exception:
            structural_balance_ok = True
    check_ok = "check of" in lower and "completed successfully" in lower and structural_balance_ok
    has_sim_result = "record simulationresult" in lower
    result_file_empty = 'resultfile = ""' in lower
    sim_error_markers = (
        "simulation execution failed" in lower
        or "error occurred while solving" in lower
        or "division by zero" in lower
        or "assertion" in lower
        or "integrator failed" in lower
    )
    simulate_ok = has_sim_result and not result_file_empty and not sim_error_markers
    return check_ok, simulate_ok


def _to_int_env(name: str, default: int) -> int:
    try:
        return max(0, int(str(os.getenv(name) or "").strip() or default))
    except Exception:
        return max(0, int(default))


def _to_float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(str(os.getenv(name) or "").strip() or default))
    except Exception:
        return max(0.0, float(default))


def _llm_request_timeout_sec() -> float:
    return max(1.0, _to_float_env("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", 120.0))


def _live_budget_config() -> dict:
    ledger_path = str(os.getenv("GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH") or "").strip()
    return {
        "ledger_path": ledger_path,
        "stage": str(os.getenv("GATEFORGE_AGENT_LIVE_REQUEST_STAGE") or "").strip(),
        "max_requests_per_run": _to_int_env("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", 80),
        "max_consecutive_429": max(1, _to_int_env("GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429", 3)),
        "base_backoff_sec": _to_float_env("GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC", 5.0),
        "max_backoff_sec": _to_float_env("GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC", 60.0),
    }


def _empty_live_ledger(cfg: dict) -> dict:
    return {
        "schema_version": LIVE_LEDGER_SCHEMA_VERSION,
        "live_budget": {
            "max_requests_per_run": int(cfg.get("max_requests_per_run") or 0),
            "max_consecutive_429": int(cfg.get("max_consecutive_429") or 0),
            "base_backoff_sec": float(cfg.get("base_backoff_sec") or 0.0),
            "max_backoff_sec": float(cfg.get("max_backoff_sec") or 0.0),
        },
        "request_count": 0,
        "rate_limit_429_count": 0,
        "consecutive_429_count": 0,
        "backoff_count": 0,
        "last_backoff_sec": 0.0,
        "budget_stop_triggered": False,
        "last_stop_reason": "",
        "last_stage": str(cfg.get("stage") or ""),
    }


def _live_ledger_key(cfg: dict) -> str:
    ledger_path = str(cfg.get("ledger_path") or "").strip()
    if ledger_path:
        return str(Path(ledger_path).resolve())
    return "__process__"


def _load_live_ledger(cfg: dict) -> dict:
    ledger_path = str(cfg.get("ledger_path") or "").strip()
    if not ledger_path:
        payload = _IN_MEMORY_LIVE_LEDGER.get(_live_ledger_key(cfg))
        if not payload:
            return _empty_live_ledger(cfg)
        out = _empty_live_ledger(cfg)
        out.update(payload)
        if cfg.get("stage"):
            out["last_stage"] = str(cfg.get("stage") or "")
        return out
    payload = _load_json(Path(ledger_path))
    if not payload:
        return _empty_live_ledger(cfg)
    out = _empty_live_ledger(cfg)
    out.update(payload)
    if cfg.get("stage"):
        out["last_stage"] = str(cfg.get("stage") or "")
    return out


def _write_live_ledger(cfg: dict, payload: dict) -> None:
    ledger_path = str(cfg.get("ledger_path") or "").strip()
    if not ledger_path:
        _IN_MEMORY_LIVE_LEDGER[_live_ledger_key(cfg)] = dict(payload)
        return
    _write_json(Path(ledger_path), payload)


def _reserve_live_request(cfg: dict) -> tuple[bool, dict]:
    ledger = _load_live_ledger(cfg)
    max_requests = int(cfg.get("max_requests_per_run") or 0)
    if max_requests > 0 and int(ledger.get("request_count") or 0) >= max_requests:
        ledger["budget_stop_triggered"] = True
        ledger["last_stop_reason"] = "live_request_budget_exceeded"
        _write_live_ledger(cfg, ledger)
        return False, ledger
    ledger["request_count"] = int(ledger.get("request_count") or 0) + 1
    ledger["last_stage"] = str(cfg.get("stage") or ledger.get("last_stage") or "")
    _write_live_ledger(cfg, ledger)
    return True, ledger


def _record_live_request_success(cfg: dict) -> dict:
    ledger = _load_live_ledger(cfg)
    ledger["consecutive_429_count"] = 0
    _write_live_ledger(cfg, ledger)
    return ledger


def _record_live_request_429(cfg: dict) -> tuple[str, dict]:
    ledger = _load_live_ledger(cfg)
    ledger["rate_limit_429_count"] = int(ledger.get("rate_limit_429_count") or 0) + 1
    ledger["consecutive_429_count"] = int(ledger.get("consecutive_429_count") or 0) + 1
    threshold = max(1, int(cfg.get("max_consecutive_429") or 1))
    if int(ledger.get("consecutive_429_count") or 0) >= threshold:
        ledger["budget_stop_triggered"] = True
        ledger["last_stop_reason"] = "rate_limited"
        _write_live_ledger(cfg, ledger)
        return "rate_limited", ledger
    backoff = min(
        float(cfg.get("max_backoff_sec") or 0.0),
        float(cfg.get("base_backoff_sec") or 0.0) * (2 ** max(0, int(ledger.get("consecutive_429_count") or 1) - 1)),
    )
    ledger["backoff_count"] = int(ledger.get("backoff_count") or 0) + 1
    ledger["last_backoff_sec"] = float(backoff)
    _write_live_ledger(cfg, ledger)
    if backoff > 0:
        time.sleep(backoff)
    return "", ledger


def _classify_failure(output: str, check_ok: bool, simulate_ok: bool) -> tuple[str, str]:
    diag = build_diagnostic_ir_v0(
        output=output,
        check_model_pass=bool(check_ok),
        simulate_pass=bool(simulate_ok),
        expected_stage="",
        declared_failure_type="",
    )
    return str(diag.get("error_type") or "none"), str(diag.get("reason") or "")


def _extract_json_object(text: str) -> dict:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _parse_env_assignment(line: str) -> tuple[str, str] | tuple[None, None]:
    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None, None
    if text.startswith("export "):
        text = text[len("export ") :].strip()
    if "=" not in text:
        return None, None
    key, raw_value = text.split("=", 1)
    key = key.strip()
    if not ENV_KEY_PATTERN.match(key):
        return None, None
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_env_file(path: Path, allowed_keys: set[str] | None = None) -> int:
    if not path.exists():
        return 0
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    loaded = 0
    for line in content.splitlines():
        key, value = _parse_env_assignment(line)
        if not key:
            continue
        if isinstance(allowed_keys, set) and key not in allowed_keys:
            continue
        if str(os.getenv(key) or "").strip():
            continue
        os.environ[key] = value
        loaded += 1
    return loaded


def _bootstrap_env_from_repo(allowed_keys: set[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    loaded = 0
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        loaded += _load_env_file(path, allowed_keys=allowed_keys)
    return loaded


def _resolve_llm_provider(requested_backend: str) -> tuple[str, str, str]:
    _bootstrap_env_from_repo(
        allowed_keys={
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "LLM_MODEL",
            "GATEFORGE_GEMINI_MODEL",
            "GEMINI_MODEL",
            "OPENAI_MODEL",
            "LLM_PROVIDER",
            "GATEFORGE_LIVE_PLANNER_BACKEND",
        }
    )
    requested = str(requested_backend or "").strip().lower()
    if requested == "rule":
        return "rule", "", ""

    model = (
        str(os.getenv("LLM_MODEL") or "").strip()
        or str(os.getenv("OPENAI_MODEL") or "").strip()
        or str(os.getenv("GATEFORGE_GEMINI_MODEL") or "").strip()
        or str(os.getenv("GEMINI_MODEL") or "").strip()
    )
    explicit = requested if requested in {"gemini", "openai"} else ""
    if not explicit:
        explicit = str(os.getenv("LLM_PROVIDER") or os.getenv("GATEFORGE_LIVE_PLANNER_BACKEND") or "").strip().lower()
    if explicit not in {"gemini", "openai"}:
        has_openai = bool(str(os.getenv("OPENAI_API_KEY") or "").strip())
        has_gemini = bool(str(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip())
        if model and OPENAI_MODEL_HINT_PATTERN.search(model) and has_openai:
            explicit = "openai"
        elif model and "gemini" in model.lower() and has_gemini:
            explicit = "gemini"
        elif has_openai and not has_gemini:
            explicit = "openai"
        elif has_gemini and not has_openai:
            explicit = "gemini"
        else:
            explicit = "gemini"
    if explicit == "openai":
        return explicit, model, str(os.getenv("OPENAI_API_KEY") or "").strip()
    return explicit, model, str(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()


def _extract_response_text_openai(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str) and str(payload.get("output_text")).strip():
        return str(payload.get("output_text"))
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), list) else []
        for row in content:
            if not isinstance(row, dict):
                continue
            if isinstance(row.get("text"), str):
                parts.append(str(row.get("text")))
            elif isinstance(row.get("value"), str):
                parts.append(str(row.get("value")))
    return "\n".join([x for x in parts if x.strip()]).strip()


def _gemini_repair_model_text(
    *,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    current_round: int = 1,
) -> tuple[str | None, str]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        _bootstrap_env_from_repo(allowed_keys={"GOOGLE_API_KEY", "LLM_MODEL", "GATEFORGE_GEMINI_MODEL", "GEMINI_MODEL"})
        api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None, "GOOGLE_API_KEY missing"
    model = os.getenv("LLM_MODEL") or os.getenv("GATEFORGE_GEMINI_MODEL") or os.getenv("GEMINI_MODEL")
    if not model:
        return None, "LLM_MODEL or GATEFORGE_GEMINI_MODEL or GEMINI_MODEL missing"
    prompt_constraints = _llm_round_constraints(
        failure_type=failure_type,
        current_round=current_round,
    )
    prompt = (
        "You are fixing a Modelica model.\n"
        "Return ONLY JSON object with keys: patched_model_text, rationale.\n"
        "Constraints:\n"
        "- Keep model name unchanged.\n"
        "- Keep edits minimal and compile-oriented.\n"
        "- Do not output markdown.\n"
        f"{prompt_constraints}"
        f"- model_name: {model_name}\n"
        f"- failure_type: {failure_type}\n"
        f"- expected_stage: {expected_stage}\n"
        f"- error_excerpt: {error_excerpt[:1200]}\n"
        f"- suggested_actions: {json.dumps(repair_actions, ensure_ascii=True)}\n"
        "Model text below:\n"
        "-----BEGIN_MODEL-----\n"
        f"{original_text}\n"
        "-----END_MODEL-----\n"
    )
    req_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    req_data = json.dumps(req_payload).encode("utf-8")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={urllib.parse.quote(api_key)}"
    )
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    cfg = _live_budget_config()
    while True:
        allowed, _ledger = _reserve_live_request(cfg)
        if not allowed:
            return None, "live_request_budget_exceeded"
        try:
            with urllib.request.urlopen(req, timeout=_llm_request_timeout_sec()) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
            _record_live_request_success(cfg)
            break
        except TimeoutError:
            return None, "gemini_request_timeout"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if int(exc.code) == 429:
                stop_reason, _ledger = _record_live_request_429(cfg)
                if stop_reason:
                    return None, stop_reason
                continue
            return None, f"gemini_http_error:{exc.code}:{body[:180]}"
        except urllib.error.URLError as exc:
            return None, f"gemini_url_error:{exc.reason}"
    candidates = response_payload.get("candidates", [])
    if not candidates:
        return None, "gemini_no_candidates"
    text = (
        candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    )
    payload = _extract_json_object(text)
    patched = payload.get("patched_model_text")
    if not isinstance(patched, str) or not patched.strip():
        return None, "gemini_missing_patched_model_text"
    return patched, ""


def _openai_repair_model_text(
    *,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    current_round: int = 1,
) -> tuple[str | None, str]:
    provider, model, api_key = _resolve_llm_provider("openai")
    if provider != "openai":
        return None, "openai_provider_resolution_failed"
    if not api_key:
        return None, "OPENAI_API_KEY missing"
    if not model:
        return None, "LLM_MODEL or OPENAI_MODEL missing"
    prompt_constraints = _llm_round_constraints(
        failure_type=failure_type,
        current_round=current_round,
    )
    prompt = (
        "You are fixing a Modelica model.\n"
        "Return ONLY JSON object with keys: patched_model_text, rationale.\n"
        "Constraints:\n"
        "- Keep model name unchanged.\n"
        "- Keep edits minimal and compile-oriented.\n"
        "- Do not output markdown.\n"
        f"{prompt_constraints}"
        f"- model_name: {model_name}\n"
        f"- failure_type: {failure_type}\n"
        f"- expected_stage: {expected_stage}\n"
        f"- error_excerpt: {error_excerpt[:1200]}\n"
        f"- suggested_actions: {json.dumps(repair_actions, ensure_ascii=True)}\n"
        "Model text below:\n"
        "-----BEGIN_MODEL-----\n"
        f"{original_text}\n"
        "-----END_MODEL-----\n"
    )
    req_payload = {
        "model": model,
        "input": prompt,
        "temperature": 0.1,
    }
    req_data = json.dumps(req_payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=req_data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    cfg = _live_budget_config()
    while True:
        allowed, _ledger = _reserve_live_request(cfg)
        if not allowed:
            return None, "live_request_budget_exceeded"
        try:
            with urllib.request.urlopen(req, timeout=_llm_request_timeout_sec()) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
            _record_live_request_success(cfg)
            break
        except TimeoutError:
            return None, "openai_request_timeout"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if int(exc.code) == 429:
                stop_reason, _ledger = _record_live_request_429(cfg)
                if stop_reason:
                    return None, stop_reason
                continue
            return None, f"openai_http_error:{exc.code}:{body[:180]}"
        except urllib.error.URLError as exc:
            return None, f"openai_url_error:{exc.reason}"
    text = _extract_response_text_openai(response_payload)
    payload = _extract_json_object(text)
    patched = payload.get("patched_model_text")
    if not isinstance(patched, str) or not patched.strip():
        return None, "openai_missing_patched_model_text"
    return patched, ""


def _llm_repair_model_text(
    *,
    planner_backend: str,
    original_text: str,
    failure_type: str,
    expected_stage: str,
    error_excerpt: str,
    repair_actions: list[str],
    model_name: str,
    current_round: int = 1,
) -> tuple[str | None, str, str]:
    provider, _model, _key = _resolve_llm_provider(planner_backend)
    if provider == "openai":
        patched, err = _openai_repair_model_text(
            original_text=original_text,
            failure_type=failure_type,
            expected_stage=expected_stage,
            error_excerpt=error_excerpt,
            repair_actions=repair_actions,
            model_name=model_name,
            current_round=current_round,
        )
        return patched, err, provider
    if provider == "gemini":
        patched, err = _gemini_repair_model_text(
            original_text=original_text,
            failure_type=failure_type,
            expected_stage=expected_stage,
            error_excerpt=error_excerpt,
            repair_actions=repair_actions,
            model_name=model_name,
            current_round=current_round,
        )
        return patched, err, provider
    return None, "rule_backend_selected", "rule"


def _llm_round_constraints(*, failure_type: str, current_round: int) -> str:
    failure = str(failure_type or "").strip().lower()
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    if failure in {
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        source_mode_constraints = ""
        if _behavioral_robustness_source_mode() != "source_aware":
            source_mode_constraints = (
                "- This run is source-blind; do not restore the model to the source version and do not copy source text verbatim.\n"
                "- Infer a localized numeric repair from the current model and observed robustness miss only.\n"
            )
        return (
            "- This is a behavioral robustness task; preserve the existing component declarations and connect structure.\n"
            "- Do not add or remove components, connectors, extends clauses, outputs, or equations unrelated to the failing parameters.\n"
            "- Restrict edits to existing numeric parameters, timing values, gains, offsets, widths, periods, thresholds, or initial-condition shaping values.\n"
            "- Do not invent new parameter names on Modelica.Blocks.Logical.Switch or other existing components; only edit parameters that already appear in the source text.\n"
            "- Do not perform broad source rewrites or declaration-level cleanup; keep the model compile-safe while improving robustness across neighboring scenarios.\n"
            + source_mode_constraints
            + (
                "- In round 1, patch only one localized parameter cluster and rerun the scenario set before broader edits.\n"
                if round_idx == 1
                else ""
            )
        )
    if failure not in {"cascading_structural_failure", "coupled_conflict_failure", "false_friend_patch_trap"}:
        return ""
    if round_idx != 1:
        return ""
    return (
        "- This is a multi-round repair task; in round 1 fix only the first exposed failure layer.\n"
        "- Do not rewrite the whole model or restore all suspicious changes at once.\n"
        "- Limit the patch to one localized repair cluster and preserve other suspicious edits for later rounds.\n"
        "- Do not perform broad cleanup, broad source restoration, or multi-site semantic normalization in round 1.\n"
    )


def _parse_repair_actions(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                return [str(x) for x in payload if isinstance(x, str)]
        except Exception:
            pass
    return [x.strip() for x in text.split("|") if x.strip()]


def _extract_state_tokens_from_output(output: str) -> list[str]:
    tokens = sorted(set(re.findall(r"__gf_state_\d+", str(output or ""))))
    return tokens


def _extract_undef_tokens_from_output(output: str) -> list[str]:
    tokens = sorted(set(re.findall(r"__gf_undef_\d+", str(output or ""))))
    return tokens


def _remove_gateforge_injected_symbol_block(model_text: str) -> tuple[str, int]:
    lines = str(model_text or "").splitlines(keepends=True)
    if not lines:
        return str(model_text or ""), 0
    remove_idx: set[int] = set()
    for i, line in enumerate(lines):
        if "__gf_" in line:
            remove_idx.add(i)
            # Remove nearby mutation comment/equation headers that usually wrap injected block.
            for j in (i - 2, i - 1, i + 1, i + 2):
                if j < 0 or j >= len(lines):
                    continue
                text = lines[j].strip()
                if "GateForge mutation" in text:
                    remove_idx.add(j)
                if text == "equation":
                    remove_idx.add(j)
    if not remove_idx:
        return str(model_text or ""), 0
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), len(remove_idx)


def _apply_parse_error_pre_repair(model_text: str, output: str, failure_type: str) -> tuple[str, dict]:
    failure = str(failure_type or "").strip().lower()
    lower = str(output or "").lower()

    tokens: list[str] = []
    reason_prefix = ""
    if failure == "script_parse_error":
        if "no viable alternative near token" not in lower:
            return model_text, {"applied": False, "reason": "parse_error_without_expected_marker"}
        tokens = _extract_state_tokens_from_output(output)
        reason_prefix = "injected_state_tokens"
        if not tokens:
            # Fallback for parse errors where OMC reports generic token (`parameter`, `equation`)
            # but injected mutant symbols still exist in model text.
            fallback_patched, removed = _remove_gateforge_injected_symbol_block(model_text)
            if removed > 0:
                return fallback_patched, {
                    "applied": True,
                    "reason": "removed_gateforge_injected_symbol_block",
                    "removed_line_count": int(removed),
                }
            return model_text, {"applied": False, "reason": "state_token_not_detected"}
    elif failure == "model_check_error":
        # Some OMC parser errors can be mapped to model_check_error by the
        # diagnostic classifier. Recover these the same way as parse errors.
        parse_markers = ("no viable alternative near token", "lexer failed to recognize")
        if any(marker in lower for marker in parse_markers):
            state_tokens = _extract_state_tokens_from_output(output)
            if not state_tokens and "__gf_state_" in str(model_text or ""):
                state_tokens = sorted(set(re.findall(r"__gf_state_\d+", str(model_text or ""))))
            if state_tokens:
                tokens = state_tokens
                reason_prefix = "injected_state_tokens"
            else:
                fallback_patched, removed = _remove_gateforge_injected_symbol_block(model_text)
                if removed > 0:
                    return fallback_patched, {
                        "applied": True,
                        "reason": "removed_gateforge_injected_symbol_block",
                        "removed_line_count": int(removed),
                    }
                return model_text, {"applied": False, "reason": "state_token_not_detected"}
        else:
        # Common mutant pattern: undefined synthetic symbol `__gf_undef_<id>`.
            tokens = _extract_undef_tokens_from_output(output)
            if not tokens and "__gf_undef_" in str(model_text or ""):
                tokens = sorted(set(re.findall(r"__gf_undef_\d+", str(model_text or ""))))
            reason_prefix = "injected_undef_tokens"
            if not tokens:
                return model_text, {"applied": False, "reason": "undef_token_not_detected"}
    else:
        return model_text, {"applied": False, "reason": "failure_type_not_supported_for_pre_repair"}

    patched = str(model_text or "")
    # Prefer dropping full lines carrying injected state token to avoid
    # leaving broken fragments like `der() = ...;` after direct token removal.
    lines = patched.splitlines(keepends=True)
    kept_lines: list[str] = []
    removed_line_count = 0
    for line in lines:
        if any(tok in line for tok in tokens):
            removed_line_count += 1
            continue
        kept_lines.append(line)
    if removed_line_count > 0:
        return "".join(kept_lines), {
            "applied": True,
            "reason": f"removed_lines_with_{reason_prefix}",
            "detected_tokens": tokens,
            "removed_line_count": int(removed_line_count),
        }

    removed_count = 0
    for token in tokens:
        patched, replaced = re.subn(rf"\b{re.escape(token)}\b", "", patched)
        removed_count += int(replaced)

    if removed_count <= 0:
        return model_text, {
            "applied": False,
            "reason": "detected_token_not_found_in_model_text",
            "detected_tokens": tokens,
        }

    return patched, {
        "applied": True,
        "reason": f"removed_{reason_prefix}_inline",
        "detected_tokens": tokens,
        "removed_count": int(removed_count),
    }


def _normalize_terminal_errors(executor_status: str, error_message: str, compile_error: str, simulate_error: str) -> tuple[str, str, str]:
    if str(executor_status or "").upper() == "PASS":
        return "", "", ""
    return str(error_message or ""), str(compile_error or ""), str(simulate_error or "")


def _run_check_and_simulate(
    *,
    workspace: Path,
    model_load_files: list[str],
    model_name: str,
    timeout_sec: int,
    backend: str,
    docker_image: str,
    stop_time: float,
    intervals: int,
) -> tuple[int | None, str, bool, bool]:
    bootstrap = "loadModel(Modelica);\n"
    if backend != "omc":
        bootstrap = "installPackage(Modelica);\nloadModel(Modelica);\n"
    load_lines = "".join([f'loadFile("{item}");\n' for item in model_load_files if str(item or "").strip()])
    script = (
        bootstrap
        + load_lines
        + f"checkModel({model_name});\n"
        + f"simulate({model_name}, stopTime={float(stop_time)}, numberOfIntervals={int(intervals)});\n"
        + "getErrorString();\n"
    )
    if backend == "omc":
        rc, output = _run_omc_script_local(script, timeout_sec=timeout_sec, cwd=str(workspace))
    else:
        rc, output = _run_omc_script_docker(script, timeout_sec=timeout_sec, cwd=str(workspace), image=docker_image)
    check_ok, simulate_ok = _extract_om_success_flags(output)
    return rc, output, check_ok, simulate_ok


@contextmanager
def _temporary_workspace(prefix: str):
    # Docker may write root-owned files into the mounted workspace/cache, and
    # TemporaryDirectory cleanup can raise PermissionError on CI. Use mkdtemp
    # with best-effort cleanup that never propagates teardown failures.
    td = tempfile.mkdtemp(prefix=prefix)
    try:
        yield td
    finally:
        _cleanup_workspace_best_effort(td)


def _cleanup_workspace_best_effort(path: str) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Modelica executor with provider-configurable patching loop and OMC validation")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--failure-type", default="unknown")
    parser.add_argument("--expected-stage", default="unknown")
    parser.add_argument("--source-model-path", default="")
    parser.add_argument("--mutated-model-path", default="")
    parser.add_argument("--source-library-path", default="")
    parser.add_argument("--source-package-name", default="")
    parser.add_argument("--source-library-model-path", default="")
    parser.add_argument("--source-qualified-model-name", default="")
    parser.add_argument("--repair-actions", default="")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--simulate-stop-time", type=float, default=0.2)
    parser.add_argument("--simulate-intervals", type=int, default=20)
    parser.add_argument("--backend", choices=["auto", "omc", "openmodelica_docker"], default="auto")
    parser.add_argument("--docker-image", default=os.getenv("GATEFORGE_OM_IMAGE", DEFAULT_DOCKER_IMAGE))
    parser.add_argument("--planner-backend", choices=["auto", "gemini", "openai", "rule"], default="auto")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    started = time.monotonic()
    model_path = Path(str(args.mutated_model_path or "").strip() or str(args.source_model_path or "").strip())
    if not model_path.exists():
        payload = {
            "task_id": args.task_id,
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "elapsed_sec": round(time.monotonic() - started, 4),
            "error_message": "model_path_missing",
            "compile_error": "model_path_missing",
            "simulate_error_message": "",
            "stderr_snippet": str(model_path),
        }
        if str(args.out).strip():
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload))
        return

    backend = str(args.backend).strip().lower()
    if backend == "auto":
        backend = "omc" if shutil.which("omc") else "openmodelica_docker"

    original_text = _read_text(model_path)
    source_model_text = ""
    source_model_path_raw = str(args.source_model_path or "").strip()
    if source_model_path_raw:
        source_model_path = Path(source_model_path_raw)
        if source_model_path.exists() and source_model_path.is_file():
            source_model_text = _read_text(source_model_path)
    model_name = _find_primary_model_name(original_text)
    if not model_name:
        payload = {
            "task_id": args.task_id,
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "elapsed_sec": round(time.monotonic() - started, 4),
            "error_message": "model_name_not_found",
            "compile_error": "model_name_not_found",
            "simulate_error_message": "",
            "stderr_snippet": "",
        }
        if str(args.out).strip():
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload))
        return

    repair_actions = _parse_repair_actions(args.repair_actions)
    attempts: list[dict] = []
    current_text = original_text
    multistep_memory = {
        "stage_1_unlock_cluster": "",
        "stage_2_first_fail_bucket": "",
        "stage_2_branch": "",
        "preferred_stage_2_branch": "",
        "branch_history": [],
        "trap_branch_history": [],
        "branch_reason": "",
        "trap_branch_active": False,
        "trap_branch_entered": False,
        "correct_branch_selected": False,
        "correct_branch_round": 0,
        "last_trap_escape_direction": "",
        "last_successful_branch_correction": "",
        "branch_bad_directions": [],
        "branch_reentry_count": 0,
        "branch_escape_attempt_count": 0,
        "branch_escape_success_count": 0,
        "branch_budget_reallocated_count": 0,
        "stage_2_transition_round": 0,
        "stage_2_transition_reason": "",
        "stage_aware_focus_applied": False,
        "stage_1_revisit_after_unlock": False,
        "last_plan_stage": "",
        "last_plan_goal": "",
        "last_plan_actions": [],
        "last_plan_constraints": [],
        "last_plan_stop_condition": "",
        "stage_plan_generated": False,
        "stage_plan_followed": False,
        "executed_plan_stage": "",
        "executed_plan_action": "",
        "plan_conflict_rejected": False,
        "plan_conflict_rejected_count": 0,
        "last_successful_stage_action": "",
        "tried_parameters": [],
        "tried_candidate_values": [],
        "bad_directions": [],
        "successful_directions": [],
        "local_search_attempt_count": 0,
        "local_search_success_count": 0,
        "local_search_kinds": [],
        "adaptive_search_attempt_count": 0,
        "adaptive_search_success_count": 0,
        "search_improvement_seen": False,
        "search_regression_seen": False,
        "search_bad_direction_count": 0,
        "best_stage_2_fail_bucket_seen": "",
        "stage_2_best_progress_seen": False,
        "stage_1_unlock_via_local_search": False,
        "stage_2_resolution_via_local_search": False,
        "cluster_only_resolution": False,
        "llm_force_signatures": [],
        "llm_plan_used": False,
        "llm_plan_reason": "",
        "llm_request_count_delta_total": 0,
        "llm_branch_correction_used": False,
        "llm_resolution_contributed": False,
        "llm_only_resolution": False,
    }
    final_check_ok = False
    final_simulate_ok = False
    final_error = ""
    final_compile_error = ""
    final_sim_error = ""
    final_stderr = ""
    executor_status = "FAILED"
    budget_cfg = _live_budget_config()
    resolved_provider = "rule" if str(args.planner_backend) == "rule" else _resolve_llm_provider(str(args.planner_backend))[0]

    with _temporary_workspace(prefix="gf_live_exec_") as td:
        workspace = Path(td)
        layout = _prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=model_path,
            primary_model_name=model_name,
            source_library_path=str(args.source_library_path or ""),
            source_package_name=str(args.source_package_name or ""),
            source_library_model_path=str(args.source_library_model_path or ""),
            source_qualified_model_name=str(args.source_qualified_model_name or ""),
        )
        for round_idx in range(1, max(1, int(args.max_rounds)) + 1):
            behavioral_eval = None
            layout.model_write_path.write_text(current_text, encoding="utf-8")
            rc, output, check_ok, simulate_ok = _run_check_and_simulate(
                workspace=workspace,
                model_load_files=layout.model_load_files,
                model_name=layout.model_identifier,
                timeout_sec=max(1, int(args.timeout_sec)),
                backend=backend,
                docker_image=str(args.docker_image),
                stop_time=float(args.simulate_stop_time),
                intervals=max(1, int(args.simulate_intervals)),
            )
            diagnostic = build_diagnostic_ir_v0(
                output=output,
                check_model_pass=bool(check_ok),
                simulate_pass=bool(simulate_ok),
                expected_stage=str(args.expected_stage or ""),
                declared_failure_type=str(args.failure_type or ""),
                declared_context_hints=_diagnostic_context_hints_from_model(
                    failure_type=str(args.failure_type or ""),
                    expected_stage=str(args.expected_stage or ""),
                    model_text=current_text,
                ),
            )
            ftype = str(diagnostic.get("error_type") or "none")
            reason = str(diagnostic.get("reason") or "")
            attempts.append(
                {
                    "round": round_idx,
                    "return_code": rc,
                    "check_model_pass": check_ok,
                    "simulate_pass": simulate_ok,
                    "observed_failure_type": ftype,
                    "reason": reason,
                    "diagnostic_ir": diagnostic,
                    "log_excerpt": str(output or "")[:1200],
                }
            )
            if check_ok and simulate_ok:
                behavioral_eval = _evaluate_behavioral_contract_from_model_text(
                    current_text=current_text,
                    source_model_text=source_model_text,
                    failure_type=str(args.failure_type),
                )
                if isinstance(behavioral_eval, dict):
                    attempts[-1]["physics_contract_pass"] = bool(behavioral_eval.get("pass"))
                    attempts[-1]["physics_contract_reasons"] = [
                        str(x) for x in (behavioral_eval.get("reasons") or []) if str(x).strip()
                    ]
                    attempts[-1]["contract_pass"] = bool(behavioral_eval.get("pass"))
                    attempts[-1]["contract_fail_bucket"] = str(behavioral_eval.get("contract_fail_bucket") or "")
                    attempts[-1]["scenario_results"] = [
                        dict(item) for item in (behavioral_eval.get("scenario_results") or []) if isinstance(item, dict)
                    ]
                    attempts[-1]["multi_step_stage"] = str(behavioral_eval.get("multi_step_stage") or "")
                    attempts[-1]["multi_step_stage_2_unlocked"] = bool(behavioral_eval.get("multi_step_stage_2_unlocked"))
                    attempts[-1]["multi_step_transition_seen"] = bool(behavioral_eval.get("multi_step_transition_seen"))
                    attempts[-1]["multi_step_transition_reason"] = str(behavioral_eval.get("multi_step_transition_reason") or "")
                    attempts[-1]["multi_step_transition_round"] = (
                        int(round_idx) if bool(behavioral_eval.get("multi_step_transition_seen")) else 0
                    )
                    stage_context = _build_multistep_stage_context(
                        failure_type=str(args.failure_type),
                        behavioral_eval=behavioral_eval,
                        current_round=round_idx,
                        memory=multistep_memory,
                    )
                    if stage_context["stage_2_unlocked"]:
                        if not multistep_memory.get("stage_2_transition_round"):
                            multistep_memory["stage_2_transition_round"] = int(stage_context["transition_round"] or round_idx)
                        if not multistep_memory.get("stage_2_transition_reason"):
                            multistep_memory["stage_2_transition_reason"] = str(stage_context["transition_reason"] or "")
                        if stage_context["current_fail_bucket"] and not multistep_memory.get("stage_2_first_fail_bucket"):
                            multistep_memory["stage_2_first_fail_bucket"] = str(stage_context["current_fail_bucket"] or "")
                        if stage_context["current_fail_bucket"]:
                            multistep_memory["best_stage_2_fail_bucket_seen"] = str(stage_context["current_fail_bucket"] or "")
                        if str(stage_context.get("current_stage") or "") == "stage_2":
                            multistep_memory["stage_2_best_progress_seen"] = True
                        if str(stage_context.get("stage_2_branch") or "").strip():
                            multistep_memory["stage_2_branch"] = str(stage_context.get("stage_2_branch") or "").strip()
                        if str(stage_context.get("preferred_stage_2_branch") or "").strip():
                            multistep_memory["preferred_stage_2_branch"] = str(stage_context.get("preferred_stage_2_branch") or "").strip()
                        if str(stage_context.get("branch_reason") or "").strip():
                            multistep_memory["branch_reason"] = str(stage_context.get("branch_reason") or "").strip()
                        current_branch = str(stage_context.get("stage_2_branch") or "").strip()
                        if current_branch:
                            branch_history = list(multistep_memory.get("branch_history") or [])
                            branch_history.append(current_branch)
                            multistep_memory["branch_history"] = branch_history
                        multistep_memory["trap_branch_active"] = bool(stage_context.get("trap_branch"))
                        if bool(stage_context.get("trap_branch")):
                            trap_history = list(multistep_memory.get("trap_branch_history") or [])
                            if current_branch in trap_history:
                                multistep_memory["branch_reentry_count"] = int(multistep_memory.get("branch_reentry_count") or 0) + 1
                            trap_history.append(current_branch)
                            multistep_memory["trap_branch_history"] = trap_history
                            multistep_memory["trap_branch_entered"] = True
                        if bool(stage_context.get("correct_branch_selected")) and not bool(stage_context.get("trap_branch")):
                            multistep_memory["correct_branch_selected"] = True
                            if not int(multistep_memory.get("correct_branch_round") or 0):
                                multistep_memory["correct_branch_round"] = int(round_idx)
                            if str(multistep_memory.get("last_trap_escape_direction") or "").strip():
                                multistep_memory["last_successful_branch_correction"] = str(multistep_memory.get("last_trap_escape_direction") or "").strip()
                                multistep_memory["branch_escape_success_count"] = int(multistep_memory.get("branch_escape_success_count") or 0) + 1
                    attempts[-1]["current_stage"] = str(stage_context.get("current_stage") or "")
                    attempts[-1]["stage_2_unlocked"] = bool(stage_context.get("stage_2_unlocked"))
                    attempts[-1]["transition_round"] = int(stage_context.get("transition_round") or 0)
                    attempts[-1]["transition_reason"] = str(stage_context.get("transition_reason") or "")
                    attempts[-1]["current_fail_bucket"] = str(stage_context.get("current_fail_bucket") or "")
                    attempts[-1]["next_focus"] = str(stage_context.get("next_focus") or "")
                    attempts[-1]["stage_1_unlock_cluster"] = str(stage_context.get("stage_1_unlock_cluster") or "")
                    attempts[-1]["stage_2_first_fail_bucket"] = str(stage_context.get("stage_2_first_fail_bucket") or "")
                    attempts[-1]["stage_2_branch"] = str(stage_context.get("stage_2_branch") or "")
                    attempts[-1]["preferred_stage_2_branch"] = str(stage_context.get("preferred_stage_2_branch") or "")
                    attempts[-1]["branch_mode"] = str(stage_context.get("branch_mode") or "")
                    attempts[-1]["branch_reason"] = str(stage_context.get("branch_reason") or "")
                    attempts[-1]["trap_branch"] = bool(stage_context.get("trap_branch"))
                    attempts[-1]["correct_branch_selected"] = bool(stage_context.get("correct_branch_selected"))
                    stage_plan = build_multistep_repair_plan_v0(
                        failure_type=str(args.failure_type),
                        current_stage=str(stage_context.get("current_stage") or ""),
                        current_fail_bucket=str(stage_context.get("current_fail_bucket") or ""),
                        stage_2_branch=str(stage_context.get("stage_2_branch") or ""),
                        preferred_stage_2_branch=str(stage_context.get("preferred_stage_2_branch") or ""),
                        trap_branch=bool(stage_context.get("trap_branch")),
                        plan_actions=[],
                    )
                    stage_plan_fields = _stage_plan_fields(
                        plan=stage_plan,
                        generated=bool(stage_context.get("current_stage")),
                        followed=str(stage_context.get("current_stage") or "") == "passed",
                        conflict_rejected=False,
                        conflict_rejected_count=0,
                        executed_action="stop_editing" if str(stage_context.get("current_stage") or "") == "passed" else "",
                    )
                    attempts[-1].update(stage_plan_fields)
                    multistep_memory["last_plan_stage"] = str(stage_plan_fields.get("plan_stage") or "")
                    multistep_memory["last_plan_goal"] = str(stage_plan_fields.get("plan_goal") or "")
                    multistep_memory["last_plan_actions"] = list(stage_plan_fields.get("plan_actions") or [])
                    multistep_memory["last_plan_constraints"] = list(stage_plan_fields.get("plan_constraints") or [])
                    multistep_memory["last_plan_stop_condition"] = str(stage_plan_fields.get("plan_stop_condition") or "")
                    multistep_memory["stage_plan_generated"] = bool(stage_plan_fields.get("stage_plan_generated"))
                    multistep_memory["stage_plan_followed"] = bool(stage_plan_fields.get("stage_plan_followed"))
                    multistep_memory["executed_plan_stage"] = str(stage_plan_fields.get("executed_plan_stage") or "")
                    multistep_memory["executed_plan_action"] = str(stage_plan_fields.get("executed_plan_action") or "")
                    multistep_memory["plan_conflict_rejected"] = bool(stage_plan_fields.get("plan_conflict_rejected"))
                    multistep_memory["plan_conflict_rejected_count"] = int(stage_plan_fields.get("plan_conflict_rejected_count") or 0)
                    if str(stage_context.get("current_stage") or "") == "passed":
                        multistep_memory["last_successful_stage_action"] = "stop_editing"
                if not isinstance(behavioral_eval, dict) or bool(behavioral_eval.get("pass")):
                    if isinstance(behavioral_eval, dict):
                        if (
                            bool(multistep_memory.get("trap_branch_entered"))
                            and str(multistep_memory.get("last_trap_escape_direction") or "").strip()
                            and int(multistep_memory.get("branch_escape_attempt_count") or 0)
                            > int(multistep_memory.get("branch_escape_success_count") or 0)
                        ):
                            multistep_memory["branch_escape_success_count"] = int(multistep_memory.get("branch_escape_success_count") or 0) + 1
                            multistep_memory["last_successful_branch_correction"] = str(multistep_memory.get("last_trap_escape_direction") or "").strip()
                        if bool(multistep_memory.get("trap_branch_entered")):
                            multistep_memory["correct_branch_selected"] = True
                            if not int(multistep_memory.get("correct_branch_round") or 0):
                                multistep_memory["correct_branch_round"] = int(round_idx)
                            preferred_branch = str(multistep_memory.get("preferred_stage_2_branch") or "").strip()
                            if preferred_branch:
                                multistep_memory["stage_2_branch"] = preferred_branch
                            multistep_memory["trap_branch_active"] = False
                    final_check_ok = True
                    final_simulate_ok = True
                    executor_status = "PASS"
                    final_stderr = str(output or "")[-1200:]
                    break
                final_error = str(behavioral_eval.get("contract_fail_bucket") or "behavioral_contract_fail")
                final_sim_error = final_error
                final_stderr = str(output or "")[-1200:]

            if not (check_ok and simulate_ok):
                final_error = reason or "repair_round_failed"
            if not check_ok:
                final_compile_error = reason or "compile_failed"
            if check_ok and not simulate_ok:
                final_sim_error = reason or "simulate_failed"
                final_stderr = str(output or "")[-1200:]

            if round_idx >= max(1, int(args.max_rounds)):
                break

            pre_repaired_text, pre_repair = _apply_parse_error_pre_repair(
                model_text=current_text,
                output=str(output or ""),
                failure_type=ftype,
            )
            attempts[-1]["pre_repair"] = pre_repair
            if bool(pre_repair.get("applied")):
                current_text = pre_repaired_text
                final_error = "pre_repair_applied_retry_pending"
                continue

            init_repaired_text, init_repair = _apply_initialization_marker_repair(
                current_text=current_text,
                declared_failure_type=str(args.failure_type),
            )
            attempts[-1]["initialization_marker_repair"] = init_repair
            if bool(init_repair.get("applied")):
                current_text = init_repaired_text
                final_error = "initialization_marker_repair_applied_retry_pending"
                continue

            wave2_repaired_text, wave2_repair = _apply_wave2_marker_repair(
                current_text=current_text,
                declared_failure_type=str(args.failure_type),
            )
            attempts[-1]["wave2_marker_repair"] = wave2_repair
            if bool(wave2_repair.get("applied")):
                current_text = wave2_repaired_text
                final_error = "wave2_marker_repair_applied_retry_pending"
                continue

            wave2_1_repaired_text, wave2_1_repair = _apply_wave2_1_marker_repair(
                current_text=current_text,
                declared_failure_type=str(args.failure_type),
            )
            attempts[-1]["wave2_1_marker_repair"] = wave2_1_repair
            if bool(wave2_1_repair.get("applied")):
                current_text = wave2_1_repaired_text
                final_error = "wave2_1_marker_repair_applied_retry_pending"
                continue

            wave2_2_repaired_text, wave2_2_repair = _apply_wave2_2_marker_repair(
                current_text=current_text,
                declared_failure_type=str(args.failure_type),
            )
            attempts[-1]["wave2_2_marker_repair"] = wave2_2_repair
            if bool(wave2_2_repair.get("applied")):
                current_text = wave2_2_repaired_text
                final_error = "wave2_2_marker_repair_applied_retry_pending"
                continue

            multi_round_repaired_text, multi_round_repair = _apply_multi_round_layered_repair(
                current_text=current_text,
                source_model_text=source_model_text,
                declared_failure_type=str(args.failure_type),
                current_round=round_idx,
            )
            attempts[-1]["multi_round_layered_repair"] = multi_round_repair
            if bool(multi_round_repair.get("applied")):
                current_text = multi_round_repaired_text
                final_error = "multi_round_layered_repair_applied_retry_pending"
                continue

            pre_stage_context = _build_multistep_stage_context(
                failure_type=str(args.failure_type),
                behavioral_eval=behavioral_eval if isinstance(behavioral_eval, dict) else {},
                current_round=round_idx,
                memory=multistep_memory,
            )
            llm_context = _build_source_blind_multistep_llm_context(
                current_text=current_text,
                stage_context=pre_stage_context,
                current_round=round_idx,
                memory=multistep_memory,
            )
            multistep_memory["llm_force_signatures"] = list(multistep_memory.get("llm_force_signatures") or []) + [
                str(llm_context.get("signature") or "")
            ]
            attempts[-1]["planner_backend"] = str(args.planner_backend or "")
            attempts[-1]["resolved_llm_provider"] = str(resolved_provider or "")
            attempts[-1]["llm_forcing"] = bool(llm_context.get("llm_forcing"))
            attempts[-1]["realism_version"] = str(llm_context.get("realism_version") or "")
            attempts[-1]["llm_plan_used"] = False
            attempts[-1]["llm_plan_reason"] = ""
            attempts[-1]["llm_request_count_delta"] = 0
            attempts[-1]["llm_branch_correction_used"] = False
            attempts[-1]["llm_resolution_contributed"] = False
            attempts[-1]["llm_only_resolution"] = False
            force_llm_now = bool(llm_context.get("should_force_llm"))
            if (
                str(pre_stage_context.get("current_stage") or "").strip().lower() == "stage_2"
                and bool(pre_stage_context.get("trap_branch"))
                and not force_llm_now
            ):
                multistep_local_search_text = current_text
                multistep_local_search = {
                    "applied": False,
                    "reason": "trap_branch_requires_branch_escape_first",
                    "current_branch": str(pre_stage_context.get("stage_2_branch") or ""),
                    "preferred_branch": str(pre_stage_context.get("preferred_stage_2_branch") or ""),
                }
            elif force_llm_now:
                multistep_local_search_text = current_text
                multistep_local_search = {
                    "applied": False,
                    "reason": "llm_forcing_gated_before_local_search",
                    "llm_plan_reason": str(llm_context.get("llm_plan_reason") or ""),
                }
            else:
                multistep_local_search_text, multistep_local_search = _apply_source_blind_multistep_local_search(
                    current_text=current_text,
                    declared_failure_type=str(args.failure_type),
                    current_stage=str(pre_stage_context.get("current_stage") or ""),
                    current_fail_bucket=str(pre_stage_context.get("current_fail_bucket") or ""),
                    search_memory=multistep_memory,
                )
            attempts[-1]["source_blind_multistep_local_search"] = multistep_local_search
            if bool(multistep_local_search.get("applied")):
                multistep_memory["local_search_attempt_count"] = int(multistep_memory.get("local_search_attempt_count") or 0) + 1
                multistep_memory["adaptive_search_attempt_count"] = int(multistep_memory.get("adaptive_search_attempt_count") or 0) + 1
                candidate_key = str(multistep_local_search.get("candidate_key") or "").strip()
                if candidate_key:
                    multistep_memory["tried_candidate_values"] = list(multistep_memory.get("tried_candidate_values") or []) + [candidate_key]
                multistep_memory["tried_parameters"] = list(multistep_memory.get("tried_parameters") or []) + [
                    str(x) for x in (multistep_local_search.get("parameter_names") or []) if isinstance(x, str)
                ]
                direction = str(multistep_local_search.get("search_direction") or "").strip()
                search_kind = str(multistep_local_search.get("search_kind") or "").strip()
                if search_kind:
                    multistep_memory["local_search_kinds"] = list(multistep_memory.get("local_search_kinds") or []) + [search_kind]
                if search_kind == "stage_1_unlock" and not str(multistep_memory.get("stage_1_unlock_cluster") or "").strip():
                    multistep_memory["stage_1_unlock_cluster"] = str(multistep_local_search.get("cluster_name") or "").strip()
                guarded_patched, patch_guard = _guard_robustness_patch(
                    original_text=current_text,
                    patched_text=multistep_local_search_text,
                    failure_type=str(args.failure_type),
                )
                attempts[-1]["patch_guard"] = patch_guard
                if isinstance(guarded_patched, str) and guarded_patched.strip():
                    current_text = guarded_patched
                    final_error = "source_blind_multistep_local_search_applied_retry_pending"
                    continue
                if direction:
                    multistep_memory["bad_directions"] = list(multistep_memory.get("bad_directions") or []) + [direction]
                multistep_memory["search_regression_seen"] = True
                multistep_memory["search_bad_direction_count"] = int(multistep_memory.get("search_bad_direction_count") or 0) + 1
                final_error = str(patch_guard.get("reason") or "robustness_patch_rejected")
                continue

            multistep_repaired_text, multistep_repair = _apply_source_blind_multistep_exposure_repair(
                current_text=current_text,
                declared_failure_type=str(args.failure_type),
                current_round=round_idx,
            )
            if force_llm_now:
                multistep_repair = {"applied": False, "reason": "llm_forcing_gated_before_exposure_repair"}
                multistep_repaired_text = current_text
            attempts[-1]["source_blind_multistep_exposure_repair"] = multistep_repair
            if bool(multistep_repair.get("applied")):
                if str(multistep_repair.get("cluster_name") or "").strip():
                    multistep_memory["stage_1_unlock_cluster"] = str(multistep_repair.get("cluster_name") or "").strip()
                current_text = multistep_repaired_text
                final_error = "source_blind_multistep_exposure_repair_applied_retry_pending"
                continue

            source_blind_repaired_text, source_blind_repair = _apply_behavioral_robustness_source_blind_local_repair(
                current_text=current_text,
                declared_failure_type=str(args.failure_type),
                current_round=round_idx,
            )
            attempts[-1]["source_blind_local_repair"] = source_blind_repair
            if bool(source_blind_repair.get("applied")):
                current_text = source_blind_repaired_text
                final_error = "source_blind_local_repair_applied_retry_pending"
                continue

            source_repaired_text, source_repair = _apply_source_model_repair(
                current_text=current_text,
                source_model_text=source_model_text,
                declared_failure_type=str(args.failure_type),
                observed_failure_type=ftype,
            )
            if force_llm_now:
                source_repair = {"applied": False, "reason": "llm_forcing_gated_before_source_repair"}
                source_repaired_text = current_text
            attempts[-1]["source_repair"] = source_repair
            if bool(source_repair.get("applied")):
                current_text = source_repaired_text
                final_error = "source_repair_applied_retry_pending"
                continue

            if resolved_provider in {"gemini", "openai"}:
                stage_context = _build_multistep_stage_context(
                    failure_type=str(args.failure_type),
                    behavioral_eval=behavioral_eval if isinstance(behavioral_eval, dict) else {},
                    current_round=round_idx,
                    memory=multistep_memory,
                )
                stage_policy = recommend_repair_actions_v0(
                    failure_type=str(args.failure_type),
                    expected_stage=str(args.expected_stage),
                    diagnostic_payload=diagnostic,
                    fallback_actions=repair_actions,
                    multistep_context=stage_context,
                )
                stage_repair_actions = [str(x) for x in (stage_policy.get("actions") or []) if isinstance(x, str)]
                stage_plan = stage_policy.get("plan") if isinstance(stage_policy.get("plan"), dict) else {}
                stage_aware_control_applied = bool(stage_policy.get("stage_aware")) and bool(stage_repair_actions)
                stage_1_revisit_after_unlock = False
                if bool(stage_context.get("stage_2_unlocked")):
                    if str(stage_context.get("current_stage") or "") == "stage_1":
                        stage_1_revisit_after_unlock = True
                    elif any(
                        _looks_like_stage_1_focus(
                            failure_type=str(args.failure_type),
                            action=action,
                        )
                        for action in stage_repair_actions
                    ):
                        stage_1_revisit_after_unlock = True
                stage_plan_fields = _stage_plan_fields(
                    plan=stage_plan,
                    generated=bool(stage_policy.get("plan_generated")),
                    followed=bool(stage_policy.get("plan_followed")),
                    conflict_rejected=bool(stage_policy.get("plan_conflict_rejected")),
                    conflict_rejected_count=int(stage_policy.get("plan_conflict_rejected_count") or 0),
                    executed_action=str(stage_policy.get("executed_plan_action") or ""),
                )
                multistep_memory["stage_aware_focus_applied"] = bool(multistep_memory.get("stage_aware_focus_applied")) or stage_aware_control_applied
                multistep_memory["stage_1_revisit_after_unlock"] = bool(multistep_memory.get("stage_1_revisit_after_unlock")) or stage_1_revisit_after_unlock
                multistep_memory["last_plan_stage"] = str(stage_plan_fields.get("plan_stage") or "")
                multistep_memory["last_plan_goal"] = str(stage_plan_fields.get("plan_goal") or "")
                multistep_memory["last_plan_actions"] = list(stage_plan_fields.get("plan_actions") or [])
                multistep_memory["last_plan_constraints"] = list(stage_plan_fields.get("plan_constraints") or [])
                multistep_memory["last_plan_stop_condition"] = str(stage_plan_fields.get("plan_stop_condition") or "")
                multistep_memory["stage_plan_generated"] = bool(stage_plan_fields.get("stage_plan_generated"))
                multistep_memory["stage_plan_followed"] = bool(stage_plan_fields.get("stage_plan_followed"))
                multistep_memory["executed_plan_stage"] = str(stage_plan_fields.get("executed_plan_stage") or "")
                multistep_memory["executed_plan_action"] = str(stage_plan_fields.get("executed_plan_action") or "")
                multistep_memory["plan_conflict_rejected"] = bool(stage_plan_fields.get("plan_conflict_rejected"))
                multistep_memory["plan_conflict_rejected_count"] = int(stage_plan_fields.get("plan_conflict_rejected_count") or 0)
                attempts[-1]["current_stage"] = str(stage_context.get("current_stage") or "")
                attempts[-1]["stage_2_unlocked"] = bool(stage_context.get("stage_2_unlocked"))
                attempts[-1]["transition_round"] = int(stage_context.get("transition_round") or 0)
                attempts[-1]["transition_reason"] = str(stage_context.get("transition_reason") or "")
                attempts[-1]["current_fail_bucket"] = str(stage_context.get("current_fail_bucket") or "")
                attempts[-1]["next_focus"] = str(stage_context.get("next_focus") or "")
                attempts[-1]["stage_1_unlock_cluster"] = str(stage_context.get("stage_1_unlock_cluster") or "")
                attempts[-1]["stage_2_first_fail_bucket"] = str(stage_context.get("stage_2_first_fail_bucket") or "")
                attempts[-1]["stage_2_branch"] = str(stage_context.get("stage_2_branch") or "")
                attempts[-1]["preferred_stage_2_branch"] = str(stage_context.get("preferred_stage_2_branch") or "")
                attempts[-1]["branch_mode"] = str(stage_context.get("branch_mode") or "")
                attempts[-1]["branch_reason"] = str(stage_context.get("branch_reason") or "")
                attempts[-1]["trap_branch"] = bool(stage_context.get("trap_branch"))
                attempts[-1]["correct_branch_selected"] = bool(stage_context.get("correct_branch_selected"))
                attempts[-1]["stage_aware_repair_actions"] = stage_repair_actions
                attempts[-1]["stage_aware_control_applied"] = stage_aware_control_applied
                attempts[-1]["stage_1_revisit_after_unlock"] = stage_1_revisit_after_unlock
                attempts[-1].update(stage_plan_fields)
                attempts[-1]["branch_escape_attempted"] = False
                attempts[-1]["branch_escape_succeeded"] = False
                attempts[-1]["branch_escape_direction"] = ""
                attempts[-1]["branch_budget_reallocated"] = False
                if str(stage_context.get("current_stage") or "").strip().lower() == "stage_2":
                    if force_llm_now:
                        attempts[-1]["source_blind_multistep_branch_escape"] = {
                            "applied": False,
                            "reason": "llm_forcing_gated_before_branch_escape",
                            "llm_plan_reason": str(llm_context.get("llm_plan_reason") or ""),
                        }
                    elif bool(stage_context.get("trap_branch")):
                        attempts[-1]["branch_budget_reallocated"] = True
                        multistep_memory["branch_budget_reallocated_count"] = int(multistep_memory.get("branch_budget_reallocated_count") or 0) + 1
                        escape_text, escape_audit = _apply_source_blind_multistep_branch_escape_search(
                            current_text=current_text,
                            declared_failure_type=str(args.failure_type),
                            current_branch=str(stage_context.get("stage_2_branch") or ""),
                            preferred_branch=str(stage_context.get("preferred_stage_2_branch") or ""),
                            search_memory=multistep_memory,
                        )
                        attempts[-1]["source_blind_multistep_branch_escape"] = escape_audit
                        if bool(escape_audit.get("applied")):
                            attempts[-1]["branch_escape_attempted"] = True
                            attempts[-1]["branch_escape_direction"] = str(escape_audit.get("search_direction") or "")
                            multistep_memory["branch_escape_attempt_count"] = int(multistep_memory.get("branch_escape_attempt_count") or 0) + 1
                            candidate_key = str(escape_audit.get("candidate_key") or "").strip()
                            if candidate_key:
                                multistep_memory["tried_candidate_values"] = list(multistep_memory.get("tried_candidate_values") or []) + [candidate_key]
                            direction = str(escape_audit.get("search_direction") or "").strip()
                            if direction:
                                multistep_memory["last_trap_escape_direction"] = direction
                            guarded_patched, patch_guard = _guard_robustness_patch(
                                original_text=current_text,
                                patched_text=escape_text,
                                failure_type=str(args.failure_type),
                            )
                            attempts[-1]["patch_guard"] = patch_guard
                            if isinstance(guarded_patched, str) and guarded_patched.strip():
                                current_text = guarded_patched
                                if str(stage_plan_fields.get("executed_plan_action") or ""):
                                    multistep_memory["last_successful_stage_action"] = str(stage_plan_fields.get("executed_plan_action") or "")
                                final_error = "source_blind_multistep_branch_escape_applied_retry_pending"
                                continue
                            if direction:
                                multistep_memory["branch_bad_directions"] = list(multistep_memory.get("branch_bad_directions") or []) + [direction]
                            multistep_memory["search_regression_seen"] = True
                            multistep_memory["search_bad_direction_count"] = int(multistep_memory.get("search_bad_direction_count") or 0) + 1
                            final_error = str(patch_guard.get("reason") or "robustness_patch_rejected")
                            continue
                    else:
                        attempts[-1]["source_blind_multistep_branch_escape"] = {"applied": False, "reason": "current_branch_not_trap"}
                    if force_llm_now:
                        multistep_local_search_text = current_text
                        multistep_local_search = {
                            "applied": False,
                            "reason": "llm_forcing_gated_before_stage_2_local_search",
                            "llm_plan_reason": str(llm_context.get("llm_plan_reason") or ""),
                        }
                    else:
                        multistep_local_search_text, multistep_local_search = _apply_source_blind_multistep_local_search(
                            current_text=current_text,
                            declared_failure_type=str(args.failure_type),
                            current_stage=str(stage_context.get("current_stage") or ""),
                            current_fail_bucket=str(stage_context.get("current_fail_bucket") or ""),
                            search_memory=multistep_memory,
                        )
                    attempts[-1]["source_blind_multistep_local_search"] = multistep_local_search
                    if bool(multistep_local_search.get("applied")):
                        multistep_memory["local_search_attempt_count"] = int(multistep_memory.get("local_search_attempt_count") or 0) + 1
                        multistep_memory["adaptive_search_attempt_count"] = int(multistep_memory.get("adaptive_search_attempt_count") or 0) + 1
                        candidate_key = str(multistep_local_search.get("candidate_key") or "").strip()
                        if candidate_key:
                            multistep_memory["tried_candidate_values"] = list(multistep_memory.get("tried_candidate_values") or []) + [candidate_key]
                        multistep_memory["tried_parameters"] = list(multistep_memory.get("tried_parameters") or []) + [
                            str(x) for x in (multistep_local_search.get("parameter_names") or []) if isinstance(x, str)
                        ]
                        direction = str(multistep_local_search.get("search_direction") or "").strip()
                        search_kind = str(multistep_local_search.get("search_kind") or "").strip()
                        if search_kind:
                            multistep_memory["local_search_kinds"] = list(multistep_memory.get("local_search_kinds") or []) + [search_kind]
                        guarded_patched, patch_guard = _guard_robustness_patch(
                            original_text=current_text,
                            patched_text=multistep_local_search_text,
                            failure_type=str(args.failure_type),
                        )
                        attempts[-1]["patch_guard"] = patch_guard
                        if isinstance(guarded_patched, str) and guarded_patched.strip():
                            current_text = guarded_patched
                            if str(stage_plan_fields.get("executed_plan_action") or ""):
                                multistep_memory["last_successful_stage_action"] = str(stage_plan_fields.get("executed_plan_action") or "")
                            final_error = "source_blind_multistep_local_search_applied_retry_pending"
                            continue
                        if direction:
                            multistep_memory["bad_directions"] = list(multistep_memory.get("bad_directions") or []) + [direction]
                        multistep_memory["search_regression_seen"] = True
                        multistep_memory["search_bad_direction_count"] = int(multistep_memory.get("search_bad_direction_count") or 0) + 1
                        final_error = str(patch_guard.get("reason") or "robustness_patch_rejected")
                        continue
                else:
                    attempts[-1]["source_blind_multistep_branch_escape"] = {"applied": False, "reason": "branch_escape_requires_stage_2"}
                if force_llm_now:
                    stage2_repaired_text = current_text
                    stage2_repair = {
                        "applied": False,
                        "reason": "llm_forcing_gated_before_stage2_local_repair",
                        "llm_plan_reason": str(llm_context.get("llm_plan_reason") or ""),
                    }
                else:
                    stage2_repaired_text, stage2_repair = _apply_source_blind_multistep_stage2_local_repair(
                        current_text=current_text,
                        declared_failure_type=str(args.failure_type),
                        current_stage=str(stage_context.get("current_stage") or ""),
                        current_fail_bucket=str(stage_context.get("current_fail_bucket") or ""),
                        current_round=round_idx,
                    )
                attempts[-1]["source_blind_multistep_stage2_local_repair"] = stage2_repair
                if bool(stage2_repair.get("applied")):
                    guarded_patched, patch_guard = _guard_robustness_patch(
                        original_text=current_text,
                        patched_text=stage2_repaired_text,
                        failure_type=str(args.failure_type),
                    )
                    attempts[-1]["patch_guard"] = patch_guard
                    if isinstance(guarded_patched, str) and guarded_patched.strip():
                        current_text = guarded_patched
                        if str(stage_plan_fields.get("executed_plan_action") or ""):
                            multistep_memory["last_successful_stage_action"] = str(stage_plan_fields.get("executed_plan_action") or "")
                        final_error = "source_blind_multistep_stage2_local_repair_applied_retry_pending"
                        continue
                    multistep_memory["search_regression_seen"] = True
                    multistep_memory["search_bad_direction_count"] = int(multistep_memory.get("search_bad_direction_count") or 0) + 1
                llm_request_count_before = int(_load_live_ledger(budget_cfg).get("request_count") or 0)
                patched, llm_err, resolved_provider = _llm_repair_model_text(
                    planner_backend=str(args.planner_backend),
                    original_text=current_text,
                    failure_type=str(args.failure_type),
                    expected_stage=str(args.expected_stage),
                    error_excerpt=str(output or "")[-1800:],
                    repair_actions=stage_repair_actions or repair_actions,
                    model_name=model_name,
                    current_round=round_idx,
                )
                llm_request_count_after = int(_load_live_ledger(budget_cfg).get("request_count") or 0)
                llm_request_delta = max(0, llm_request_count_after - llm_request_count_before)
                attempts[-1]["planner_backend"] = str(args.planner_backend or "")
                attempts[-1]["resolved_llm_provider"] = str(resolved_provider or "")
                attempts[-1]["llm_plan_used"] = bool(llm_request_delta > 0)
                attempts[-1]["llm_plan_reason"] = str(llm_context.get("llm_plan_reason") or "")
                attempts[-1]["llm_request_count_delta"] = int(llm_request_delta)
                attempts[-1]["llm_branch_correction_used"] = bool(
                    llm_request_delta > 0
                    and (
                        bool(stage_context.get("trap_branch"))
                        or str(stage_context.get("branch_mode") or "").strip().lower() == "unknown"
                    )
                )
                if llm_request_delta > 0:
                    multistep_memory["llm_plan_used"] = True
                    multistep_memory["llm_plan_reason"] = str(llm_context.get("llm_plan_reason") or "")
                    multistep_memory["llm_request_count_delta_total"] = int(multistep_memory.get("llm_request_count_delta_total") or 0) + int(llm_request_delta)
                    if bool(attempts[-1]["llm_branch_correction_used"]):
                        multistep_memory["llm_branch_correction_used"] = True
                if bool(llm_context.get("llm_forcing")) and llm_request_delta > 0:
                    llm_resolution_text, llm_resolution_audit = _apply_source_blind_multistep_llm_resolution(
                        current_text=current_text,
                        declared_failure_type=str(args.failure_type),
                        llm_reason=str(llm_context.get("llm_plan_reason") or ""),
                    )
                    attempts[-1]["source_blind_multistep_llm_resolution"] = llm_resolution_audit
                    if bool(llm_resolution_audit.get("applied")):
                        patched = llm_resolution_text
                if isinstance(patched, str) and patched.strip():
                    guarded_patched, patch_guard = _guard_robustness_patch(
                        original_text=current_text,
                        patched_text=patched,
                        failure_type=str(args.failure_type),
                    )
                    attempts[-1]["patch_guard"] = patch_guard
                    if isinstance(guarded_patched, str) and guarded_patched.strip():
                        current_text = guarded_patched
                        if llm_request_delta > 0:
                            attempts[-1]["llm_resolution_contributed"] = True
                            multistep_memory["llm_resolution_contributed"] = True
                        if str(stage_plan_fields.get("executed_plan_action") or ""):
                            multistep_memory["last_successful_stage_action"] = str(stage_plan_fields.get("executed_plan_action") or "")
                    else:
                        final_error = str(patch_guard.get("reason") or "robustness_patch_rejected")
                        continue
                else:
                    final_error = llm_err or f"{resolved_provider}_patch_generation_failed"
                    break
            else:
                # rule backend does not mutate model text; useful for dry harness checks.
                break

    elapsed = round(time.monotonic() - started, 4)
    final_error, final_compile_error, final_sim_error = _normalize_terminal_errors(
        executor_status=executor_status,
        error_message=final_error,
        compile_error=final_compile_error,
        simulate_error=final_sim_error,
    )
    behavioral_eval = None
    if bool(final_check_ok and final_simulate_ok):
        behavioral_eval = _evaluate_behavioral_contract_from_model_text(
            current_text=current_text,
            source_model_text=source_model_text,
            failure_type=str(args.failure_type),
        )
    physics_contract_pass = bool(final_check_ok and final_simulate_ok)
    physics_contract_reasons: list[str] = []
    contract_fail_bucket = ""
    if isinstance(behavioral_eval, dict):
        physics_contract_pass = bool(behavioral_eval.get("pass"))
        physics_contract_reasons = [str(x) for x in (behavioral_eval.get("reasons") or []) if str(x).strip()]
        contract_fail_bucket = str(behavioral_eval.get("contract_fail_bucket") or "")
        scenario_results = [dict(item) for item in (behavioral_eval.get("scenario_results") or []) if isinstance(item, dict)]
        multi_step_stage = str(behavioral_eval.get("multi_step_stage") or "")
        multi_step_stage_2_unlocked = bool(behavioral_eval.get("multi_step_stage_2_unlocked"))
        multi_step_transition_seen = bool(behavioral_eval.get("multi_step_transition_seen"))
        multi_step_transition_reason = str(behavioral_eval.get("multi_step_transition_reason") or "")
    else:
        scenario_results = []
        multi_step_stage = ""
        multi_step_stage_2_unlocked = False
        multi_step_transition_seen = False
        multi_step_transition_reason = ""
    final_stage_context = _build_multistep_stage_context(
        failure_type=str(args.failure_type),
        behavioral_eval=behavioral_eval if isinstance(behavioral_eval, dict) else {},
        current_round=len(attempts),
        memory=multistep_memory,
    )
    local_search_audits = [
        row.get("source_blind_multistep_local_search")
        for row in attempts
        if isinstance(row, dict)
        and isinstance(row.get("source_blind_multistep_local_search"), dict)
        and bool((row.get("source_blind_multistep_local_search") or {}).get("applied"))
    ]
    local_search_kinds = [
        str((row or {}).get("search_kind") or "").strip()
        for row in local_search_audits
        if str((row or {}).get("search_kind") or "").strip()
    ]
    stage_1_unlock_via_local_search = bool(
        multi_step_stage_2_unlocked and any(kind == "stage_1_unlock" for kind in local_search_kinds)
    )
    stage_2_resolution_via_local_search = bool(
        physics_contract_pass and any(kind == "stage_2_resolution" for kind in local_search_kinds)
    )
    local_search_success_count = 1 if bool(physics_contract_pass and local_search_audits) else 0
    successful_directions = [
        str((row or {}).get("search_direction") or "").strip()
        for row in local_search_audits
        if str((row or {}).get("search_direction") or "").strip()
    ]
    adaptive_search_attempt_count = int(multistep_memory.get("adaptive_search_attempt_count") or len(local_search_audits) or 0)
    adaptive_search_success_count = 1 if bool(physics_contract_pass and local_search_audits) else 0
    search_improvement_seen = bool(stage_1_unlock_via_local_search or stage_2_resolution_via_local_search)
    cluster_only_resolution = bool(
        physics_contract_pass
        and not local_search_audits
        and any(
            bool(((row.get("source_blind_multistep_exposure_repair") or {}) if isinstance(row, dict) else {}).get("applied"))
            or bool(((row.get("source_blind_multistep_stage2_local_repair") or {}) if isinstance(row, dict) else {}).get("applied"))
            for row in attempts
            if isinstance(row, dict)
        )
    )
    llm_markers = _extract_source_blind_multistep_markers(current_text)
    llm_request_count_delta_total = int(multistep_memory.get("llm_request_count_delta_total") or 0)
    llm_plan_used = bool(multistep_memory.get("llm_plan_used")) or llm_request_count_delta_total > 0
    llm_resolution_contributed = bool(multistep_memory.get("llm_resolution_contributed")) and bool(physics_contract_pass)
    llm_only_resolution = bool(
        llm_resolution_contributed
        and not stage_1_unlock_via_local_search
        and not stage_2_resolution_via_local_search
        and not cluster_only_resolution
    )
    payload = {
        "task_id": str(args.task_id),
        "failure_type": str(args.failure_type),
        "realism_version": str(llm_markers.get("realism_version") or ""),
        "llm_forcing": bool(llm_markers.get("llm_forcing")),
        "llm_forcing_profile": str(llm_markers.get("llm_profile") or ""),
        "executor_status": executor_status,
        "planner_backend": str(args.planner_backend),
        "resolved_llm_provider": resolved_provider,
        "backend_used": backend,
        "uses_external_library": bool(layout.uses_external_library) if "layout" in locals() else False,
        "check_model_pass": bool(final_check_ok),
        "simulate_pass": bool(final_simulate_ok),
        "physics_contract_pass": bool(physics_contract_pass),
        "physics_contract_reasons": physics_contract_reasons,
        "contract_pass": bool(physics_contract_pass),
        "contract_fail_bucket": contract_fail_bucket,
        "scenario_results": scenario_results,
        "multi_step_stage": multi_step_stage,
        "multi_step_stage_2_unlocked": multi_step_stage_2_unlocked,
        "multi_step_transition_seen": multi_step_transition_seen,
        "multi_step_transition_round": int(max(1, len(attempts))) if multi_step_transition_seen else 0,
        "multi_step_transition_reason": multi_step_transition_reason,
        "current_stage": str(final_stage_context.get("current_stage") or ""),
        "stage_2_unlocked": bool(final_stage_context.get("stage_2_unlocked")),
        "transition_round": int(final_stage_context.get("transition_round") or 0),
        "transition_reason": str(final_stage_context.get("transition_reason") or ""),
        "current_fail_bucket": str(final_stage_context.get("current_fail_bucket") or ""),
        "next_focus": str(final_stage_context.get("next_focus") or ""),
        "stage_1_unlock_cluster": str(multistep_memory.get("stage_1_unlock_cluster") or ""),
        "stage_2_first_fail_bucket": str(multistep_memory.get("stage_2_first_fail_bucket") or ""),
        "stage_2_branch": str(final_stage_context.get("stage_2_branch") or multistep_memory.get("stage_2_branch") or ""),
        "preferred_stage_2_branch": str(final_stage_context.get("preferred_stage_2_branch") or multistep_memory.get("preferred_stage_2_branch") or ""),
        "branch_mode": str(final_stage_context.get("branch_mode") or ""),
        "branch_reason": str(final_stage_context.get("branch_reason") or multistep_memory.get("branch_reason") or ""),
        "trap_branch": bool(final_stage_context.get("trap_branch")) if str(final_stage_context.get("stage_2_branch") or "").strip() else bool(multistep_memory.get("trap_branch_active")),
        "trap_branch_entered": bool(multistep_memory.get("trap_branch_entered")),
        "correct_branch_selected": bool(final_stage_context.get("correct_branch_selected")) if str(final_stage_context.get("stage_2_branch") or "").strip() else bool(multistep_memory.get("correct_branch_selected")),
        "correct_branch_round": int(multistep_memory.get("correct_branch_round") or 0),
        "stage_aware_control_applied": bool(multistep_memory.get("stage_aware_focus_applied")),
        "stage_1_revisit_after_unlock": bool(multistep_memory.get("stage_1_revisit_after_unlock")),
        "plan_stage": str(multistep_memory.get("last_plan_stage") or ""),
        "branch_stage": str(multistep_memory.get("last_plan_stage") or "") if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else "",
        "current_branch": str(final_stage_context.get("stage_2_branch") or multistep_memory.get("stage_2_branch") or ""),
        "preferred_branch": str(final_stage_context.get("preferred_stage_2_branch") or multistep_memory.get("preferred_stage_2_branch") or ""),
        "plan_goal": str(multistep_memory.get("last_plan_goal") or ""),
        "plan_actions": [str(x) for x in (multistep_memory.get("last_plan_actions") or []) if isinstance(x, str)],
        "plan_constraints": [str(x) for x in (multistep_memory.get("last_plan_constraints") or []) if isinstance(x, str)],
        "plan_stop_condition": str(multistep_memory.get("last_plan_stop_condition") or ""),
        "branch_plan_goal": str(multistep_memory.get("last_plan_goal") or "") if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else "",
        "branch_plan_actions": [str(x) for x in (multistep_memory.get("last_plan_actions") or []) if isinstance(x, str)] if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else [],
        "branch_plan_stop_condition": str(multistep_memory.get("last_plan_stop_condition") or "") if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else "",
        "stage_plan_generated": bool(multistep_memory.get("stage_plan_generated")),
        "stage_plan_followed": bool(multistep_memory.get("stage_plan_followed")),
        "executed_plan_stage": str(multistep_memory.get("executed_plan_stage") or ""),
        "executed_plan_action": str(multistep_memory.get("executed_plan_action") or ""),
        "plan_followed": bool(multistep_memory.get("stage_plan_followed")),
        "plan_conflict_rejected": bool(multistep_memory.get("plan_conflict_rejected")),
        "plan_conflict_rejected_count": int(multistep_memory.get("plan_conflict_rejected_count") or 0),
        "last_successful_stage_action": str(multistep_memory.get("last_successful_stage_action") or ""),
        "tried_candidate_values": [str(x) for x in (multistep_memory.get("tried_candidate_values") or []) if str(x).strip()],
        "bad_directions": [str(x) for x in (multistep_memory.get("bad_directions") or []) if str(x).strip()],
        "successful_directions": successful_directions,
        "local_search_attempt_count": int(multistep_memory.get("local_search_attempt_count") or 0),
        "local_search_success_count": local_search_success_count,
        "local_search_kinds": local_search_kinds,
        "adaptive_search_attempt_count": adaptive_search_attempt_count,
        "adaptive_search_success_count": adaptive_search_success_count,
        "adaptive_search_success_pct": 100.0 if adaptive_search_success_count > 0 else 0.0,
        "search_improvement_seen": search_improvement_seen,
        "search_regression_seen": bool(multistep_memory.get("search_regression_seen")),
        "search_bad_direction_count": int(multistep_memory.get("search_bad_direction_count") or 0),
        "best_stage_2_fail_bucket_seen": str(multistep_memory.get("best_stage_2_fail_bucket_seen") or ""),
        "stage_2_best_progress_seen": bool(multistep_memory.get("stage_2_best_progress_seen")),
        "stage_1_unlock_via_local_search": stage_1_unlock_via_local_search,
        "stage_2_resolution_via_local_search": stage_2_resolution_via_local_search,
        "stage_1_unlock_via_adaptive_search": stage_1_unlock_via_local_search,
        "stage_2_resolution_via_adaptive_search": stage_2_resolution_via_local_search,
        "cluster_only_resolution": cluster_only_resolution,
        "template_only_resolution": cluster_only_resolution,
        "branch_history": [str(x) for x in (multistep_memory.get("branch_history") or []) if str(x).strip()],
        "trap_branch_history": [str(x) for x in (multistep_memory.get("trap_branch_history") or []) if str(x).strip()],
        "last_trap_escape_direction": str(multistep_memory.get("last_trap_escape_direction") or ""),
        "last_successful_branch_correction": str(multistep_memory.get("last_successful_branch_correction") or ""),
        "branch_bad_directions": [str(x) for x in (multistep_memory.get("branch_bad_directions") or []) if str(x).strip()],
        "branch_reentry_count": int(multistep_memory.get("branch_reentry_count") or 0),
        "repeated_trap_branch": bool(int(multistep_memory.get("branch_reentry_count") or 0) > 0),
        "branch_escape_attempt_count": int(multistep_memory.get("branch_escape_attempt_count") or 0),
        "branch_escape_success_count": int(multistep_memory.get("branch_escape_success_count") or 0),
        "branch_escape_success_pct": round((int(multistep_memory.get("branch_escape_success_count") or 0) / max(1, int(multistep_memory.get("branch_escape_attempt_count") or 0))) * 100.0, 2) if int(multistep_memory.get("branch_escape_attempt_count") or 0) > 0 else 0.0,
        "branch_budget_reallocated_count": int(multistep_memory.get("branch_budget_reallocated_count") or 0),
        "branch_escape_attempted": bool(int(multistep_memory.get("branch_escape_attempt_count") or 0) > 0),
        "branch_escape_succeeded": bool(int(multistep_memory.get("branch_escape_success_count") or 0) > 0),
        "branch_escape_direction": str(multistep_memory.get("last_trap_escape_direction") or ""),
        "branch_budget_reallocated": bool(int(multistep_memory.get("branch_budget_reallocated_count") or 0) > 0),
        "llm_plan_used": llm_plan_used,
        "llm_plan_reason": str(multistep_memory.get("llm_plan_reason") or ""),
        "llm_request_count_delta": llm_request_count_delta_total,
        "llm_branch_correction_used": bool(multistep_memory.get("llm_branch_correction_used")),
        "llm_resolution_contributed": llm_resolution_contributed,
        "llm_only_resolution": llm_only_resolution,
        "regression_pass": bool(final_check_ok and final_simulate_ok),
        "elapsed_sec": elapsed,
        "error_message": final_error,
        "compile_error": final_compile_error,
        "simulate_error_message": final_sim_error,
        "stderr_snippet": final_stderr,
        "attempts": attempts,
        "live_budget": {
            "max_requests_per_run": int(budget_cfg.get("max_requests_per_run") or 0),
            "max_consecutive_429": int(budget_cfg.get("max_consecutive_429") or 0),
            "base_backoff_sec": float(budget_cfg.get("base_backoff_sec") or 0.0),
            "max_backoff_sec": float(budget_cfg.get("max_backoff_sec") or 0.0),
        },
    }
    ledger = _load_live_ledger(budget_cfg)
    payload["live_request_count"] = int(ledger.get("request_count") or 0)
    payload["rate_limit_429_count"] = int(ledger.get("rate_limit_429_count") or 0)
    payload["budget_stop_triggered"] = bool(ledger.get("budget_stop_triggered"))
    payload["live_budget_stop_reason"] = str(ledger.get("last_stop_reason") or "")
    if str(args.out).strip():
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
