from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .agent_modelica_difficulty_layer_spec_v1 import (
    STAGE_SUBTYPE_INIT,
    STAGE_SUBTYPE_NONE,
    STAGE_SUBTYPE_PARSE,
    STAGE_SUBTYPE_RUNTIME,
    STAGE_SUBTYPE_STAGE3_TYPE_CONNECTOR,
    STAGE_SUBTYPE_STRUCTURAL,
)


SCHEMA_VERSION = "agent_modelica_diagnostic_ir_v0"
CANONICAL_ERROR_TYPES = {
    "model_check_error",
    "simulate_error",
    "semantic_regression",
    "numerical_instability",
    "constraint_violation",
}
LEGACY_TO_CANONICAL = {
    "script_parse_error": "model_check_error",
}


def canonical_error_type_v0(error_type: str) -> str:
    value = str(error_type or "").strip().lower()
    if not value:
        return "none"
    return LEGACY_TO_CANONICAL.get(value, value)


def canonical_stage_from_failure_type_v0(error_type: str) -> str:
    value = canonical_error_type_v0(error_type)
    if value == "model_check_error":
        return "check"
    if value in {"simulate_error", "semantic_regression", "numerical_instability"}:
        return "simulate"
    return "none"


def dominant_stage_subtype_v0(
    *,
    error_type: str,
    error_subtype: str,
    observed_phase: str = "",
) -> str:
    value = canonical_error_type_v0(error_type)
    subtype = str(error_subtype or "").strip().lower()
    phase = str(observed_phase or "").strip().lower()

    if value == "none":
        return STAGE_SUBTYPE_NONE
    if subtype.startswith("parse_"):
        return STAGE_SUBTYPE_PARSE
    if subtype in {"underconstrained_system", "overconstrained_system", "undefined_symbol"}:
        return STAGE_SUBTYPE_STRUCTURAL
    if subtype in {"connector_mismatch", "array_dimension_mismatch", "parameter_binding_error"}:
        return STAGE_SUBTYPE_STAGE3_TYPE_CONNECTOR
    if subtype in {"init_failure"}:
        return STAGE_SUBTYPE_INIT
    if value in {"simulate_error", "numerical_instability"}:
        return STAGE_SUBTYPE_RUNTIME if phase == "simulate" else STAGE_SUBTYPE_INIT
    return STAGE_SUBTYPE_STRUCTURAL


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _structural_count_mismatch(text: str) -> tuple[int, int] | None:
    match = re.search(
        r"class\s+[a-z_][a-z0-9_]*\s+has\s+([0-9]+)\s+equation\(s\)\s+and\s+([0-9]+)\s+variable\(s\)",
        str(text or ""),
        re.IGNORECASE,
    )
    if not match:
        return None
    equations = int(match.group(1))
    variables = int(match.group(2))
    if equations == variables:
        return None
    return equations, variables


def _classify_output(output: str, check_model_pass: bool, simulate_pass: bool) -> tuple[str, str, str]:
    text = str(output or "")
    lower = text.lower()
    if check_model_pass and simulate_pass:
        return "none", "none", "no failure observed"

    if _contains_any(
        lower,
        (
            "parse error",
            "syntax error",
            "unexpected token",
            "lexer failed",
            "no viable alternative",
        ),
    ):
        return "model_check_error", "parse_lexer_error", "compile or syntax error"

    mismatch = _structural_count_mismatch(lower)
    if mismatch:
        equations, variables = mismatch
        if equations < variables:
            return "model_check_error", "underconstrained_system", "structural balance failed"
        return "constraint_violation", "overconstrained_system", "structural balance failed"

    if _contains_any(lower, ("under-determined", "underdetermined", "too few equations")):
        return "model_check_error", "underconstrained_system", "structural balance failed"
    if _contains_any(lower, ("over-determined", "overdetermined", "too many equations")):
        return "constraint_violation", "overconstrained_system", "structural balance failed"
    if "class" in lower and "not found" in lower:
        return "model_check_error", "undefined_symbol", "referenced class not found"
    if "connect" in lower and _contains_any(lower, ("type mismatch", "incompatible connector", "connector")):
        return "model_check_error", "connector_mismatch", "connector mismatch"
    if _contains_any(lower, ("dimension mismatch", "array dimension", "subscript", "size mismatch")):
        return "model_check_error", "array_dimension_mismatch", "array dimension mismatch"
    if _contains_any(lower, ("binding", "modifier", "modification")) and _contains_any(
        lower, ("type mismatch", "wrong type", "cannot")
    ):
        return "model_check_error", "parameter_binding_error", "parameter binding failed"

    if check_model_pass and not simulate_pass:
        if _contains_any(lower, ("initialization", "initial system", "singular")):
            return "simulate_error", "init_failure", "simulation initialization failed"
        if _contains_any(lower, ("division by zero", "integrator failed", "solver", "nonlinear system")):
            return "numerical_instability", "runtime_failure", "simulation runtime failed"
        return "simulate_error", "runtime_failure", "simulation failed"

    return "model_check_error", "compile_failure_unknown", "model check failed"


def build_diagnostic_ir_v0(
    *,
    output: str,
    check_model_pass: bool,
    simulate_pass: bool,
    expected_stage: str = "",
    declared_failure_type: str = "",
) -> dict[str, Any]:
    error_type, error_subtype, reason = _classify_output(
        output=output,
        check_model_pass=bool(check_model_pass),
        simulate_pass=bool(simulate_pass),
    )
    observed_stage = canonical_stage_from_failure_type_v0(error_type)
    if observed_stage == "none" and expected_stage:
        observed_stage = str(expected_stage or "").strip().lower()
    stage_subtype = dominant_stage_subtype_v0(
        error_type=error_type,
        error_subtype=error_subtype,
        observed_phase=observed_stage,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "error_type": canonical_error_type_v0(error_type),
        "error_subtype": error_subtype,
        "reason": reason,
        "observed_stage": observed_stage,
        "stage_subtype": stage_subtype,
        "declared_failure_type": canonical_error_type_v0(declared_failure_type),
    }
