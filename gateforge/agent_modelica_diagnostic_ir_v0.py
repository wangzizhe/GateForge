from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_diagnostic_ir_v0"


def _token_set(text: str) -> set[str]:
    return {x for x in re.split(r"[^A-Za-z0-9_]+", str(text or "").lower()) if x}


def _extract_objects(output: str) -> dict:
    text = str(output or "")
    undefined_symbols = sorted(set(re.findall(r"__gf_undef_[0-9]+", text)))
    injected_states = sorted(set(re.findall(r"__gf_state_[0-9]+", text)))
    models = sorted(set(re.findall(r"(?i)\bmodel:\s*([A-Za-z_][A-Za-z0-9_]*)", text)))
    if not models:
        models = sorted(set(re.findall(r"(?i)\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\s+not\s+found", text)))
    return {
        "undefined_symbols": undefined_symbols,
        "injected_states": injected_states,
        "model_candidates": models,
    }


def _suggest_actions(error_type: str) -> list[str]:
    if error_type == "script_parse_error":
        return [
            "remove injected parser-breaking tokens before planner edits",
            "rerun checkModel immediately after pre-repair",
        ]
    if error_type == "model_check_error":
        return [
            "resolve undefined symbols and connector mismatches first",
            "rerun checkModel before simulation",
        ]
    if error_type == "simulate_error":
        return [
            "stabilize initialization and solver-facing parameters",
            "rerun simulate after compile passes",
        ]
    return []


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
    reason = ""
    stage = "none"

    if not check_model_pass:
        stage = "check"
        if "no viable alternative near token" in lower or "syntax error" in lower:
            err_type = "script_parse_error"
            reason = "compile/syntax error"
        elif "not found" in lower or "undeclared" in lower or "failed to load package" in lower:
            err_type = "model_check_error"
            reason = "model check failed"
        else:
            err_type = "model_check_error"
            reason = "model check failed"
    elif not simulate_pass:
        stage = "simulate"
        if "assert" in lower:
            err_type = "simulate_error"
            reason = "assertion triggered"
        elif "integrator failed" in lower or "step size" in lower:
            err_type = "simulate_error"
            reason = "numerical instability"
        else:
            err_type = "simulate_error"
            reason = "simulation failed"

    if err_type == "none":
        stage = "none"
        reason = ""

    objects = _extract_objects(output)
    declared = str(declared_failure_type or "").strip().lower()
    expected = str(expected_stage or "").strip().lower()
    diagnostic_tokens = _token_set(lower)
    confidence = 0.9 if err_type != "none" else 1.0
    if err_type == "model_check_error" and "script_parse_error" in diagnostic_tokens:
        confidence = 0.6
    if expected and stage != "none" and expected != stage:
        confidence = min(confidence, 0.7)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "error_type": err_type,
        "stage": stage,
        "reason": reason,
        "expected_stage": expected,
        "declared_failure_type": declared,
        "confidence": round(confidence, 4),
        "objects": objects,
        "suggested_actions": _suggest_actions(err_type),
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
    print(json.dumps({"status": "PASS", "error_type": payload.get("error_type"), "stage": payload.get("stage")}))


if __name__ == "__main__":
    main()
