"""
Dual-layer multi-parameter mutation generator for v0.3.6.

v0.3.5 established a validated baseline lever:
  simulate_error_parameter_recovery_sweep

v0.3.6 needs tasks that are harder than that baseline. The first public step is
to generate post-restore hidden-base mutations that require more than a single
numeric correction attempt. This module keeps the same dual-layer structure as
v0.3.5, but the hidden base now mutates multiple parameters.

Primary family in this file:
  post_restore_residual_semantic_conflict
    - hidden base mutates two Real parameters together
    - marked top is still removed by the existing rule path in Round 1
    - after restore, the residual hidden base is no longer a single-parameter
      numeric recovery problem by construction

Schema: agent_modelica_dual_layer_mutation_v0_3_6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_dual_layer_mutation_v0_3_5 import (
    SAFE_DUAL_LAYER_FAILURE_TYPES,
    TOP_LAYER_COMMENT,
    TOP_LAYER_TAU_PREFIX,
    apply_marked_top_mutation,
)


SCHEMA_VERSION = "agent_modelica_dual_layer_mutation_v0_3_6"
FAMILY_ID = "post_restore_residual_semantic_conflict"
HIDDEN_BASE_OPERATORS = {
    "paired_value_collapse",
    "paired_value_bias_shift",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_hash(text: str) -> str:
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return str(h % 100_000_000).zfill(8)


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _candidate_real_parameter_matches(model_text: str) -> list[dict]:
    pattern = re.compile(
        r"(parameter\s+Real\s+(\w+)\s*(?:\([^)]*\))?\s*=\s*)([0-9]+\.?[0-9]*(?:e[+-]?[0-9]+)?)(\s*;)",
        re.IGNORECASE,
    )
    rows = []
    for m in pattern.finditer(model_text):
        rows.append(
            {
                "span": (m.start(3), m.end(3)),
                "prefix": m.group(1),
                "name": m.group(2),
                "value": m.group(3),
                "suffix": m.group(4),
            }
        )
    return rows


def _pick_parameter_rows(
    matches: list[dict],
    *,
    target_param_names: tuple[str, str] | None = None,
    disallowed_values: set[str] | None = None,
) -> list[dict]:
    if target_param_names:
        name_map = {str(row.get("name") or ""): row for row in matches}
        picked = [name_map.get(name) for name in target_param_names]
        if any(row is None for row in picked):
            return []
        resolved = [row for row in picked if isinstance(row, dict)]
        if len(resolved) != 2 or resolved[0].get("name") == resolved[1].get("name"):
            return []
        return resolved
    blocked = disallowed_values or set()
    picked = [row for row in matches if row["value"] not in blocked][:2]
    return picked if len(picked) == 2 else []


def apply_paired_value_collapse(
    model_text: str,
    *,
    collapse_values: tuple[str, str] = ("0.0", "0.0"),
    target_param_names: tuple[str, str] | None = None,
) -> tuple[str, dict]:
    matches = _candidate_real_parameter_matches(model_text)
    picked = _pick_parameter_rows(
        matches,
        target_param_names=target_param_names,
        disallowed_values={"0", "0.0"},
    )
    if len(picked) < 2:
        return model_text, {
            "applied": False,
            "reason": (
                "target_parameter_pair_not_found"
                if target_param_names
                else "fewer_than_two_numeric_real_parameters"
            ),
        }

    result = model_text
    mutations = []
    for row, new_value in sorted(zip(picked, collapse_values), key=lambda item: item[0]["span"][0], reverse=True):
        start, end = row["span"]
        result = result[:start] + new_value + result[end:]
        mutations.append(
            {
                "param_name": row["name"],
                "original_value": row["value"],
                "new_value": new_value,
            }
        )
    mutations.reverse()
    return result, {
        "applied": True,
        "operator": "paired_value_collapse",
        "mutations": mutations,
        "mutation_count": len(mutations),
        "has_gateforge_marker": False,
        "target_param_names": [row["name"] for row in picked],
    }


def apply_paired_value_bias_shift(
    model_text: str,
    *,
    replacement_values: tuple[str, str] = ("0.1", "10.0"),
    target_param_names: tuple[str, str] | None = None,
) -> tuple[str, dict]:
    matches = _candidate_real_parameter_matches(model_text)
    picked = _pick_parameter_rows(
        matches,
        target_param_names=target_param_names,
        disallowed_values=set(replacement_values),
    )
    if len(picked) < 2:
        return model_text, {
            "applied": False,
            "reason": (
                "target_parameter_pair_not_found"
                if target_param_names
                else "fewer_than_two_numeric_real_parameters"
            ),
        }

    result = model_text
    mutations = []
    for row, new_value in sorted(zip(picked, replacement_values), key=lambda item: item[0]["span"][0], reverse=True):
        start, end = row["span"]
        result = result[:start] + new_value + result[end:]
        mutations.append(
            {
                "param_name": row["name"],
                "original_value": row["value"],
                "new_value": new_value,
            }
        )
    mutations.reverse()
    return result, {
        "applied": True,
        "operator": "paired_value_bias_shift",
        "mutations": mutations,
        "mutation_count": len(mutations),
        "has_gateforge_marker": False,
        "target_param_names": [row["name"] for row in picked],
    }


def build_dual_layer_multi_param_task(
    *,
    task_id: str,
    clean_source_text: str,
    source_model_path: str,
    source_library: str,
    model_hint: str,
    hidden_base_operator: str = "paired_value_collapse",
    hidden_base_param_names: tuple[str, str] | None = None,
    hidden_base_replacement_values: tuple[str, str] | None = None,
    declared_failure_type: str = "simulate_error",
    expected_stage: str = "simulate",
) -> dict:
    if declared_failure_type not in SAFE_DUAL_LAYER_FAILURE_TYPES:
        raise ValueError(
            f"declared_failure_type={declared_failure_type!r} is not safe for dual-layer mutation"
        )
    if hidden_base_operator not in HIDDEN_BASE_OPERATORS:
        raise ValueError(
            f"hidden_base_operator={hidden_base_operator!r} not in {sorted(HIDDEN_BASE_OPERATORS)}"
        )

    if hidden_base_operator == "paired_value_collapse":
        source_model_text, base_audit = apply_paired_value_collapse(
            clean_source_text,
            collapse_values=hidden_base_replacement_values or ("0.0", "0.0"),
            target_param_names=hidden_base_param_names,
        )
    elif hidden_base_operator == "paired_value_bias_shift":
        source_model_text, base_audit = apply_paired_value_bias_shift(
            clean_source_text,
            replacement_values=hidden_base_replacement_values or ("0.1", "10.0"),
            target_param_names=hidden_base_param_names,
        )
    else:
        raise ValueError(f"Unknown operator: {hidden_base_operator}")

    if not base_audit.get("applied"):
        raise RuntimeError(
            f"Hidden base mutation {hidden_base_operator!r} could not be applied: "
            f"{base_audit.get('reason')}"
        )

    mutated_model_text, top_audit = apply_marked_top_mutation(
        source_model_text,
        var_suffix=_short_hash(task_id),
    )
    if not top_audit.get("applied"):
        raise RuntimeError(
            f"Marked top mutation could not be applied: {top_audit.get('reason')}"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "task_id": task_id,
        "failure_type": declared_failure_type,
        "declared_failure_type": declared_failure_type,
        "expected_stage": expected_stage,
        "source_model_path": source_model_path,
        "source_library": source_library,
        "model_hint": model_hint,
        "v0_3_6_family_id": FAMILY_ID,
        "dual_layer_mutation": True,
        "marker_only_repair": False,
        "multi_parameter_hidden_base": True,
        "hidden_base_operator": hidden_base_operator,
        "hidden_base_param_names": list(hidden_base_param_names or []),
        "hidden_base_replacement_values": list(hidden_base_replacement_values or []),
        "mutation_spec": {
            "hidden_base": {
                "operator": hidden_base_operator,
                "audit": base_audit,
                "has_gateforge_marker": False,
            },
            "marked_top": {
                "operator": "simulate_error_top_injection",
                "audit": top_audit,
                "has_gateforge_marker": True,
                "removed_by_rule": "rule_simulate_error_injection_repair",
                "marker_comment": TOP_LAYER_COMMENT,
            },
        },
        "source_model_text": source_model_text,
        "mutated_model_text": mutated_model_text,
        "baseline_expectation": {
            "single_sweep_expected_to_fail": True,
            "reason": "hidden_base_mutates_multiple_parameters",
        },
        "post_restore_target_buckets": [
            "residual_semantic_conflict_after_restore",
            "stalled_search_after_progress",
        ],
        "expected_execution_path": {
            "round_1": "marked_top_removed_by_rule_engine",
            "round_2": "hidden_multi_parameter_residual_exposed",
            "round_3_plus": "llm_or_multistep_policy_must_go_beyond_single_parameter_sweep",
        },
    }


def write_task_json(
    *,
    out_path: str | Path,
    task: dict,
) -> None:
    _write_json(out_path, task)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a v0.3.6 dual-layer multi-parameter harder-lane task.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--source-model", required=True)
    parser.add_argument("--source-model-path", required=True)
    parser.add_argument("--source-library", required=True)
    parser.add_argument("--model-hint", required=True)
    parser.add_argument("--hidden-base-operator", default="paired_value_collapse", choices=sorted(HIDDEN_BASE_OPERATORS))
    parser.add_argument("--declared-failure-type", default="simulate_error")
    parser.add_argument("--expected-stage", default="simulate")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    clean_source_text = Path(args.source_model).read_text(encoding="utf-8")
    task = build_dual_layer_multi_param_task(
        task_id=str(args.task_id),
        clean_source_text=clean_source_text,
        source_model_path=str(args.source_model_path),
        source_library=str(args.source_library),
        model_hint=str(args.model_hint),
        hidden_base_operator=str(args.hidden_base_operator),
        declared_failure_type=str(args.declared_failure_type),
        expected_stage=str(args.expected_stage),
    )
    write_task_json(out_path=str(args.out), task=task)
    print(json.dumps({"task_id": task["task_id"], "family_id": task["v0_3_6_family_id"], "hidden_base_operator": task["hidden_base_operator"]}))


if __name__ == "__main__":
    main()
