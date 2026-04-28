from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .agent_modelica_semantic_time_constant_oracle_v1 import (
    TARGET_RESPONSE_FRACTION,
    _response_fraction,
    _run_simulation_csv,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_behavioral_oracle_v0_29_3"


def _extract_model_name(model_text: str) -> str:
    match = re.search(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)", model_text, re.MULTILINE)
    return str(match.group(1) or "") if match else ""


def evaluate_time_constant_behavior(
    *,
    model_text: str,
    behavioral: dict[str, Any],
    simulate: dict[str, Any],
) -> dict[str, Any]:
    model_name = _extract_model_name(model_text)
    if not model_name:
        return {"pass": False, "reason": "model_name_missing"}
    expected_tau = float(behavioral.get("expected_tau") or 0.0)
    tolerance = float(behavioral.get("tolerance") or 0.08)
    observation_variable = str(
        behavioral.get("observation_variable")
        or behavioral.get("variable")
        or behavioral.get("target_variable")
        or ""
    )
    if not observation_variable:
        return {"pass": False, "reason": "missing_observation_variable_in_task_config"}
    event_time = float(behavioral.get("event_time") or 0.0)
    stop_time = float(simulate.get("stop_time") or max(0.25, event_time + expected_tau * 6.0))
    intervals = int(simulate.get("intervals") or 600)
    ok, data, error = _run_simulation_csv(
        model_text=model_text,
        model_name=model_name,
        stop_time=stop_time,
        intervals=intervals,
    )
    if not ok or data is None:
        return {"pass": False, "reason": "simulation_failed", "error": error}
    try:
        metrics = _response_fraction(
            data=data,
            observation_var=observation_variable,
            event_time=event_time,
            tau=expected_tau,
        )
    except ValueError as exc:
        return {"pass": False, "reason": "trace_parse_failed", "error": str(exc)}
    fraction = float(metrics["fraction"])
    deviation = abs(fraction - TARGET_RESPONSE_FRACTION)
    passed = bool(math.isfinite(fraction) and deviation <= tolerance)
    return {
        "pass": passed,
        "reason": "time_constant_pass" if passed else "time_constant_miss",
        "observation_variable": observation_variable,
        "expected_tau": expected_tau,
        "event_time": event_time,
        "fraction_at_tau": fraction,
        "target_fraction": TARGET_RESPONSE_FRACTION,
        "tolerance": tolerance,
        "deviation": deviation,
        "metrics": metrics,
    }


def evaluate_spec_assertions_behavior(
    *,
    model_text: str,
    behavioral: dict[str, Any],
    simulate: dict[str, Any],
) -> dict[str, Any]:
    model_name = _extract_model_name(model_text)
    if not model_name:
        return {"pass": False, "reason": "model_name_missing"}
    stop_time = float(simulate.get("stop_time") or 0.1)
    intervals = int(simulate.get("intervals") or 100)
    ok, data, error = _run_simulation_csv(
        model_text=model_text,
        model_name=model_name,
        stop_time=stop_time,
        intervals=intervals,
    )
    if not ok or data is None:
        return {"pass": False, "reason": "simulation_failed", "error": error}
    assertions = list(behavioral.get("assertions") or [])
    results: list[dict[str, Any]] = []
    for assertion in assertions:
        variable = str(assertion.get("variable") or "")
        values = list(data.get(variable) or [])
        times = list(data.get("time") or [])
        if not variable or not values or len(values) != len(times):
            results.append({"pass": False, "reason": "variable_missing", "variable": variable})
            continue
        if "at_time" in assertion and "range" in assertion:
            target_time = float(assertion["at_time"])
            idx = min(range(len(times)), key=lambda i: abs(times[i] - target_time))
            value = float(values[idx])
            bounds = list(assertion.get("range") or [])
            lo, hi = float(bounds[0]), float(bounds[1])
            results.append({
                "pass": lo <= value <= hi,
                "variable": variable,
                "at_time": target_time,
                "value": value,
                "range": [lo, hi],
            })
    passed = bool(results) and all(bool(row.get("pass")) for row in results)
    return {
        "pass": passed,
        "reason": "spec_assertions_pass" if passed else "spec_assertions_miss",
        "assertion_results": results,
    }


def evaluate_benchmark_behavior(task: dict[str, Any], model_text: str) -> dict[str, Any]:
    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    behavioral = verification.get("behavioral") if isinstance(verification.get("behavioral"), dict) else None
    simulate = verification.get("simulate") if isinstance(verification.get("simulate"), dict) else {}
    if behavioral is None:
        return {"pass": True, "reason": "no_behavioral_oracle"}
    behavior_type = str(behavioral.get("type") or "").lower()
    if behavior_type == "pass_through":
        return {"pass": True, "reason": "pass_through"}
    if behavior_type == "time_constant":
        return evaluate_time_constant_behavior(model_text=model_text, behavioral=behavioral, simulate=simulate)
    if behavior_type == "spec_assertions":
        return evaluate_spec_assertions_behavior(model_text=model_text, behavioral=behavioral, simulate=simulate)
    return {"pass": False, "reason": f"unsupported_behavioral_type:{behavior_type}"}


def build_behavioral_oracle_summary(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary = {
        "version": "v0.29.3",
        "status": "PASS",
        "analysis_scope": "benchmark_behavioral_oracle",
        "supported_behavioral_types": ["pass_through", "time_constant", "spec_assertions"],
        "decision": "benchmark_behavioral_oracle_ready",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
