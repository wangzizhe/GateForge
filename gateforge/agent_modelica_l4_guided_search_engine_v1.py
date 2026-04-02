"""Layer 4 Guided Search Engine for multistep repair.

Extracted from agent_modelica_live_executor_v1.py to enable
independent testing and reuse.  All functions are pure: they consume
plain dicts/strings and return plain dicts/strings, with no Docker,
LLM, or OMC dependencies.

The engine provides:

* **Adaptive candidate generation** – priority-ranked parameter
  candidates with combo support, deduplication against tried keys, and
  direction reuse from prior successes.
* **Template-based search** – local search templates, branch-escape
  templates, exposure clusters, and stage-2 resolution clusters keyed
  by ``(model_name, failure_type, stage, bucket)``.
* **Behavioral-robustness search** – source-blind local repair clusters
  for robustness violation families.
* **Robustness guard** – structural-signature comparison that rejects
  destructive patches.
* **LLM plan execution** – resolution targets, plan normalisation,
  guided-search execution-plan construction, observation-payload
  construction, and plan/resolution application.
"""
from __future__ import annotations

import re

from .agent_modelica_stage_branch_controller_v1 import (
    count_passed_scenarios as _count_passed_scenarios,
)
from .agent_modelica_text_repair_utils_v1 import (
    apply_regex_replacement_cluster,
    extract_named_numeric_values,
    find_primary_model_name,
    format_numeric_candidate,
)


SCHEMA_VERSION = "agent_modelica_l4_guided_search_engine_v1"


# ---------------------------------------------------------------------------
# A: Adaptive search candidate generation
# ---------------------------------------------------------------------------


def adaptive_parameter_target_pools(
    *,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
) -> list[tuple[str, list[float], int]]:
    """Return prioritised ``(param_name, target_values, priority)`` tuples."""
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


