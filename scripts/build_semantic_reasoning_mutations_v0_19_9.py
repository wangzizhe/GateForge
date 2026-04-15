"""
Build v0.19.9 semantic reasoning mutation candidates.

The family is intentionally small: each case compiles and simulates, but fails
a semantic product contract. OMC does not name the faulty parameter; admission
requires the model structure relation R*C = expectedTimeConstant.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_behavioral_contract_evaluator_v1 import (
    evaluate_behavioral_contract_from_model_text,
)

OUT_DIR = REPO_ROOT / "artifacts" / "semantic_reasoning_mutations_v0_19_9"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


@dataclass(frozen=True)
class SemanticSpec:
    candidate_id: str
    model_name: str
    resistor: float
    source_capacitor: float
    mutated_capacitor: float
    voltage: float


SPECS = [
    SemanticSpec("v0199_semantic_rc_small_tau", "V0199SemanticRCSmallV0", 100.0, 0.01, 0.0001, 10.0),
    SemanticSpec("v0199_semantic_rc_medium_tau", "V0199SemanticRCMediumV0", 500.0, 0.002, 0.00002, 5.0),
    SemanticSpec("v0199_semantic_rc_large_tau", "V0199SemanticRCLargeV0", 1000.0, 0.001, 0.00001, 12.0),
]


def _get_lib_cache() -> Path:
    raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    return Path(raw) if raw else (Path.home() / ".openmodelica" / "libraries")


def build_model_text(spec: SemanticSpec, *, capacitor: float) -> str:
    expected_tau = spec.resistor * spec.source_capacitor
    return f"""model {spec.model_name}
  // gateforge_semantic_contract_kind: product_equals_target
  // gateforge_semantic_contract_operands: R_charge,C_store
  // gateforge_semantic_contract_target: expectedTimeConstant
  // gateforge_semantic_contract_relative_tolerance: 0.02
  // gateforge_source_blind_multistep_llm_forcing:true
  // gateforge_source_blind_multistep_llm_trigger:semantic_contract_miss
  parameter Real supplyVoltage = {spec.voltage};
  parameter Real expectedTimeConstant = {expected_tau};
  parameter Real R_charge = {spec.resistor};
  parameter Real C_store = {capacitor};
  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=supplyVoltage);
  Modelica.Electrical.Analog.Basic.Resistor R1(R=R_charge);
  Modelica.Electrical.Analog.Basic.Capacitor C1(C=C_store);
  Modelica.Electrical.Analog.Sensors.VoltageSensor VS1;
  Modelica.Electrical.Analog.Basic.Ground G;
equation
  connect(V1.p, R1.p);
  connect(R1.n, C1.p);
  connect(C1.n, V1.n);
  connect(V1.n, G.p);
  connect(VS1.p, C1.p);
  connect(VS1.n, G.p);
  annotation(experiment(StartTime=0.0, StopTime=1.0, NumberOfIntervals=100, Tolerance=1e-06));
