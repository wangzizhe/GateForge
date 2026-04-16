"""Runtime semantic oracle for RC time-constant benchmark cases.

This module provides the simulation-based behavioral contract used by the
v0.19.15 semantic benchmark family. The contract is intentionally grounded in
simulation output rather than text markers so the LLM cannot solve the task by
reading an explicit arithmetic hint from the model text.
"""
from __future__ import annotations

import csv
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .agent_modelica_stage_branch_controller_v1 import build_multistep_eval

DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
TARGET_RESPONSE_FRACTION = 1.0 - math.exp(-1.0)
RESPONSE_TOLERANCE = 0.08
MIN_REQUIRED_DEVIATION = 0.12
_SIMULATION_CACHE: dict[tuple[str, str, float, int], tuple[bool, dict | None, str]] = {}


def _extract_named_numeric_value(text: str, name: str) -> float | None:
    match = re.search(
        rf"\b{re.escape(str(name))}\s*=\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\b",
        str(text or ""),
    )
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_annotation_numeric_value(text: str, field_name: str) -> float | None:
    match = re.search(
        rf"\b{re.escape(str(field_name))}\s*=\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\b",
        str(text or ""),
    )
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_model_name(text: str) -> str:
    match = re.search(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)\b", str(text or ""))
    return str(match.group(1) or "").strip() if match else ""


def _extract_validation_target(text: str) -> str:
    match = re.search(r"//\s*gateforge_validation_targets\s*:\s*([^\n]+)", str(text or ""))
    if not match:
        return "VS1.v"
    raw = str(match.group(1) or "").strip()
    first = raw.split(",", 1)[0].strip()
    return first or "VS1.v"


def _extract_event_time(text: str) -> float:
    step_match = re.search(
        r"StepVoltage\s+[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\bstartTime\s*=\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
        str(text or ""),
    )
    if step_match:
        try:
            return float(step_match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _extract_contract_spec(source_model_text: str) -> dict | None:
    model_name = _extract_model_name(source_model_text)
    if not model_name:
        return None
    expected_tau = _extract_named_numeric_value(source_model_text, "expectedTimeConstant")
    if expected_tau is None:
        resistance = _extract_named_numeric_value(source_model_text, "R_charge")
        capacitance = _extract_named_numeric_value(source_model_text, "C_store")
        if resistance is None or capacitance is None:
            return None
        expected_tau = resistance * capacitance
    stop_time = _extract_annotation_numeric_value(source_model_text, "StopTime")
    event_time = _extract_event_time(source_model_text)
    if stop_time is None:
        stop_time = max(0.25, event_time + (expected_tau * 6.0))
    intervals = _extract_annotation_numeric_value(source_model_text, "NumberOfIntervals")
    if intervals is None:
        intervals = 600.0
    return {
        "model_name": model_name,
        "observation_var": _extract_validation_target(source_model_text),
        "expected_tau": float(expected_tau),
        "event_time": float(event_time),
        "stop_time": float(stop_time),
        "intervals": max(100, int(intervals)),
    }


def _get_lib_cache() -> Path:
    raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    return Path(raw) if raw else (Path.home() / ".openmodelica" / "libraries")


def _run_simulation_csv(
    *,
    model_text: str,
    model_name: str,
    stop_time: float,
    intervals: int,
) -> tuple[bool, dict | None, str]:
    cache_key = (model_name, model_text, float(stop_time), int(intervals))
    if cache_key in _SIMULATION_CACHE:
        return _SIMULATION_CACHE[cache_key]
    mos = (
        "loadModel(Modelica);\n"
        'loadFile("/workspace/model.mo");\n'
        f'simulate({model_name}, startTime=0.0, stopTime={stop_time}, '
        f'numberOfIntervals={intervals}, tolerance=1e-06, outputFormat="csv");\n'
        "getErrorString();\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / ".omc_home" / ".openmodelica" / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "model.mo").write_text(model_text, encoding="utf-8")
        (tmp_path / "run.mos").write_text(mos, encoding="utf-8")
        lib_cache = _get_lib_cache()
        lib_cache.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-e",
                "HOME=/workspace/.omc_home",
                "-v",
                f"{tmp}:/workspace",
                "-v",
                f"{str(lib_cache)}:/workspace/.omc_home/.openmodelica/libraries",
                "-w",
                "/workspace",
                DOCKER_IMAGE,
                "omc",
                "run.mos",
            ],
            capture_output=True,
            text=True,
            timeout=240,
        )
        output = (result.stdout or "") + (result.stderr or "")
        match = re.search(r'resultFile\s*=\s*"([^"]+)"', output)
        if result.returncode != 0 or not match:
            cached = (False, None, output[-1200:])
            _SIMULATION_CACHE[cache_key] = cached
            return cached
        result_file = str(match.group(1) or "").strip()
        csv_path = Path(result_file)
        if not csv_path.is_absolute():
            csv_path = tmp_path / csv_path.name
        elif str(csv_path).startswith("/workspace/"):
            csv_path = tmp_path / csv_path.name
        if not csv_path.exists():
            cached = (False, None, f"csv_result_missing:{result_file}\n{output[-1200:]}")
            _SIMULATION_CACHE[cache_key] = cached
            return cached
        data = _parse_csv_result(csv_path)
        cached = (True, data, "")
        _SIMULATION_CACHE[cache_key] = cached
        return cached