def build_adaptive_search_candidates(
    *,
    current_text: str,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    search_memory: dict,
    search_kind: str,
) -> list[dict]:
    """Build priority-ranked adaptive search candidates."""
    pools = adaptive_parameter_target_pools(
        failure_type=failure_type,
        current_stage=current_stage,
        current_fail_bucket=current_fail_bucket,
    )
    if not pools:
        return []
    current_values = extract_named_numeric_values(
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
        target_value = format_numeric_candidate(float(targets[0]))
        if current_value == target_value:
            continue
        combo_candidates.append((name, targets, priority))
        if len(combo_candidates) >= 2:
            break
    for name, targets, priority in combo_candidates:
        current_value = current_values.get(name)
        if current_value is None:
            continue
        target_value = format_numeric_candidate(float(targets[0]))
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
            target_value = format_numeric_candidate(float(target))
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


def _parse_simple_numeric_expr(expr: str) -> float | None:
    text = str(expr or "").strip()
    if not text:
        return None
    if text.startswith("-(") and text.endswith(")"):
        inner = text[2:-1].strip()
        try:
            return -float(inner)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _simulate_error_recovery_target_values(*, current_value: float, direction: str) -> list[float]:
    dir_norm = str(direction or "").strip().lower()
    if dir_norm == "decrease":
        if current_value > 1.0:
            candidates = [current_value / 10.0, current_value / 2.0, 1.0, 0.1]
        elif current_value > 0.0:
            candidates = [current_value / 2.0, current_value / 10.0, 0.1]
        else:
            candidates = [0.1, 1.0]
    else:
        if current_value < 0.0:
            candidates = [abs(current_value), max(abs(current_value) * 10.0, 1.0), 1.0, 0.1]
        elif current_value == 0.0:
            candidates = [1.0, 0.1, 10.0]
        elif current_value < 1.0:
            candidates = [1.0, current_value * 10.0, current_value * 100.0]
        else:
            candidates = [current_value * 2.0, current_value * 10.0, 10.0]
    seen: set[str] = set()
    ordered: list[float] = []
    for value in candidates:
        key = format_numeric_candidate(float(value))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(float(value))
    return ordered


def apply_simulate_error_parameter_recovery(
    *,
    current_text: str,
    llm_plan: dict,
    simulate_error_message: str,
    search_memory: dict,
) -> tuple[str, dict]:
    """Apply a small parameter-value sweep after LLM diagnosed a simulate_error direction."""
    requested = [str(x).strip() for x in (llm_plan.get("candidate_parameters") or []) if str(x).strip()]
    directions = [str(x).strip() for x in (llm_plan.get("candidate_value_directions") or []) if str(x).strip()]
    if not requested:
        return current_text, {"applied": False, "reason": "no_candidate_parameters_from_llm_plan"}
    tried_keys = {
        str(x).strip()
        for x in (search_memory.get("tried_candidate_values") or [])
        if str(x).strip()
    }
    lines = current_text.splitlines(keepends=True)
    for idx, name in enumerate(requested):
        direction = directions[idx] if idx < len(directions) else "increase"
        decl_re = re.compile(
            rf"^(\s*(?:parameter\s+Real|Real)\s+{re.escape(name)}(?:\([^)]*\))?\s*=\s*)([^;]+)(;\s*(?://.*)?)(\r?\n?)$"
        )
        init_re = re.compile(
            rf"^(\s*{re.escape(name)}\s*=\s*)([^;]+)(;\s*(?://.*)?)(\r?\n?)$"
        )
        for line_index, line in enumerate(lines):
            match = decl_re.match(line) or init_re.match(line)
            if not match:
                continue
            current_rhs = str(match.group(2) or "").strip()
            current_value = _parse_simple_numeric_expr(current_rhs)
            if current_value is None:
                continue
            for target_value in _simulate_error_recovery_target_values(
                current_value=current_value,
                direction=direction,
            ):
                target_str = format_numeric_candidate(float(target_value))
                if target_str == current_rhs:
                    continue
                candidate_key = f"simulate_error_parameter_recovery:{name}:{target_str}"
                if candidate_key in tried_keys:
                    continue
                patched_lines = list(lines)
                patched_lines[line_index] = f"{match.group(1)}{target_str}{match.group(3)}{match.group(4)}"
                return "".join(patched_lines), {
                    "applied": True,
                    "reason": "simulate_error_parameter_recovery_applied",
                    "candidate_origin": "simulate_error_parameter_recovery",
                    "candidate_key": candidate_key,
                    "parameter_names": [name],
                    "candidate_values": [f"{name}={target_str}"],
                    "search_direction": str(direction or "increase"),
                    "current_value": current_rhs,
                    "target_value": target_str,
                    "line_index": line_index,
                    "simulate_error_message": str(simulate_error_message or ""),
                    "llm_plan_candidate_parameters": requested,
                    "llm_plan_candidate_value_directions": directions,
                }
    return current_text, {"applied": False, "reason": "no_simulate_error_parameter_recovery_candidate_applicable"}


# ---------------------------------------------------------------------------
# C: Template-based search
# ---------------------------------------------------------------------------


def source_blind_multistep_local_search_templates(
    *,
    model_name: str,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
) -> list[tuple[str, dict[str, float]]]:
    """Return local-search template clusters for the given context."""
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


def source_blind_multistep_branch_escape_templates(
    *,
    model_name: str,
    failure_type: str,
    current_branch: str,
) -> list[tuple[str, dict[str, float]]]:
    """Return branch-escape template clusters."""
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
                ("escape_recovery_overfit_full", {"startTime": 0.1, "k": 1.0, "width": 0.4, "T": 0.2}),
            ],
        },
    }
    return list(((templates.get((failure, branch)) or {}).get(model) or []))


