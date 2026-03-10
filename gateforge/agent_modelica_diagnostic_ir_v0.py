from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


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
    et = str(error_type or "").strip().lower()
    if not et:
        return "none"
    if et in CANONICAL_ERROR_TYPES:
        return et
    mapped = LEGACY_TO_CANONICAL.get(et)
    if mapped:
        return mapped
    return et


def canonical_stage_from_failure_type_v0(error_type: str) -> str:
    et = canonical_error_type_v0(error_type)
    if et in {"model_check_error"}:
        return "check"
    if et in {"simulate_error", "semantic_regression", "numerical_instability"}:
        return "simulate"
    # constraint violations can happen in either check or simulate;
    # return "none" and let caller fall back to task expected_stage.
    if et == "constraint_violation":
        return "none"
    return "none"


def _token_set(text: str) -> set[str]:
    return {x for x in re.split(r"[^A-Za-z0-9_]+", str(text or "").lower()) if x}


def _extract_objects(output: str) -> dict:
    text = str(output or "")
    lower = text.lower()
    undefined_symbols = sorted(set(re.findall(r"__gf_undef_[0-9]+", text)))
    injected_states = sorted(set(re.findall(r"__gf_state_[0-9]+", text)))
    models = sorted(set(re.findall(r"(?i)\bmodel:\s*([A-Za-z_][A-Za-z0-9_]*)", text)))
    if not models:
        models = sorted(set(re.findall(r"(?i)\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\s+not\s+found", text)))

    token_hints = sorted(
        set(
            [
                str(x).strip()
                for x in re.findall(r"(?i)near token:\s*([^\s\]\)\n\r;]+)", text)
                if str(x).strip()
            ]
        )
    )
    connector_hints = sorted(
        set(
            [
                str(x).strip()
                for x in re.findall(r"(?i)connect\(([^\)]*)\)", text)
                if str(x).strip()
            ]
        )
    )
    assertion_hints = sorted(
        set(
            [
                str(x).strip()
                for x in re.findall(r"(?i)gateforge_[a-z0-9_]+", text)
                if str(x).strip()
            ]
        )
    )
    solver_hints = []
    for marker in ("integrator failed", "step size", "nonlinear system", "homotopy", "division by zero", "timeout"):
        if marker in lower:
            solver_hints.append(marker)

    return {
        "undefined_symbols": undefined_symbols,
        "injected_states": injected_states,
        "model_candidates": models,
        "token_hints": token_hints,
        "connector_hints": connector_hints,
        "assertion_hints": assertion_hints,
        "solver_hints": sorted(set(solver_hints)),
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _structural_count_mismatch(text: str) -> tuple[int, int] | None:
    m = re.search(r"class\s+[a-z_][a-z0-9_]*\s+has\s+([0-9]+)\s+equation\(s\)\s+and\s+([0-9]+)\s+variable\(s\)", str(text or ""), re.IGNORECASE)
    if not m:
        return None
    try:
        equations = int(m.group(1))
        variables = int(m.group(2))
    except Exception:
        return None
    if equations == variables:
        return None
    return equations, variables


def _classify_check_failure(lower: str) -> tuple[str, str, str, str]:
    parse_markers = (
        "no viable alternative near token",
        "lexer failed to recognize",
        "parse error",
        "syntax error",
        "unexpected token",
    )
    if _contains_any(lower, parse_markers):
        return "model_check_error", "parse_lexer_error", "compile/syntax error", "script_parse_error"

    if _contains_any(
        lower,
        (
            "under-determined",
            "underdetermined",
            "too few equations",
            "not fully determined",
            "structurally singular",
            "gateforge_underconstrained_probe",
        ),
    ):
        return "model_check_error", "underconstrained_system", "structural balance failed", "model_check_error"
    structural_mismatch = _structural_count_mismatch(lower)
    if structural_mismatch:
        equations, variables = structural_mismatch
        if equations < variables:
            return "model_check_error", "underconstrained_system", "structural balance failed", "model_check_error"

    if _contains_any(lower, ("type mismatch", "incompatible connector", "connector")) and "connect" in lower:
        return "model_check_error", "connector_mismatch", "connector mismatch", "model_check_error"

    if _contains_any(lower, ("unit", "dimension", "inconsistent")):
        return "constraint_violation", "unit_inconsistency", "constraint/unit mismatch", "constraint_violation"

    if _contains_any(lower, ("assert", "assertion")):
        return "constraint_violation", "assertion_violation", "assertion triggered", "constraint_violation"

    if _contains_any(lower, ("not found", "undeclared", "failed to load package", "unknown variable", "not in scope")):
        return "model_check_error", "undefined_symbol", "model check failed", "model_check_error"

    return "model_check_error", "compile_failure_unknown", "model check failed", "model_check_error"


def _classify_sim_failure(lower: str) -> tuple[str, str, str]:
    if _contains_any(
        lower,
        (
            "under-determined",
            "underdetermined",
            "too few equations",
            "not fully determined",
            "structurally singular",
            "gateforge_underconstrained_probe",
        ),
    ):
        return "model_check_error", "underconstrained_system", "structural balance failed"

    if _contains_any(lower, ("gateforge_initialization_infeasible", "initialization infeasible", "initial equation")):
        return "simulate_error", "init_failure", "initialization failed"

    if _contains_any(lower, ("timeoutexpired", "timed out", "timeout expired", "simulation timeout")):
        return "numerical_instability", "timeout", "simulation timeout"

    if _contains_any(lower, ("division by zero", "floating point exception")):
        return "numerical_instability", "division_by_zero", "division by zero"

    if _contains_any(lower, ("integrator failed", "step size", "stiff", "newton", "solver")):
        return "numerical_instability", "solver_divergence", "numerical instability"

    if _contains_any(lower, ("initialization", "homotopy", "initial conditions", "nonlinear system")):
        return "simulate_error", "init_failure", "initialization failed"

    if _contains_any(lower, ("assert", "assertion")):
        return "constraint_violation", "assertion_violation", "assertion triggered"

    return "simulate_error", "simulation_failure_unknown", "simulation failed"


def _suggest_actions(error_type: str, error_subtype: str) -> list[str]:
    et = canonical_error_type_v0(error_type)
    sub = str(error_subtype or "").strip().lower()

    if et == "model_check_error" and sub.startswith("parse_"):
        return [
            "remove injected parser-breaking tokens before planner edits",
            "rerun checkModel immediately after pre-repair",
        ]
    if et == "model_check_error" and sub == "connector_mismatch":
        return [
            "align connector types and endpoint port names",
            "rerun checkModel before simulation",
        ]
    if et == "model_check_error" and sub == "underconstrained_system":
        return [
            "restore dropped connects and structural balance before simulate",
            "rerun checkModel and verify the model is square before repair rollout",
        ]
    if et == "model_check_error":
        return [
            "resolve undefined symbols and connector mismatches first",
            "rerun checkModel before simulation",
        ]
    if et == "numerical_instability":
        return [
            "stabilize solver-facing dynamics and initialization",
            "rerun simulate with conservative integration settings",
        ]
    if et == "simulate_error":
        return [
            "stabilize initialization and solver-facing parameters",
            "rerun simulate after compile passes",
        ]
    if et == "constraint_violation":
        return [
            "inspect and repair violated constraints/assertions",
            "rerun checkModel and simulate after repair",
        ]
    if et == "semantic_regression":
        return [
            "compare candidate trajectory against baseline targets",
            "apply minimal localized semantic repair and rerun",
        ]
    return []


def _confidence(error_type: str, error_subtype: str, expected_stage: str, stage: str, declared_failure_type: str) -> float:
    et = canonical_error_type_v0(error_type)
    sub = str(error_subtype or "").strip().lower()
    declared = canonical_error_type_v0(declared_failure_type)
    expected = str(expected_stage or "").strip().lower()

    if et == "none":
        return 1.0

    conf = 0.88
    if sub in {"parse_lexer_error", "undefined_symbol", "connector_mismatch", "solver_divergence", "timeout", "assertion_violation"}:
        conf = 0.94
    elif sub in {"compile_failure_unknown", "simulation_failure_unknown"}:
        conf = 0.78

    if expected and stage != "none" and expected != stage:
        conf = min(conf, 0.7)
    if declared not in {"", "none"} and declared in CANONICAL_ERROR_TYPES and declared != et:
        conf = min(conf, 0.68)
    return round(max(0.05, min(conf, 1.0)), 4)


def _taxonomy_stage(error_type: str, observed_phase: str) -> str:
    canonical_stage = canonical_stage_from_failure_type_v0(error_type)
    if canonical_stage in {"check", "simulate"}:
        return canonical_stage
    phase = str(observed_phase or "").strip().lower()
    if phase in {"check", "simulate"}:
        return phase
    return "none"


def build_diagnostic_ir_v0(
    *,
    output: str,
    check_model_pass: bool,
    simulate_pass: bool,
    expected_stage: str = "",
    declared_failure_type: str = "",
) -> dict:
    lower = str(output or "").lower()
    err_type = "none"
    err_subtype = "none"
    reason = ""
    observed_phase = "none"
    legacy_type = "none"

    if not check_model_pass:
        observed_phase = "check"
        err_type, err_subtype, reason, legacy_type = _classify_check_failure(lower)
    elif not simulate_pass:
        observed_phase = "simulate"
        err_type, err_subtype, reason = _classify_sim_failure(lower)
        legacy_type = err_type

    if err_type == "none":
        observed_phase = "none"
        reason = ""
        err_subtype = "none"
        legacy_type = "none"

    stage = _taxonomy_stage(err_type, observed_phase)

    objects = _extract_objects(output)
    declared_raw = str(declared_failure_type or "").strip().lower()
    declared = canonical_error_type_v0(declared_raw)
    expected = str(expected_stage or "").strip().lower()

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "error_type": canonical_error_type_v0(err_type),
        "error_subtype": err_subtype,
        "error_type_legacy": legacy_type,
        "stage": stage,
        "observed_phase": observed_phase,
        "reason": reason,
        "expected_stage": expected,
        "declared_failure_type": declared_raw,
        "declared_failure_type_canonical": declared,
        "confidence": _confidence(
            error_type=err_type,
            error_subtype=err_subtype,
            expected_stage=expected,
            stage=stage,
            declared_failure_type=declared,
        ),
        "objects": objects,
        "suggested_actions": _suggest_actions(err_type, err_subtype),
        "compat": {
            "legacy_script_parse_error": bool(legacy_type == "script_parse_error"),
            "canonical_error_type": canonical_error_type_v0(err_type),
        },
    }
    return payload


def _load_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="latin-1")


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build diagnostic IR v0 from OMC output")
    parser.add_argument("--output-text", default="")
    parser.add_argument("--output-file", default="")
    parser.add_argument("--check-model-pass", choices=["true", "false"], required=True)
    parser.add_argument("--simulate-pass", choices=["true", "false"], required=True)
    parser.add_argument("--expected-stage", default="")
    parser.add_argument("--declared-failure-type", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_diagnostic_ir_v0/diagnostic.json")
    args = parser.parse_args()

    text = str(args.output_text or "")
    if not text and str(args.output_file).strip():
        text = _load_text(str(args.output_file))
    payload = build_diagnostic_ir_v0(
        output=text,
        check_model_pass=str(args.check_model_pass).lower() == "true",
        simulate_pass=str(args.simulate_pass).lower() == "true",
        expected_stage=str(args.expected_stage or ""),
        declared_failure_type=str(args.declared_failure_type or ""),
    )
    _write_json(args.out, payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "error_type": payload.get("error_type"),
                "error_subtype": payload.get("error_subtype"),
                "stage": payload.get("stage"),
            }
        )
    )


if __name__ == "__main__":
    main()