def _parse_csv_result(path: Path) -> dict[str, list[float]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f"empty csv result: {path}")
    headers = [str(item or "").strip().strip('"') for item in rows[0]]
    columns: dict[str, list[float]] = {header: [] for header in headers if header}
    for row in rows[1:]:
        if len(row) != len(headers):
            continue
        for idx, value in enumerate(row):
            header = headers[idx]
            if not header:
                continue
            try:
                columns[header].append(float(value))
            except ValueError:
                columns[header].append(float("nan"))
    return columns


def _pick_nearest_value(times: list[float], values: list[float], target_time: float) -> float:
    best_idx = min(range(len(times)), key=lambda i: abs(times[i] - target_time))
    return float(values[best_idx])


def _pick_pre_event_value(times: list[float], values: list[float], event_time: float) -> float:
    candidate_idx = 0
    for idx, t in enumerate(times):
        if t <= event_time + 1e-9:
            candidate_idx = idx
        else:
            break
    return float(values[candidate_idx])


def _average_tail(values: list[float]) -> float:
    if not values:
        return float("nan")
    start = max(0, int(len(values) * 0.95))
    tail = values[start:] or values[-1:]
    return sum(tail) / len(tail)


def _response_fraction(*, data: dict[str, list[float]], observation_var: str, event_time: float, tau: float) -> dict:
    times = list(data.get("time") or [])
    values = list(data.get(observation_var) or [])
    if not times or not values or len(times) != len(values):
        raise ValueError(f"missing observation variable: {observation_var}")
    baseline = _pick_pre_event_value(times, values, event_time)
    final_value = _average_tail(values)
    tau_value = _pick_nearest_value(times, values, event_time + tau)
    amplitude = final_value - baseline
    if abs(amplitude) <= 1e-9:
        raise ValueError("degenerate_response_amplitude")
    fraction = (tau_value - baseline) / amplitude
    return {
        "baseline": baseline,
        "final": final_value,
        "tau_value": tau_value,
        "fraction": fraction,
    }