end {spec.model_name};
"""


def _run_omc(model_text: str, model_name: str, action: str) -> tuple[bool, str]:
    if action == "check":
        command = f"checkModel({model_name});\n"
        timeout = 90
    elif action == "simulate":
        command = f"simulate({model_name}, startTime=0.0, stopTime=0.1, numberOfIntervals=20, tolerance=1e-06);\n"
        timeout = 180
    else:
        raise ValueError(f"unsupported OMC action: {action}")

    mos = (
        "loadModel(Modelica);\n"
        'loadFile("/workspace/model.mo");\n'
        f"{command}"
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
                "docker", "run", "--rm",
                "--user", f"{os.getuid()}:{os.getgid()}",
                "-e", "HOME=/workspace/.omc_home",
                "-v", f"{tmp}:/workspace",
                "-v", f"{str(lib_cache)}:/workspace/.omc_home/.openmodelica/libraries",
                "-w", "/workspace",
                DOCKER_IMAGE,
                "omc", "run.mos",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    output = result.stdout + result.stderr
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    error_text = ""
    for line in lines:
        if line.startswith('"') and len(line) > 2:
            error_text = line.strip('"')
    if action == "check":
        passed = any(line == "true" for line in lines) and "Error" not in error_text
    else:
        passed = any("resultFile" in line for line in lines) and "Error" not in error_text
    return passed, error_text if error_text else output[:800]


def build_candidates() -> tuple[list[dict], dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []
    rejected = []
    for spec in SPECS:
        source_text = build_model_text(spec, capacitor=spec.source_capacitor)
        mutated_text = build_model_text(spec, capacitor=spec.mutated_capacitor)
        source_path = OUT_DIR / f"{spec.candidate_id}_source.mo"
        mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
        source_path.write_text(source_text, encoding="utf-8")
        mutated_path.write_text(mutated_text, encoding="utf-8")

        source_check, source_check_log = _run_omc(source_text, spec.model_name, "check")
        source_sim, source_sim_log = _run_omc(source_text, spec.model_name, "simulate")
        mutated_check, mutated_check_log = _run_omc(mutated_text, spec.model_name, "check")
        mutated_sim, mutated_sim_log = _run_omc(mutated_text, spec.model_name, "simulate")
        source_contract = evaluate_behavioral_contract_from_model_text(
            current_text=source_text,
            source_model_text=source_text,
            failure_type="semantic_initial_value_wrong_but_compiles",
        )
        mutated_contract = evaluate_behavioral_contract_from_model_text(
            current_text=mutated_text,
            source_model_text=source_text,
            failure_type="semantic_initial_value_wrong_but_compiles",
        )
        admitted = (
            source_check
            and source_sim
            and mutated_check
            and mutated_sim
            and bool((source_contract or {}).get("pass"))
            and not bool((mutated_contract or {}).get("pass"))
        )
        row = {
            "candidate_id": spec.candidate_id,
            "task_id": spec.candidate_id,
            "benchmark_family": "semantic_initial_value_wrong_but_compiles",
            "mutation_family": "semantic_product_contract_rc_tau",
            "description": "RC model compiles and simulates, but C_store breaks R_charge*C_store = expectedTimeConstant.",
            "source_model_path": str(source_path),
            "mutated_model_path": str(mutated_path),
            "failure_type": "semantic_initial_value_wrong_but_compiles",
            "expected_stage": "simulate",
            "expected_turns": 2,
            "workflow_goal": (
                "Restore the RC semantic behavior: the charging time constant must satisfy "
                "R_charge*C_store = expectedTimeConstant while preserving the circuit topology."
            ),
            "requires_nonlocal_or_semantic_reasoning": True,
            "failure_localization_not_explicit_tag": True,
            "omc_localization_sufficient": False,
            "semantic_contract": {
                "kind": "product_equals_target",
                "operands": ["R_charge", "C_store"],
                "target": "expectedTimeConstant",
                "fault_parameter": "C_store",
            },
            "admission_checks": {
                "source_check": source_check,
                "source_simulate": source_sim,
                "mutated_check": mutated_check,
                "mutated_simulate": mutated_sim,
                "source_contract_pass": bool((source_contract or {}).get("pass")),
                "mutated_contract_pass": bool((mutated_contract or {}).get("pass")),
            },
            "admission_status": "PASS" if admitted else "FAIL",
            "admission_log_excerpt": {
                "source_check": source_check_log[:400],
                "source_simulate": source_sim_log[:400],
                "mutated_check": mutated_check_log[:400],
                "mutated_simulate": mutated_sim_log[:400],
            },
            "benchmark_version": "v0.19.9",
        }
        if admitted:
            candidates.append(row)
        else:
            rejected.append(row)

    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.19.9",
        "family": "semantic_initial_value_wrong_but_compiles",
        "candidate_count": len(SPECS),
        "admitted_count": len(candidates),
        "rejected_count": len(rejected),
        "admission_status": "PASS" if len(candidates) == len(SPECS) else "PARTIAL",
        "hard_gates": [
            "source_clean_and_omc_admitted",
            "mutated_check_and_simulate_pass",
            "behavior_oracle_fails_mutated_model",
            "failure_localization_not_explicit_tag",
            "requires_nonlocal_or_semantic_reasoning",
        ],
        "candidates": candidates,
        "rejected": rejected,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return candidates, summary


def main() -> int:
    candidates, summary = build_candidates()
    print(f"admitted={len(candidates)}/{summary['candidate_count']} -> {OUT_DIR}/admitted_cases.jsonl")
    return 0 if summary["admission_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
