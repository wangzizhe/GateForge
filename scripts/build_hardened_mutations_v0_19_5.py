"""
Build and OMC-admit hardened mutation candidates for v0.19.5.

This expands beyond the v0.19.4 undefined-variable/assert masking families with
workflow-proximal electrical model errors:
  - component parameter reference errors
  - component modifier name errors
  - dropped connection topology errors
  - connection endpoint typo errors
  - extra equation count errors

Outputs:
  artifacts/hardened_mutations_v0_19_5/
    candidates.jsonl
    summary.json
    *.mo
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = (
    REPO_ROOT
    / "artifacts"
    / "agent_modelica_electrical_frozen_taskset_v1_smoke"
    / "source_models"
)
OUT_DIR = REPO_ROOT / "artifacts" / "hardened_mutations_v0_19_5"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


@dataclass(frozen=True)
class SourceModel:
    source_file: str
    model_name: str
    component_line: str
    modifier_from: str
    modifier_to: str
    parameter_from: str
    parameter_to: str
    connect_line: str
    extra_equation: str


SOURCE_MODELS = [
    SourceModel(
        source_file="small_rc_constant_v0.mo",
        model_name="SmallRCConstantV0",
        component_line="Modelica.Electrical.Analog.Basic.Resistor R1(R=100.0);",
        modifier_from="R=100.0",
        modifier_to="resistance=100.0",
        parameter_from="R=100.0",
        parameter_to="R=gateforge_R1_nominal",
        connect_line="  connect(R1.n, C1.p);",
        extra_equation="  C1.v = 0.0;",
    ),
    SourceModel(
        source_file="small_rl_step_v0.mo",
        model_name="SmallRLStepV0",
        component_line="Modelica.Electrical.Analog.Basic.Inductor L1(L=0.1);",
        modifier_from="L=0.1",
        modifier_to="inductance=0.1",
        parameter_from="L=0.1",
        parameter_to="L=gateforge_L1_nominal",
        connect_line="  connect(CS1.n, L1.p);",
        extra_equation="  L1.i = 0.0;",
    ),
    SourceModel(
        source_file="small_r_divider_v0.mo",
        model_name="SmallRDividerV0",
        component_line="Modelica.Electrical.Analog.Basic.Resistor R2(R=1000.0);",
        modifier_from="R=1000.0",
        modifier_to="resistance=1000.0",
        parameter_from="R=1000.0",
        parameter_to="R=gateforge_R2_nominal",
        connect_line="  connect(R1.n, R2.p);",
        extra_equation="  R2.v = 0.0;",
    ),
    SourceModel(
        source_file="medium_ladder_rc_v0.mo",
        model_name="MediumLadderRCV0",
        component_line="Modelica.Electrical.Analog.Basic.Capacitor C2(C=0.0015);",
        modifier_from="C=0.0015",
        modifier_to="capacitance=0.0015",
        parameter_from="C=0.0015",
        parameter_to="C=gateforge_C2_nominal",
        connect_line="  connect(R2.n, C2.p);",
        extra_equation="  C2.v = 0.0;",
    ),
    SourceModel(
        source_file="medium_parallel_rc_v0.mo",
        model_name="MediumParallelRCV0",
        component_line="Modelica.Electrical.Analog.Basic.Resistor R2(R=220.0);",
        modifier_from="R=220.0",
        modifier_to="resistance=220.0",
        parameter_from="R=220.0",
        parameter_to="R=gateforge_R2_nominal",
        connect_line="  connect(R2.n, C2.p);",
        extra_equation="  C2.v = 0.0;",
    ),
    SourceModel(
        source_file="medium_rlc_series_v0.mo",
        model_name="MediumRLCSeriesV0",
        component_line="Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.001);",
        modifier_from="C=0.001",
        modifier_to="capacitance=0.001",
        parameter_from="C=0.001",
        parameter_to="C=gateforge_C1_nominal",
        connect_line="  connect(L1.n, C1.p);",
        extra_equation="  C1.v = 0.0;",
    ),
    SourceModel(
        source_file="large_rc_ladder4_v0.mo",
        model_name="LargeRCLadder4V0",
        component_line="Modelica.Electrical.Analog.Basic.Capacitor C4(C=0.001);",
        modifier_from="C=0.001",
        modifier_to="capacitance=0.001",
        parameter_from="C=0.001",
        parameter_to="C=gateforge_C4_nominal",
        connect_line="  connect(R4.n, C4.p);",
        extra_equation="  C4.v = 0.0;",
    ),
    SourceModel(
        source_file="large_dual_source_ladder_v0.mo",
        model_name="LargeDualSourceLadderV0",
        component_line="Modelica.Electrical.Analog.Basic.Inductor L2(L=0.02);",
        modifier_from="L=0.02",
        modifier_to="inductance=0.02",
        parameter_from="L=0.02",
        parameter_to="L=gateforge_L2_nominal",
        connect_line="  connect(R2.n, L2.p);",
        extra_equation="  L2.i = 0.0;",
    ),
]


MUTATION_FAMILIES = [
    "component_parameter_reference_error",
    "component_modifier_name_error",
    "connection_topology_drop",
    "connection_endpoint_typo",
    "equation_count_extra_constraint",
]


def _get_lib_cache() -> Path:
    raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    return Path(raw) if raw else (Path.home() / ".openmodelica" / "libraries")


def _run_omc(model_text: str, model_name: str, action: str) -> tuple[bool, str]:
    if action == "check":
        command = f"checkModel({model_name});\n"
        timeout = 90
    elif action == "simulate":
        command = (
            f"simulate({model_name}, startTime=0.0, stopTime=0.05, "
            "numberOfIntervals=20, tolerance=1e-06);\n"
        )
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


def _replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise ValueError(f"mutation anchor not found: {old}")
    return text.replace(old, new, 1)


def _insert_after_equation(text: str, line_to_insert: str) -> str:
    lines = text.splitlines()
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and line.strip() == "equation":
            new_lines.append(line_to_insert)
            inserted = True
    if not inserted:
        raise ValueError("equation section not found")
    return "\n".join(new_lines) + "\n"


def _mutate(source_text: str, source: SourceModel, family: str) -> str:
    if family == "component_parameter_reference_error":
        mutated_line = source.component_line.replace(source.parameter_from, source.parameter_to)
        return _replace_once(source_text, source.component_line, mutated_line)
    if family == "component_modifier_name_error":
        mutated_line = source.component_line.replace(source.modifier_from, source.modifier_to)
        return _replace_once(source_text, source.component_line, mutated_line)
    if family == "connection_topology_drop":
        return _replace_once(source_text, source.connect_line + "\n", "")
    if family == "connection_endpoint_typo":
        if ".p);" in source.connect_line:
            mutated_line = source.connect_line.replace(".p);", ".pin);", 1)
        elif ".n);" in source.connect_line:
            mutated_line = source.connect_line.replace(".n);", ".neg);", 1)
        else:
            raise ValueError(f"unsupported connection endpoint line: {source.connect_line}")
        return _replace_once(source_text, source.connect_line, mutated_line)
    if family == "equation_count_extra_constraint":
        return _insert_after_equation(source_text, source.extra_equation)
    raise ValueError(f"unknown mutation family: {family}")


def _difficulty_prior(family: str, observed_stage: str) -> str:
    if family == "component_parameter_reference_error":
        return "moderate"
    if family == "component_modifier_name_error":
        return "moderate"
    if family == "connection_topology_drop":
        return "hard"
    if family == "connection_endpoint_typo":
        return "moderate"
    if family == "equation_count_extra_constraint":
        return "hard" if observed_stage == "simulate" else "moderate"
    return "unknown"


def _verify_candidate(source: SourceModel, family: str, source_text: str) -> dict:
    source_sim_pass, source_sim_err = _run_omc(source_text, source.model_name, "simulate")
    if not source_sim_pass:
        return {"ok": False, "reason": f"source simulate fails: {source_sim_err[:300]}"}

    try:
        mutated_text = _mutate(source_text, source, family)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}

    check_pass, check_err = _run_omc(mutated_text, source.model_name, "check")
    if not check_pass:
        return {
            "ok": True,
            "mutated_text": mutated_text,
            "observed_stage": "check",
            "failure_type": "model_check_error",
            "observed_error": check_err,
        }

    sim_pass, sim_err = _run_omc(mutated_text, source.model_name, "simulate")
    if sim_pass:
        return {"ok": False, "reason": "mutated model unexpectedly simulates cleanly"}
    return {
        "ok": True,
        "mutated_text": mutated_text,
        "observed_stage": "simulate",
        "failure_type": "simulate_error",
        "observed_error": sim_err,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []
    results = []

    for source in SOURCE_MODELS:
        source_path = SOURCE_DIR / source.source_file
        source_text = source_path.read_text(encoding="utf-8")
        source_slug = source.source_file.removesuffix(".mo").replace("_v0", "")
        for family in MUTATION_FAMILIES:
            family_slug = {
                "component_parameter_reference_error": "param_ref",
                "component_modifier_name_error": "modifier_name",
                "connection_topology_drop": "topology_drop",
                "connection_endpoint_typo": "endpoint_typo",
                "equation_count_extra_constraint": "extra_equation",
            }[family]
            cid = f"v0195_{family_slug}_{source_slug}"
            print(f"\n[{cid}] {family} on {source.model_name}")
            result = _verify_candidate(source, family, source_text)
            if not result["ok"]:
                print(f"  ✗ admission failed: {result['reason']}")
                results.append({"candidate_id": cid, "status": "FAIL", "reason": result["reason"]})
                continue

            mut_path = OUT_DIR / f"{cid}.mo"
            mut_path.write_text(result["mutated_text"], encoding="utf-8")
            observed_stage = result["observed_stage"]
            print(f"  ✓ admitted at {observed_stage}: {result['failure_type']}")

            candidates.append(
                {
                    "candidate_id": cid,
                    "task_id": cid,
                    "benchmark_version": "v0.19.5",
                    "benchmark_family": family,
                    "mutation_family": family,
                    "source_model_path": str(source_path),
                    "mutated_model_path": str(mut_path),
                    "model_name": source.model_name,
                    "failure_type": result["failure_type"],
                    "expected_stage": "simulate" if observed_stage == "simulate" else "check",
                    "expected_turns": 2 if family in {"connection_topology_drop", "equation_count_extra_constraint"} else 1,
                    "admission_status": "PASS",
                    "admission_source": "omc_source_simulate_and_mutated_failure_verified",
                    "observed_initial_stage": observed_stage,
                    "observed_initial_error_excerpt": result["observed_error"][:600],
                    "difficulty_prior": _difficulty_prior(family, observed_stage),
                    "backend": "openmodelica_docker",
                    "planner_backend": "gemini",
                }
            )
            results.append({"candidate_id": cid, "status": "PASS", "observed_stage": observed_stage})

    jsonl_path = OUT_DIR / "candidates.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as handle:
        for case in candidates:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    by_family: dict[str, int] = {}
    for case in candidates:
        family = case["mutation_family"]
        by_family[family] = by_family.get(family, 0) + 1

    summary = {
        "benchmark_version": "v0.19.5",
        "total_specs": len(SOURCE_MODELS) * len(MUTATION_FAMILIES),
        "verified": len(candidates),
        "failed": len(SOURCE_MODELS) * len(MUTATION_FAMILIES) - len(candidates),
        "by_family": by_family,
        "results": results,
        "output": str(jsonl_path),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n=== Hardened v0.19.5 Summary ===")
    print(f"  verified: {summary['verified']} / {summary['total_specs']}")
    for family, count in sorted(by_family.items()):
        print(f"  {family}: {count}")
    print(f"  candidates: {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