def evaluate_semantic_time_constant_contract(
    *,
    current_text: str,
    source_model_text: str,
    failure_type: str,
) -> dict | None:
    declared = str(failure_type or "").strip().lower()
    if declared not in {"behavioral_contract_fail", "semantic_initial_value_wrong_but_compiles"}:
        return None
    spec = _extract_contract_spec(source_model_text)
    if spec is None:
        return build_multistep_eval(
            stage="stage_1",
            transition_reason="semantic_time_constant_contract_spec_missing",
            transition_seen=False,
            pass_all=False,
            bucket="semantic_time_constant_contract_spec_missing",
            scenario_results=[{"scenario_id": "semantic_time_constant", "pass": False}],
        )

    source_ok, source_data, source_err = _run_simulation_csv(
        model_text=source_model_text,
        model_name=str(spec["model_name"]),
        stop_time=float(spec["stop_time"]),
        intervals=int(spec["intervals"]),
    )
    if not source_ok or source_data is None:
        return build_multistep_eval(
            stage="stage_1",
            transition_reason="semantic_time_constant_source_simulation_failed",
            transition_seen=False,
            pass_all=False,
            bucket="semantic_time_constant_source_simulation_failed",
            scenario_results=[{
                "scenario_id": "semantic_time_constant",
                "pass": False,
                "source_error": source_err,
            }],
        )

    current_model_name = _extract_model_name(current_text)
    if not current_model_name:
        return build_multistep_eval(
            stage="stage_1",
            transition_reason="semantic_time_constant_model_name_missing",
            transition_seen=False,
            pass_all=False,
            bucket="semantic_time_constant_model_name_missing",
            scenario_results=[{"scenario_id": "semantic_time_constant", "pass": False}],
        )

    current_ok, current_data, current_err = _run_simulation_csv(
        model_text=current_text,
        model_name=current_model_name,
        stop_time=float(spec["stop_time"]),
        intervals=int(spec["intervals"]),
    )
    if not current_ok or current_data is None:
        return build_multistep_eval(
            stage="stage_1",
            transition_reason="semantic_time_constant_current_simulation_failed",
            transition_seen=False,
            pass_all=False,
            bucket="semantic_time_constant_current_simulation_failed",
            scenario_results=[{
                "scenario_id": "semantic_time_constant",
                "pass": False,
                "current_error": current_err,
            }],
        )

    try:
        source_metrics = _response_fraction(
            data=source_data,
            observation_var=str(spec["observation_var"]),
            event_time=float(spec["event_time"]),
            tau=float(spec["expected_tau"]),
        )
        current_metrics = _response_fraction(
            data=current_data,
            observation_var=str(spec["observation_var"]),
            event_time=float(spec["event_time"]),
            tau=float(spec["expected_tau"]),
        )
    except ValueError as exc:
        return build_multistep_eval(
            stage="stage_1",
            transition_reason="semantic_time_constant_trace_parse_failed",
            transition_seen=False,
            pass_all=False,
            bucket="semantic_time_constant_trace_parse_failed",
            scenario_results=[{
                "scenario_id": "semantic_time_constant",
                "pass": False,
                "trace_error": str(exc),
            }],
        )

    source_fraction = float(source_metrics["fraction"])
    current_fraction = float(current_metrics["fraction"])
    source_valid = abs(source_fraction - TARGET_RESPONSE_FRACTION) <= RESPONSE_TOLERANCE
    current_valid = abs(current_fraction - TARGET_RESPONSE_FRACTION) <= RESPONSE_TOLERANCE
    deviation = abs(current_fraction - source_fraction)

    passed = bool(source_valid and current_valid)
    scenario = {
        "scenario_id": "semantic_time_constant",
        "pass": passed,
        "observation_var": str(spec["observation_var"]),
        "expected_tau": float(spec["expected_tau"]),
        "event_time": float(spec["event_time"]),
        "source_fraction_at_tau": source_fraction,
        "current_fraction_at_tau": current_fraction,
        "target_fraction": TARGET_RESPONSE_FRACTION,
        "response_tolerance": RESPONSE_TOLERANCE,
        "deviation_from_source": deviation,
        "min_required_deviation": MIN_REQUIRED_DEVIATION,
    }

    if not source_valid:
        return build_multistep_eval(
            stage="stage_1",
            transition_reason="semantic_time_constant_source_contract_invalid",
            transition_seen=False,
            pass_all=False,
            bucket="semantic_time_constant_source_contract_invalid",
            scenario_results=[scenario],
        )

    if not passed:
        scenario["pass"] = False
        if deviation < MIN_REQUIRED_DEVIATION and not current_valid:
            bucket = "semantic_time_constant_contract_miss"
        else:
            bucket = "semantic_time_constant_contract_miss"
        return build_multistep_eval(
            stage="stage_1",
            transition_reason=bucket,
            transition_seen=False,
            pass_all=False,
            bucket=bucket,
            scenario_results=[scenario],
        )

    return build_multistep_eval(
        stage="passed",
        transition_reason="semantic_time_constant_contract_satisfied",
        transition_seen=True,
        pass_all=True,
        bucket="",
        scenario_results=[scenario],
    )
