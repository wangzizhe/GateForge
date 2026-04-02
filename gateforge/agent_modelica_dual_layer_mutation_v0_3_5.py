"""
Dual-layer mutation generator for v0.3.5 post-restore harder lanes.

Design rationale (from Block 0 root-cause analysis):

  The executor unconditionally calls _apply_source_model_repair() in each round.
  However, source_repair has a guard:
    if current_text == source_model_text: return applied=False, reason="current_text_matches_source"

  This means: if source_model_text is the hidden-base-mutation state (not the clean original),
  then after the marked top layer is removed in Round 1, current_text == source_model_text,
  and source_repair is a no-op. The LLM must then diagnose the residual hidden base mutation.

Layer structure:

  clean_source_text
       |
       | hidden_base_mutation (no gateforge_ marker, produces stage_4/5 failure)
       v
  source_model_text  <-- GateForge sees this as the "reference" source
       |
       | marked_top_mutation (uses existing gateforge_ marker, removed by rule_engine Round 1)
       v
  mutated_model_text <-- GateForge starts here

Execution path (target behavior):
  Round 1: rule engine removes marked_top → current_text = source_model_text
           source_repair: current_text == source_model_text → applied=False
  Round 2: hidden_base_mutation still present → simulate FAIL (stage_4 or stage_5)
           source_repair: current_text == source_model_text → applied=False (again)
           LLM invoked → planner_invoked = true
  Round 3+: LLM must diagnose and repair the hidden base mutation

Hidden base mutation operators (produce stage_4 / stage_5 failures):

  init_value_collapse:
    - Find a numeric parameter with start/initial value
    - Change it to a value that causes initialization failure
    - Target: models with Real parameters that have physical bounds
    - Example: change a positive-definite mass/resistance to zero or negative

  stiff_time_constant_injection:
    - Find a time constant parameter (tau, T, timeConstant, etc.)
    - Reduce it to near-zero to cause solver stiffness
    - Target: models with first-order dynamics (low-pass filters, thermal models)
    - Example: tau = 1.0 → tau = 1e-9

  init_equation_sign_flip:
    - Flip the sign of a term in an initial equation
    - Produces an impossible initial condition
    - Target: models with explicit initial equation blocks
    - Example: initial equation x = A → x = -A

Marked top mutation (removed by rule engine Round 1):

  simulate_error_top_injection:
    - Inject a __gf_state_xxx variable (existing simulate_error injection format)
    - rule_simulate_error_injection_repair removes it in Round 1
    - Requires declared_failure_type = "simulate_error" for the top layer trigger
    - IMPORTANT: the task's declared_failure_type must still reflect the hidden base mutation
      type, not "simulate_error", to avoid confusion in attribution

  NOTE on declared_failure_type for dual-layer tasks:
    The recommended declared_failure_type for dual-layer mutation tasks is
    "post_restore_init_residual" or "post_restore_numerical_residual",
    which are NOT in the executor's source restore dispatch.
    The marked top layer is a secondary signal, not the primary failure type.

Schema: agent_modelica_dual_layer_mutation_v0_3_5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_dual_layer_mutation_v0_3_5"

# Declared failure types NOT in executor source restore dispatch (safe for dual-layer).
# "simulate_error" is the operative type: rule_simulate_error_injection_repair requires
# declared_failure_type == "simulate_error" to fire and remove the marked top layer.
# It is NOT in the executor source-restore dispatch, so source_repair remains a no-op.
SAFE_DUAL_LAYER_FAILURE_TYPES = {
    "simulate_error",
    "post_restore_init_residual",
    "post_restore_numerical_residual",
    "post_restore_semantic_residual",
}

# The gateforge marker used by the marked top mutation.
# Uses __gf_tau_ prefix with a decimal-digit-only suffix so it matches the rule regex:
#   re.search(r"\b(__gf_(?:state|tau)_\d+)\b", line)
# Injected as a benign `parameter Real` declaration (no effect on check_model or simulate).
# Removed in Round 1 by rule_simulate_error_injection_repair when
# declared_failure_type == "simulate_error".
TOP_LAYER_TAU_PREFIX = "__gf_tau_"
TOP_LAYER_COMMENT = "// GateForge mutation: zero time constant"

# Legacy alias kept for validate_dual_layer_text_pair (searches for this prefix)
TOP_LAYER_STATE_VAR_PREFIX = TOP_LAYER_TAU_PREFIX

# Hidden base mutation operator identifiers
HIDDEN_BASE_OPERATORS = {
    "init_value_collapse",
    "stiff_time_constant_injection",
    "init_equation_sign_flip",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_hash(text: str) -> str:
    """Return an 8-digit decimal hash (matches rule regex \\d+)."""
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    return str(h % 100_000_000).zfill(8)


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def apply_init_value_collapse(
    model_text: str,
    *,
    target_param_pattern: str = r"parameter\s+Real\s+(\w+)\s*=\s*([0-9]+\.?[0-9]*)",
    collapse_value: str = "0.0",
    max_targets: int = 1,
) -> tuple[str, dict]:
    """
    Hidden base mutation: collapse a Real parameter value toward zero.

    Targets parameters like:
      parameter Real mass = 1.0;
      parameter Real resistance = 100.0;

    Changes the first match to collapse_value (default 0.0), which typically
    causes initialization failure when the parameter is used as a divisor or
    physical lower bound.

    Does NOT inject any gateforge_ markers — this is the hidden layer.

    Returns (mutated_text, audit_dict).
    """
    pattern = re.compile(target_param_pattern)
    lines = model_text.splitlines(keepends=True)
    mutations: list[dict] = []
    result_lines = list(lines)
    count = 0
    for i, line in enumerate(lines):
        if count >= max_targets:
            break
        m = pattern.search(line)
        if not m:
            continue
        param_name = m.group(1)
        original_value = m.group(2)
        if original_value == collapse_value:
            continue
        mutated_line = line[: m.start(2)] + collapse_value + line[m.end(2) :]
        result_lines[i] = mutated_line
        mutations.append({
            "line_index": i,
            "param_name": param_name,
            "original_value": original_value,
            "new_value": collapse_value,
        })
        count += 1

    if not mutations:
        return model_text, {"applied": False, "reason": "no_matching_parameter_found"}

    mutated_text = "".join(result_lines)
    return mutated_text, {
        "applied": True,
        "operator": "init_value_collapse",
        "mutations": mutations,
        "has_gateforge_marker": False,
    }


def apply_stiff_time_constant_injection(
    model_text: str,
    *,
    stiff_value: str = "1e-9",
    max_targets: int = 1,
) -> tuple[str, dict]:
    """
    Hidden base mutation: reduce a time constant to near-zero (stiffness injection).

    Targets parameters named: tau, T, timeConstant, time_constant, Td, Ti, Tr
    with positive numeric values like:
      parameter Real tau = 1.0;
      parameter Real T = 0.5;

    Changes to stiff_value (default 1e-9), causing extreme stiffness and
    solver divergence during simulation (stage_5 failure).

    No gateforge_ markers — hidden layer.
    """
    # Common time constant parameter names in Modelica
    name_pattern = re.compile(
        r"parameter\s+Real\s+(tau|T|timeConstant|time_constant|Td|Ti|Tr|T_(?:open|close|d|i))\s*"
        r"(?:\([^)]*\))?\s*=\s*([0-9]+\.?[0-9]*(?:e[+-]?[0-9]+)?)",
        re.IGNORECASE,
    )
    lines = model_text.splitlines(keepends=True)
    mutations: list[dict] = []
    result_lines = list(lines)
    count = 0
    for i, line in enumerate(lines):
        if count >= max_targets:
            break
        m = name_pattern.search(line)
        if not m:
            continue
        param_name = m.group(1)
        original_value = m.group(2)
        # Skip if already very small
        try:
            if float(original_value) < 1e-6:
                continue
        except ValueError:
            continue
        mutated_line = line[: m.start(2)] + stiff_value + line[m.end(2) :]
        result_lines[i] = mutated_line
        mutations.append({
            "line_index": i,
            "param_name": param_name,
            "original_value": original_value,
            "new_value": stiff_value,
        })
        count += 1

    if not mutations:
        return model_text, {"applied": False, "reason": "no_time_constant_parameter_found"}

    mutated_text = "".join(result_lines)
    return mutated_text, {
        "applied": True,
        "operator": "stiff_time_constant_injection",
        "mutations": mutations,
        "has_gateforge_marker": False,
    }


def apply_init_equation_sign_flip(
    model_text: str,
    *,
    target_lhs_names: list[str] | tuple[str, ...] | None = None,
    max_targets: int = 1,
) -> tuple[str, dict]:
    """
    Hidden base mutation: flip the sign of a term in an initial equation.

    Targets lines inside initial equation blocks like:
      x = some_expression;
      der(x) = 0;

    Changes:
      x = expr; → x = -(expr);

    This makes the initial condition unsatisfiable when the variable
    has a physical constraint (e.g. x must be positive).

    No gateforge_ markers — hidden layer.
    """
    # Find initial equation block
    in_init_block = False
    block_depth = 0
    lines = model_text.splitlines(keepends=True)
    result_lines = list(lines)
    mutations: list[dict] = []
    count = 0

    # Simple pattern: look for initial equation section
    init_eq_start = re.compile(r"^\s*initial\s+equation\b", re.IGNORECASE)
    eq_assignment = re.compile(r"^(\s*)(\w[\w.]*(?:\([^)]*\))?)\s*=\s*(.+?);\s*$")
    section_end = re.compile(r"^\s*(equation|algorithm|protected|public|end\s+\w+)\b", re.IGNORECASE)
    wanted = {str(x).strip() for x in (target_lhs_names or []) if str(x).strip()}

    for i, line in enumerate(lines):
        if count >= max_targets:
            break
        stripped = line.strip()
        if init_eq_start.match(stripped):
            in_init_block = True
            continue
        if in_init_block:
            if section_end.match(stripped) and not init_eq_start.match(stripped):
                in_init_block = False
                continue
            m = eq_assignment.match(line.rstrip("\n\r"))
            if m:
                indent = m.group(1)
                lhs = m.group(2)
                if wanted and lhs not in wanted:
                    continue
                rhs = m.group(3).strip()
                # Skip trivial zero assignments
                if rhs in {"0", "0.0"}:
                    continue
                # Skip if already negated
                if rhs.startswith("-"):
                    continue
                new_rhs = f"-({rhs})"
                new_line = f"{indent}{lhs} = {new_rhs};\n"
                result_lines[i] = new_line
                mutations.append({
                    "line_index": i,
                    "lhs": lhs,
                    "original_rhs": rhs,
                    "new_rhs": new_rhs,
                })
                count += 1

    if not mutations:
        return model_text, {
            "applied": False,
            "reason": (
                "target_initial_equation_lhs_not_found"
                if wanted
                else "no_initial_equation_target_found"
            ),
        }

    return "".join(result_lines), {
        "applied": True,
        "operator": "init_equation_sign_flip",
        "mutations": mutations,
        "has_gateforge_marker": False,
        "target_lhs_names": [row["lhs"] for row in mutations],
    }


def apply_marked_top_mutation(
    model_text: str,
    *,
    var_suffix: str | None = None,
) -> tuple[str, dict]:
    """
    Marked top mutation: inject a benign __gf_tau_ parameter that rule engine removes in Round 1.

    Design requirements:
      1. Must NOT break check_model (no compile errors — previous design used array start
         value for scalar which caused stage_3 type error and blocked rule from firing).
      2. Marker name must match rule regex: __gf_(?:state|tau)_\\d+ (decimal digits only,
         not hex — previous design used hex hash which the regex didn't match).
      3. declared_failure_type must be "simulate_error" for rule guard to pass.

    The injected parameter is valid Modelica (`parameter Real __gf_tau_DIGITS = 1e-9`)
    and has no effect on check_model or simulation. It is removed by
    rule_simulate_error_injection_repair when declared_failure_type == "simulate_error".

    After removal, current_text == source_model_text (hidden base state).
    The hidden base mutation then causes the actual stage_4/5 simulate failure.
    """
    if var_suffix is None:
        var_suffix = _short_hash(model_text)

    tau_var = f"{TOP_LAYER_TAU_PREFIX}{var_suffix}"
    # Inject a single benign parameter declaration before the equation section.
    # parameter Real does NOT need an equation, so no underdetermined-system error.
    injection_pattern = re.compile(r"^(\s*equation\b)", re.MULTILINE | re.IGNORECASE)
    m = injection_pattern.search(model_text)
    if not m:
        return model_text, {"applied": False, "reason": "no_equation_section_found"}

    injection = f"  parameter Real {tau_var} = 1e-9; {TOP_LAYER_COMMENT}\n"
    insert_pos = m.start()
    mutated_text = model_text[:insert_pos] + injection + model_text[insert_pos:]

    return mutated_text, {
        "applied": True,
        "operator": "simulate_error_top_injection",
        "tau_var": tau_var,
        "has_gateforge_marker": True,
        "marker_comment": TOP_LAYER_COMMENT,
        "removed_by_rule": "rule_simulate_error_injection_repair",
        "required_declared_failure_type": "simulate_error",
    }


def build_dual_layer_task(
    *,
    task_id: str,
    clean_source_text: str,
    source_model_path: str,
    source_library: str,
    model_hint: str,
    hidden_base_operator: str,
    declared_failure_type: str = "simulate_error",
    expected_stage: str = "simulate",
    hidden_base_kwargs: dict | None = None,
) -> dict:
    """
    Build a complete dual-layer mutation task record.

    Returns a task dict with:
    - task_id, schema metadata
    - source_model_text (hidden base applied)
    - mutated_model_text (hidden base + marked top)
    - mutation_spec (operator details)
    - dual_layer_mutation=True flag
    - pre-filled admission gate fields
    """
    if declared_failure_type not in SAFE_DUAL_LAYER_FAILURE_TYPES:
        raise ValueError(
            f"declared_failure_type={declared_failure_type!r} is not in SAFE_DUAL_LAYER_FAILURE_TYPES. "
            f"Use one of: {sorted(SAFE_DUAL_LAYER_FAILURE_TYPES)}"
        )
    if hidden_base_operator not in HIDDEN_BASE_OPERATORS:
        raise ValueError(
            f"hidden_base_operator={hidden_base_operator!r} not in HIDDEN_BASE_OPERATORS."
        )

    # Apply hidden base mutation
    kwargs = hidden_base_kwargs or {}
    if hidden_base_operator == "init_value_collapse":
        source_model_text, base_audit = apply_init_value_collapse(clean_source_text, **kwargs)
    elif hidden_base_operator == "stiff_time_constant_injection":
        source_model_text, base_audit = apply_stiff_time_constant_injection(clean_source_text, **kwargs)
    elif hidden_base_operator == "init_equation_sign_flip":
        source_model_text, base_audit = apply_init_equation_sign_flip(clean_source_text, **kwargs)
    else:
        raise ValueError(f"Unknown operator: {hidden_base_operator}")

    if not base_audit.get("applied"):
        raise RuntimeError(
            f"Hidden base mutation {hidden_base_operator!r} could not be applied: "
            f"{base_audit.get('reason')}"
        )

    # Apply marked top mutation on top of hidden base
    var_suffix = _short_hash(task_id)
    mutated_model_text, top_audit = apply_marked_top_mutation(
        source_model_text, var_suffix=var_suffix
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
        # Dual-layer mutation fields
        "dual_layer_mutation": True,
        "marker_only_repair": False,
        "hidden_base_operator": hidden_base_operator,
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
            },
        },
        # Texts for GateForge executor
        "source_model_text": source_model_text,
        "mutated_model_text": mutated_model_text,
        # Admission gate pre-fill (planner fields filled after GateForge run)
        "planner_invoked": None,
        "resolution_path": None,
        "dominant_stage_subtype": None,
        "rounds_used": None,
        "llm_request_count": None,
        # Expected execution path annotation
        "expected_execution_path": {
            "round_1": "marked_top_removed_by_rule_engine",
            "round_2": "hidden_base_still_present_llm_invoked",
            "round_3_plus": "llm_diagnoses_and_repairs_hidden_base",
        },
    }


def validate_dual_layer_text_pair(
    source_model_text: str,
    mutated_model_text: str,
) -> dict:
    """
    Structural validation of a dual-layer text pair.

    Checks:
    1. source_model_text and mutated_model_text are different
    2. mutated_model_text contains gateforge_ markers (marked top present)
    3. source_model_text does NOT contain gateforge_ markers (hidden base only)
    4. After removing marked lines from mutated_model_text, result == source_model_text
    """
    reasons: list[str] = []

    if source_model_text == mutated_model_text:
        reasons.append("source_and_mutated_are_identical")

    has_marker_in_source = TOP_LAYER_STATE_VAR_PREFIX in source_model_text
    if has_marker_in_source:
        reasons.append("source_model_text_contains_gateforge_marker_unexpected")

    has_marker_in_mutated = TOP_LAYER_STATE_VAR_PREFIX in mutated_model_text
    if not has_marker_in_mutated:
        reasons.append("mutated_model_text_missing_gateforge_marker")

    # Check that stripping marked lines from mutated restores source
    if has_marker_in_mutated and not has_marker_in_source:
        stripped_lines = [
            line for line in mutated_model_text.splitlines(keepends=True)
            if TOP_LAYER_STATE_VAR_PREFIX not in line
        ]
        stripped_text = "".join(stripped_lines)
        if stripped_text.strip() != source_model_text.strip():
            reasons.append("stripped_mutated_does_not_match_source")

    status = "PASS" if not reasons else "FAIL"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reasons": reasons,
    }


def run_from_spec(
    *,
    spec_path: str,
    out_dir: str,
) -> dict:
    """
    Build dual-layer mutation tasks from a batch spec JSON file.

    Spec format:
    {
      "tasks": [
        {
          "task_id": "...",
          "source_model_path": "...",   // path to clean Modelica file
          "source_library": "...",
          "model_hint": "...",
          "hidden_base_operator": "init_value_collapse" | "stiff_time_constant_injection" | "init_equation_sign_flip",
          "declared_failure_type": "post_restore_init_residual",
          "hidden_base_kwargs": {}      // optional, passed to operator
        }
      ]
    }
    """
    spec = _load_json(spec_path)
    task_specs = [r for r in (spec.get("tasks") or []) if isinstance(r, dict)]

    out_root = Path(out_dir)
    results: list[dict] = []
    errors: list[dict] = []

    for spec_row in task_specs:
        task_id = str(spec_row.get("task_id") or "")
        source_model_path = str(spec_row.get("source_model_path") or "")
        p = Path(source_model_path)
        if not p.exists():
            errors.append({"task_id": task_id, "error": f"source_model_path_not_found:{source_model_path}"})
            continue
        try:
            clean_source_text = p.read_text(encoding="utf-8")
        except Exception as exc:
            errors.append({"task_id": task_id, "error": f"read_error:{exc}"})
            continue
        try:
            task = build_dual_layer_task(
                task_id=task_id,
                clean_source_text=clean_source_text,
                source_model_path=source_model_path,
                source_library=str(spec_row.get("source_library") or ""),
                model_hint=str(spec_row.get("model_hint") or ""),
                hidden_base_operator=str(spec_row.get("hidden_base_operator") or ""),
                declared_failure_type=str(
                    spec_row.get("declared_failure_type") or "post_restore_init_residual"
                ),
                hidden_base_kwargs=dict(spec_row.get("hidden_base_kwargs") or {}),
            )
        except Exception as exc:
            errors.append({"task_id": task_id, "error": str(exc)})
            continue

        # Structural validation
        validation = validate_dual_layer_text_pair(
            task["source_model_text"], task["mutated_model_text"]
        )
        task["text_pair_validation"] = validation
        if validation["status"] != "PASS":
            errors.append({"task_id": task_id, "error": f"text_pair_validation:{validation['reasons']}"})
            continue

        # Write individual task JSON
        task_path = out_root / f"{task_id}.json"
        _write_json(task_path, task)
        results.append({"task_id": task_id, "status": "ok", "path": str(task_path)})

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "total_input_specs": len(task_specs),
        "generated_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
    }
    _write_json(out_root / "generation_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate dual-layer mutation tasks for v0.3.5 Block A post-restore harder lane."
    )
    parser.add_argument(
        "--spec",
        required=True,
        help="JSON spec file with task definitions (see run_from_spec docstring).",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/agent_modelica_dual_layer_mutation_v0_3_5",
        help="Output directory for generated task JSON files.",
    )
    args = parser.parse_args()
    summary = run_from_spec(spec_path=str(args.spec), out_dir=str(args.out_dir))
    print(json.dumps({
        "generated_count": summary["generated_count"],
        "error_count": summary["error_count"],
    }, indent=2))
    return 0 if summary["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