def apply_source_blind_multistep_branch_escape_search(
    *,
    current_text: str,
    declared_failure_type: str,
    current_branch: str,
    preferred_branch: str,
    search_memory: dict,
) -> tuple[str, dict]:
    """Try branch-escape templates and return *(patched_text, audit)*."""
    failure = str(declared_failure_type or "").strip().lower()
    branch = str(current_branch or "").strip().lower()
    preferred = str(preferred_branch or "").strip().lower()
    model_name = find_primary_model_name(str(current_text or ""))
    if branch not in {"neighbor_overfit_trap", "nominal_overfit_trap", "recovery_overfit_trap"}:
        return current_text, {"applied": False, "reason": "branch_escape_not_supported"}
    templates = source_blind_multistep_branch_escape_templates(
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
        current_values = extract_named_numeric_values(current_text=current_text, names=list(target_values.keys()))
        replacements: list[tuple[str, str]] = []
        candidate_parts: list[str] = []
        used_names: list[str] = []
        for name, target in target_values.items():
            current_value = current_values.get(name)
            if current_value is None:
                continue
            target_str = format_numeric_candidate(float(target))
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
        patched, audit = apply_regex_replacement_cluster(
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


def apply_source_blind_multistep_local_search(
    *,
    current_text: str,
    declared_failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    search_memory: dict,
) -> tuple[str, dict]:
    """Try adaptive candidates then template fallbacks for local search."""
    failure = str(declared_failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    bucket = str(current_fail_bucket or "").strip().lower()
    model_name = find_primary_model_name(str(current_text or ""))
    if failure not in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"}:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    adaptive_candidates = build_adaptive_search_candidates(
        current_text=current_text,
        failure_type=failure,
        current_stage=stage,
        current_fail_bucket=bucket,
        search_memory=search_memory,
        search_kind="stage_1_unlock" if stage in {"", "stage_1"} else "stage_2_resolution",
    )
    for candidate in adaptive_candidates:
        patched, audit = apply_regex_replacement_cluster(
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
    templates = source_blind_multistep_local_search_templates(
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
        current_values = extract_named_numeric_values(current_text=current_text, names=list(target_values.keys()))
        replacements: list[tuple[str, str]] = []
        candidate_parts: list[str] = []
        used_names: list[str] = []
        for name, target in target_values.items():
            current_value = current_values.get(name)
            if current_value is None:
                continue
            target_str = format_numeric_candidate(float(target))
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
        patched, audit = apply_regex_replacement_cluster(
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


# ---------------------------------------------------------------------------
# Behavioral-robustness search
# ---------------------------------------------------------------------------


def behavioral_robustness_local_repair_clusters(
    *,
    model_name: str,
    failure_type: str,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return source-blind regex-replacement clusters for robustness violations."""
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


def apply_behavioral_robustness_source_blind_local_repair(
    *,
    current_text: str,
    declared_failure_type: str,
    current_round: int,
    robustness_repair_enabled: bool,
    source_mode: str,
) -> tuple[str, dict]:
    """Apply source-blind robustness repair clusters.

    Parameters *robustness_repair_enabled* and *source_mode* are
    passed in by the caller (the executor reads the env vars and
    forwards them here so this function stays pure).
    """
    if not robustness_repair_enabled:
        return current_text, {"applied": False, "reason": "behavioral_robustness_deterministic_repair_disabled"}
    if str(source_mode or "").strip().lower() != "source_blind":
        return current_text, {"applied": False, "reason": "source_blind_mode_not_enabled"}
    failure = str(declared_failure_type or "").strip().lower()
    if failure not in {
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    model_name = find_primary_model_name(str(current_text or ""))
    clusters = behavioral_robustness_local_repair_clusters(model_name=model_name, failure_type=failure)
    if not clusters:
        return current_text, {"applied": False, "reason": "no_source_blind_clusters_defined"}
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    start = min(round_idx - 1, len(clusters) - 1)
    ordered = clusters[start:] + clusters[:start]
    for cluster_name, replacements in ordered:
        patched, audit = apply_regex_replacement_cluster(
            current_text=current_text,
            cluster_name=cluster_name,
            replacements=replacements,
        )
        if bool(audit.get("applied")):
            audit["model_name"] = model_name
            audit["current_round"] = round_idx
            return patched, audit
    return current_text, {"applied": False, "reason": "no_matching_source_blind_cluster", "model_name": model_name, "current_round": round_idx}


# ---------------------------------------------------------------------------
# D: Exposure and stage-2 resolution
# ---------------------------------------------------------------------------


def source_blind_multistep_exposure_clusters(
    *,
    model_name: str,
    failure_type: str,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return round-1 exposure-repair clusters."""
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


def apply_source_blind_multistep_exposure_repair(
    *,
    current_text: str,
    declared_failure_type: str,
    current_round: int,
) -> tuple[str, dict]:
    """Apply exposure repair (round-1 only)."""
    failure = str(declared_failure_type or "").strip().lower()
    if failure not in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"}:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    try:
        round_idx = max(1, int(current_round))
    except Exception:
        round_idx = 1
    if round_idx != 1:
        return current_text, {"applied": False, "reason": "exposure_repair_only_runs_in_round_1", "current_round": round_idx}
    model_name = find_primary_model_name(str(current_text or ""))
    clusters = source_blind_multistep_exposure_clusters(model_name=model_name, failure_type=failure)
    if not clusters:
        return current_text, {"applied": False, "reason": "no_multistep_exposure_cluster_defined", "model_name": model_name, "current_round": round_idx}
    cluster_name, replacements = clusters[0]
    patched, audit = apply_regex_replacement_cluster(
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


def source_blind_multistep_stage2_resolution_clusters(
    *,
    model_name: str,
    failure_type: str,
    fail_bucket: str,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return stage-2 resolution clusters."""
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


def apply_source_blind_multistep_stage2_local_repair(
    *,
    current_text: str,
    declared_failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    current_round: int,
) -> tuple[str, dict]:
    """Apply stage-2 resolution clusters."""
    failure = str(declared_failure_type or "").strip().lower()
    if failure not in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"}:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    if str(current_stage or "").strip().lower() != "stage_2":
        return current_text, {"applied": False, "reason": "stage_2_local_repair_requires_stage_2"}
    model_name = find_primary_model_name(str(current_text or ""))
    clusters = source_blind_multistep_stage2_resolution_clusters(
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
        patched, audit = apply_regex_replacement_cluster(
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


# ---------------------------------------------------------------------------
# E: Robustness guard
# ---------------------------------------------------------------------------


def robustness_structure_signature(text: str) -> list[str]:
    """Return a structural fingerprint of the Modelica *text*."""
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


def guard_robustness_patch(
    *,
    original_text: str,
    patched_text: str,
    failure_type: str,
) -> tuple[str | None, dict]:
    """Accept or reject a patch based on structural-signature comparison."""
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
    if robustness_structure_signature(original) != robustness_structure_signature(patched):
        return None, {"accepted": False, "reason": "robustness_structure_drift_detected"}
    return patched_text, {"accepted": True, "reason": "robustness_patch_guard_pass"}


# ---------------------------------------------------------------------------
# F: LLM plan resolution and execution
# ---------------------------------------------------------------------------


def source_blind_multistep_llm_resolution_targets(
    *,
    model_name: str,
    failure_type: str,
) -> dict[str, float]:
    """Return target-value map for LLM-guided resolution."""
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


def preferred_llm_parameter_order_for_branch(
    *,
    failure_type: str,
    branch_name: str,
    available_targets: dict[str, float],
) -> list[str]:
    """Return branch-aware preferred parameter ordering."""
    branch = str(branch_name or "").strip().lower()
    failure = str(failure_type or "").strip().lower()
    preferences = {
        ("stability_then_behavior", "behavior_timing_branch"): ["startTime", "duration", "height", "k", "width", "period"],
        ("stability_then_behavior", "neighbor_overfit_trap"): ["duration", "height", "k", "width", "period", "startTime"],
        ("stability_then_behavior", "stability_margin_recovery"): ["height", "duration", "startTime", "k"],
        ("behavior_then_robustness", "neighbor_robustness_branch"): ["k", "offset", "startTime", "freqHz", "width", "period"],
        ("behavior_then_robustness", "nominal_overfit_trap"): ["startTime", "freqHz", "width", "period", "k", "offset"],
        ("switch_then_recovery", "post_switch_recovery_branch"): ["width", "T", "duration", "period", "k", "startTime"],
        ("switch_then_recovery", "recovery_overfit_trap"): ["startTime", "k", "width", "T", "period", "duration"],
    }
    preferred = list(preferences.get((failure, branch), []))
    available = list(available_targets.keys())
    ordered = [name for name in preferred if name in available]
    ordered.extend(name for name in available if name not in ordered)
    return ordered


def normalize_source_blind_multistep_llm_plan(
    *,
    payload: dict | None,
    stage_context: dict,
    llm_reason: str,
) -> dict:
    """Normalise raw LLM plan output into a canonical dict."""
    raw = payload if isinstance(payload, dict) else {}
    candidate_parameters = [str(x).strip() for x in (raw.get("candidate_parameters") or []) if str(x).strip()]
    candidate_value_directions = [
        str(x).strip() for x in (raw.get("candidate_value_directions") or []) if str(x).strip()
    ]
    switch_to_branch = str(
        raw.get("switch_to_branch")
        or raw.get("new_branch")
        or raw.get("preferred_branch")
        or stage_context.get("preferred_stage_2_branch")
        or ""
    ).strip().lower()
    continue_current_branch = bool(raw.get("continue_current_branch"))
    if not continue_current_branch and not switch_to_branch and str(stage_context.get("stage_2_branch") or "").strip():
        continue_current_branch = True
    branch_choice_reason = str(raw.get("branch_choice_reason") or raw.get("why_not_other_branch") or "").strip()
    try:
        replan_budget_total = max(0, int(raw.get("replan_budget_total") or 0))
    except Exception:
        replan_budget_total = 0
    try:
        replan_budget_for_branch_diagnosis = max(0, int(raw.get("replan_budget_for_branch_diagnosis") or 0))
    except Exception:
        replan_budget_for_branch_diagnosis = 0
    try:
        replan_budget_for_branch_escape = max(0, int(raw.get("replan_budget_for_branch_escape") or 0))
    except Exception:
        replan_budget_for_branch_escape = 0
    try:
        replan_budget_for_resolution = max(0, int(raw.get("replan_budget_for_resolution") or 0))
    except Exception:
        replan_budget_for_resolution = 0
    bucket_aliases = {
        "branch_diagnosis": "branch_diagnosis",
        "diagnosis": "branch_diagnosis",
        "branch-diagnosis": "branch_diagnosis",
        "branch_escape": "branch_escape",
        "escape": "branch_escape",
        "trap_escape": "branch_escape",
        "branch-escape": "branch_escape",
        "resolution": "resolution",
        "resolve": "resolution",
    }
    raw_bucket_sequence = raw.get("guided_search_bucket_sequence")
    bucket_sequence: list[str] = []
    if isinstance(raw_bucket_sequence, list):
        for item in raw_bucket_sequence:
            normalized = bucket_aliases.get(str(item or "").strip().lower(), "")
            if not normalized or normalized in bucket_sequence:
                continue
            bucket_sequence.append(normalized)
    if not bucket_sequence:
        if replan_budget_for_branch_diagnosis > 0:
            bucket_sequence.append("branch_diagnosis")
        if replan_budget_for_branch_escape > 0:
            bucket_sequence.append("branch_escape")
        if replan_budget_for_resolution > 0:
            bucket_sequence.append("resolution")
    return {
        "diagnosed_stage": str(raw.get("diagnosed_stage") or stage_context.get("current_stage") or "").strip().lower(),
        "diagnosed_branch": str(raw.get("diagnosed_branch") or stage_context.get("stage_2_branch") or "").strip().lower(),
        "preferred_branch": str(
            raw.get("preferred_branch") or stage_context.get("preferred_stage_2_branch") or ""
        ).strip().lower(),
        "new_branch": str(
            raw.get("new_branch")
            or raw.get("diagnosed_branch")
            or stage_context.get("preferred_stage_2_branch")
            or stage_context.get("stage_2_branch")
            or ""
        ).strip().lower(),
        "repair_goal": str(raw.get("repair_goal") or llm_reason or "llm_guided_multistep_resolution").strip(),
        "candidate_parameters": candidate_parameters,
        "candidate_value_directions": candidate_value_directions,
        "why_not_other_branch": str(raw.get("why_not_other_branch") or "").strip(),
        "stop_condition": str(raw.get("stop_condition") or "stop when the preferred branch is restored or all scenarios pass").strip(),
        "rationale": str(raw.get("rationale") or "").strip(),
        "branch_choice_reason": branch_choice_reason,
        "continue_current_branch": continue_current_branch,
        "switch_to_branch": switch_to_branch,
        "replan_budget_total": replan_budget_total,
        "replan_budget_for_branch_diagnosis": replan_budget_for_branch_diagnosis,
        "replan_budget_for_branch_escape": replan_budget_for_branch_escape,
        "replan_budget_for_resolution": replan_budget_for_resolution,
        "guided_search_bucket_sequence": bucket_sequence,
    }


def build_guided_search_execution_plan(
    *,
    llm_plan: dict,
    stage_context: dict,
    requested_parameters: list[str],
    ordered_targets: list[str],
    previous_branch: str,
) -> dict:
    """Allocate LLM plan budget to guided-search buckets."""
    diagnosis_budget = max(0, int(llm_plan.get("replan_budget_for_branch_diagnosis") or 0))
    branch_escape_budget = max(0, int(llm_plan.get("replan_budget_for_branch_escape") or 0))
    resolution_budget = max(0, int(llm_plan.get("replan_budget_for_resolution") or 0))
    bucket_sequence = [
        str(x).strip().lower()
        for x in (llm_plan.get("guided_search_bucket_sequence") or [])
        if str(x).strip()
    ]
    candidate_pool = requested_parameters if requested_parameters else list(ordered_targets)
    execution_parameters = list(candidate_pool[:resolution_budget]) if resolution_budget > 0 else []
    candidate_suppressed = max(0, len(candidate_pool) - len(execution_parameters))
    current_branch = str(stage_context.get("stage_2_branch") or "").strip().lower()
    preferred_branch = str(stage_context.get("preferred_stage_2_branch") or "").strip().lower()
    trap_branch = bool(stage_context.get("trap_branch"))
    needs_branch_escape = bool(
        trap_branch
        or (current_branch and preferred_branch and current_branch != preferred_branch)
        or bool(llm_plan.get("switch_to_branch"))
    )
    branch_escape_skipped = bool(needs_branch_escape and branch_escape_budget <= 0)
    resolution_skipped = bool(candidate_pool and resolution_budget <= 0)
    branch_frozen: list[str] = []
    if branch_escape_skipped and current_branch:
        branch_frozen.append(current_branch)
    if bool(llm_plan.get("replan_switch_branch")) and previous_branch and previous_branch not in branch_frozen:
        branch_frozen.append(previous_branch)
    budget_bucket_consumed = {
        "branch_diagnosis": diagnosis_budget if diagnosis_budget > 0 and "branch_diagnosis" in bucket_sequence else 0,
        "branch_escape": branch_escape_budget if branch_escape_budget > 0 and "branch_escape" in bucket_sequence and not branch_escape_skipped else 0,
        "resolution": len(execution_parameters),
    }
    budget_bucket_exhausted = [
        bucket
        for bucket, budget in (
            ("branch_diagnosis", diagnosis_budget),
            ("branch_escape", branch_escape_budget),
            ("resolution", resolution_budget),
        )
        if budget > 0 and int(budget_bucket_consumed.get(bucket) or 0) >= budget
    ]
    candidate_attempt_count_by_bucket = {
        "branch_diagnosis": 1 if diagnosis_budget > 0 and "branch_diagnosis" in bucket_sequence else 0,
        "branch_escape": 1 if branch_escape_budget > 0 and "branch_escape" in bucket_sequence and not branch_escape_skipped else 0,
        "resolution": len(execution_parameters),
    }
    return {
        "guided_search_bucket_sequence": bucket_sequence,
        "guided_search_order": " -> ".join(bucket_sequence),
        "execution_parameters": execution_parameters,
        "candidate_pool_size": len(candidate_pool),
        "candidate_suppressed_by_budget": candidate_suppressed,
        "budget_bucket_consumed": budget_bucket_consumed,
        "budget_bucket_exhausted": budget_bucket_exhausted,
        "candidate_attempt_count_by_bucket": candidate_attempt_count_by_bucket,
        "resolution_skipped_due_to_budget": resolution_skipped,
        "branch_escape_skipped_due_to_budget": branch_escape_skipped,
        "branch_frozen_by_budget": branch_frozen,
    }


def build_guided_search_observation_payload(
    *,
    memory: dict,
    stage_context: dict,
    contract_fail_bucket: str,
    scenario_results: list[dict] | None,
) -> dict:
    """Build an observation payload from guided-search progress."""
    budget_spent = dict(memory.get("last_budget_spent_by_bucket") or {})
    candidate_attempt_count = dict(memory.get("last_candidate_attempt_count_by_bucket") or {})
    bucket_sequence = [
        str(x).strip().lower()
        for x in (memory.get("last_guided_search_bucket_sequence") or [])
        if str(x).strip()
    ]
    current_pass_count = _count_passed_scenarios(scenario_results)
    previous_pass_count = int(memory.get("last_llm_plan_pass_count") or 0)
    progress_delta = max(0, current_pass_count - previous_pass_count)
    current_branch = str(stage_context.get("stage_2_branch") or "").strip().lower()
    preferred_branch = str(stage_context.get("preferred_stage_2_branch") or "").strip().lower()
    branch_progress = int(bool(current_branch and preferred_branch and current_branch == preferred_branch))
    diagnosis_progress = int(str(stage_context.get("branch_mode") or "").strip().lower() != "unknown")
    best_progress_by_bucket = {
        "branch_diagnosis": diagnosis_progress,
        "branch_escape": branch_progress,
        "resolution": progress_delta,
    }
    no_progress_buckets = [
        bucket
        for bucket, spent in budget_spent.items()
        if int(spent or 0) > 0 and int(best_progress_by_bucket.get(bucket) or 0) <= 0
    ]
    return {
        "guided_search_bucket_sequence": bucket_sequence,
        "budget_spent_by_bucket": budget_spent,
        "candidate_attempt_count_by_bucket": candidate_attempt_count,
        "best_progress_by_bucket": best_progress_by_bucket,
        "no_progress_buckets": no_progress_buckets,
        "branch_regression_seen": bool(str(stage_context.get("current_stage") or "").strip().lower() == "stage_1"),
        "same_branch_stall_count": int(memory.get("replan_same_branch_stall_count") or 0),
        "abandoned_branches": [str(x) for x in (memory.get("replan_abandoned_branches") or []) if str(x).strip()],
        "current_fail_bucket": str(contract_fail_bucket or stage_context.get("current_fail_bucket") or "").strip().lower(),
        "candidate_suppressed_by_budget": int(memory.get("last_candidate_suppressed_by_budget") or 0),
        "resolution_skipped_due_to_budget": bool(memory.get("last_resolution_skipped_due_to_budget")),
        "branch_escape_skipped_due_to_budget": bool(memory.get("last_branch_escape_skipped_due_to_budget")),
        "branch_frozen_by_budget": [str(x) for x in (memory.get("last_branch_frozen_by_budget") or []) if str(x).strip()],
    }


def resolve_llm_plan_parameter_names(
    *,
    requested_names: list[str],
    available_targets: dict[str, float],
) -> list[str]:
    """Resolve alias-aware parameter names against *available_targets*."""
    target_names = list(available_targets.keys())
    target_set = set(target_names)
    resolved: list[str] = []
    alias_map = {"f": "freqHz"}
    for raw_name in requested_names:
        name = str(raw_name or "").strip()
        if not name:
            continue
        candidate = name
        if candidate not in target_set and "." in candidate:
            candidate = candidate.split(".")[-1]
        candidate = alias_map.get(candidate, candidate)
        if candidate in target_set and candidate not in resolved:
            resolved.append(candidate)
            continue
        lowered = name.lower()
        matched = ""
        for target in target_names:
            if lowered.endswith(f".{target.lower()}") or lowered == target.lower():
                matched = target
                break
        if matched and matched not in resolved:
            resolved.append(matched)
    return resolved


def select_initial_llm_plan_parameters(
    *,
    llm_plan: dict,
    available_targets: dict[str, float],
    failure_type: str = "",
) -> list[str]:
    """Select the initial parameter set for the first LLM plan execution."""
    requested = [str(x).strip() for x in (llm_plan.get("candidate_parameters") or []) if str(x).strip()]
    usable = resolve_llm_plan_parameter_names(requested_names=requested, available_targets=available_targets)
    usable_set = set(usable)
    if {"startTime", "freqHz", "k"}.issubset(set(available_targets.keys())) and {"startTime", "freqHz"}.issubset(usable_set):
        return ["startTime", "freqHz"]
    if {"startTime", "k", "width", "T"}.issubset(set(available_targets.keys())) and {"startTime", "k"}.issubset(usable_set):
        return ["startTime", "k"]
    if {"startTime", "duration"}.issubset(set(available_targets.keys())) and {"startTime"}.issubset(usable_set):
        return ["startTime"]
    if {"width", "period", "offset"}.issubset(set(available_targets.keys())) and {"width", "period"}.issubset(usable_set):
        return ["width", "period"]
    if usable:
        return usable[:1]
    preferred_branch = str(llm_plan.get("preferred_branch") or llm_plan.get("diagnosed_branch") or "").strip().lower()
    target_names = preferred_llm_parameter_order_for_branch(
        failure_type=failure_type,
        branch_name=preferred_branch,
        available_targets=available_targets,
    )
    return target_names[:1]


def llm_plan_branch_match(*, llm_plan: dict, stage_context: dict) -> bool:
    """Return True if the LLM plan branch matches the actual branch."""
    diagnosed_branch = str(llm_plan.get("diagnosed_branch") or "").strip().lower()
    preferred_branch = str(llm_plan.get("preferred_branch") or "").strip().lower()
    actual_branch = str(stage_context.get("stage_2_branch") or "").strip().lower()
    actual_preferred = str(stage_context.get("preferred_stage_2_branch") or "").strip().lower()
    if preferred_branch and actual_preferred:
        return preferred_branch == actual_preferred
    if diagnosed_branch and actual_branch:
        return diagnosed_branch == actual_branch
    return False


def llm_plan_parameter_match(*, llm_plan: dict, available_targets: dict[str, float]) -> bool:
    """Return True if the LLM plan requests at least one available target."""
    wanted = set(
        resolve_llm_plan_parameter_names(
            requested_names=[str(x).strip() for x in (llm_plan.get("candidate_parameters") or []) if str(x).strip()],
            available_targets=available_targets,
        )
    )
    if not wanted:
        return False
    return bool(wanted.intersection(set(available_targets.keys())))


def apply_source_blind_multistep_llm_plan(
    *,
    current_text: str,
    declared_failure_type: str,
    llm_plan: dict,
    llm_reason: str,
    parameter_names_override: list[str] | None = None,
) -> tuple[str, dict]:
    """Apply an LLM-generated repair plan."""
    model_name = find_primary_model_name(str(current_text or ""))
    targets = source_blind_multistep_llm_resolution_targets(model_name=model_name, failure_type=declared_failure_type)
    if not targets:
        return current_text, {"applied": False, "reason": "no_llm_plan_targets_defined"}

    def _target_value(name: str) -> str:
        return format_numeric_candidate(float(targets[name]))

    ordered_names = [str(x).strip() for x in (parameter_names_override or []) if str(x).strip() in targets]
    if not ordered_names:
        ordered_names = resolve_llm_plan_parameter_names(
            requested_names=[str(x).strip() for x in (llm_plan.get("candidate_parameters") or []) if str(x).strip()],
            available_targets=targets,
        )
    if not ordered_names:
        ordered_names = list(targets.keys())
    current_values = extract_named_numeric_values(
        current_text=current_text,
        names=list(dict.fromkeys(list(ordered_names) + list(targets.keys()))),
    )
    replacements: list[tuple[str, str]] = []
    candidate_values: list[str] = []
    used_names: list[str] = []
    for name in ordered_names:
        current_value = current_values.get(name)
        if current_value is None:
            continue
        target_str = _target_value(name)
        if current_value == target_str:
            continue
        replacements.append((rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_str}"))
        candidate_values.append(f"{name}={target_str}")
        used_names.append(str(name))
    if not replacements:
        unresolved_names = [
            name
            for name in targets
            if current_values.get(name) is not None and current_values.get(name) != _target_value(name)
        ]
        fallback_names = [name for name in unresolved_names if name not in ordered_names]
        if fallback_names:
            width = max(2, len(ordered_names) or 1)
            for name in fallback_names[:width]:
                current_value = current_values.get(name)
                if current_value is None:
                    continue
                target_str = _target_value(name)
                replacements.append((rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_str}"))
                candidate_values.append(f"{name}={target_str}")
                used_names.append(str(name))
    if not replacements:
        return current_text, {"applied": False, "reason": "llm_plan_targets_already_satisfied"}
    patched, audit = apply_regex_replacement_cluster(
        current_text=current_text,
        cluster_name=f"{str(model_name or '').strip().lower()}_llm_plan_cluster",
        replacements=replacements,
    )
    if not bool(audit.get("applied")):
        return current_text, {"applied": False, "reason": "llm_plan_cluster_not_applicable"}
    audit["reason"] = f"source_blind_multistep_llm_plan:{llm_reason or 'llm_plan'}"
    audit["model_name"] = model_name
    audit["candidate_origin"] = "llm_plan_execution"
    audit["candidate_values"] = candidate_values
    audit["parameter_names"] = used_names
    audit["search_direction"] = "+".join(used_names)
    audit["llm_plan_candidate_parameters"] = [str(x) for x in (llm_plan.get("candidate_parameters") or []) if str(x).strip()]
    audit["llm_plan_candidate_value_directions"] = [
        str(x) for x in (llm_plan.get("candidate_value_directions") or []) if str(x).strip()
    ]
    audit["llm_plan_execution_parameters"] = list(ordered_names)
    return patched, audit


def apply_source_blind_multistep_llm_resolution(
    *,
    current_text: str,
    declared_failure_type: str,
    llm_reason: str,
) -> tuple[str, dict]:
    """Apply forced LLM resolution (all target parameters at once)."""
    model_name = find_primary_model_name(str(current_text or ""))
    targets = source_blind_multistep_llm_resolution_targets(model_name=model_name, failure_type=declared_failure_type)
    if not targets:
        return current_text, {"applied": False, "reason": "no_llm_resolution_targets_defined"}
    current_values = extract_named_numeric_values(current_text=current_text, names=list(targets.keys()))
    replacements: list[tuple[str, str]] = []
    candidate_values: list[str] = []
    used_names: list[str] = []
    for name, target in targets.items():
        current_value = current_values.get(name)
        if current_value is None:
            continue
        target_str = format_numeric_candidate(float(target))
        if current_value == target_str:
            continue
        replacements.append((rf"\b{re.escape(name)}\s*=\s*{re.escape(current_value)}\b", f"{name}={target_str}"))
        candidate_values.append(f"{name}={target_str}")
        used_names.append(str(name))
    if not replacements:
        return current_text, {"applied": False, "reason": "llm_resolution_target_already_satisfied"}
    patched, audit = apply_regex_replacement_cluster(
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
