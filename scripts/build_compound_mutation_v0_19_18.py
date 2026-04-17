"""Build OMC-admitted compound mutation cases for v0.19.18.

Compound mutation design
------------------------
Each case applies TWO bugs simultaneously to a semantic RC source model:

  Bug 1 (structural)  — remove all ground connects
                         → OMC simulate fails with floating-node error
  Bug 2 (semantic)    — change C_store to wrong value (5× larger)
                         → behavioral oracle fails (wrong RC time constant)

Expected repair trajectory
--------------------------
  Round 1 : OMC simulate fails (floating) → LLM adds ground connects
  Round 2 : OMC simulate PASS, behavioral oracle fails (wrong tau)
             → LLM fixes capacitor value
  Round 3 : both PASS → done

This is the first family where the LLM must navigate two *different* oracle
signal types in sequence.  All previous multi-turn cases cycle within a
single oracle type.

Admission checks (five gates)
------------------------------
  1. source_model : OMC simulate PASS + oracle PASS          (already proven by v0.19.15)
  2. compound     : OMC simulate FAIL  (floating nodes)      (verified here)
  3. intermediate : OMC simulate PASS + oracle FAIL          (grounds restored, wrong C)
  4. after_fix    : oracle(source, source) = PASS            (sanity, already proven)

Base models come from the v0.19.15 semantic family artifacts; only the 3-5
most structurally diverse cases are selected.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_semantic_time_constant_oracle_v1 import (
    evaluate_semantic_time_constant_contract,
)

SEMANTIC_V0_19_15_DIR = (
    REPO_ROOT / "artifacts" / "semantic_reasoning_mutations_v0_19_15"
)
OUT_DIR = REPO_ROOT / "artifacts" / "compound_mutation_v0_19_18"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

GROUND_CONNECT_RE = re.compile(
    r"^\s*connect\s*\([^)]*\bG\.[pn]\b[^)]*\)\s*;\s*$"
)


@dataclass(frozen=True)
class CompoundSpec:
    v01915_base_id: str
    v01915_model_name: str
    compound_candidate_id: str
    compound_model_name: str
    description_suffix: str


SPECS = [
    CompoundSpec(
        v01915_base_id="v01915_semantic_rc_const_tau1_a",
        v01915_model_name="V01915SemanticRCConstTau1A",
        compound_candidate_id="v01918_compound_rc_const_tau1_a",
        compound_model_name="V01918CompoundRCConstTau1A",
        description_suffix="constant source, tau=1.0 (R=100, C=0.01→0.05)",
    ),
    CompoundSpec(
        v01915_base_id="v01915_semantic_rc_step_tau05",
        v01915_model_name="V01915SemanticRCStepTau05",
        compound_candidate_id="v01918_compound_rc_step_tau05",
        compound_model_name="V01918CompoundRCStepTau05",
        description_suffix="step source, tau=0.5 (R=50, C=0.01→0.05)",
    ),
    CompoundSpec(
        v01915_base_id="v01915_semantic_rc_const_tau02",
        v01915_model_name="V01915SemanticRCConstTau02",
        compound_candidate_id="v01918_compound_rc_const_tau02",
        compound_model_name="V01918CompoundRCConstTau02",
        description_suffix="constant source, tau=0.2 (R=20, C=0.01→0.05)",
    ),
    CompoundSpec(
        v01915_base_id="v01915_semantic_rc_const_tau1_b",
        v01915_model_name="V01915SemanticRCConstTau1B",
        compound_candidate_id="v01918_compound_rc_const_tau1_b",
        compound_model_name="V01918CompoundRCConstTau1B",
        description_suffix="constant source, tau=1.0 (R=500, C=0.002→0.01)",
    ),
    CompoundSpec(
        v01915_base_id="v01915_semantic_rc_step_tau1",
        v01915_model_name="V01915SemanticRCStepTau1",
        compound_candidate_id="v01918_compound_rc_step_tau1",
        compound_model_name="V01918CompoundRCStepTau1",
        description_suffix="step source, tau=1.0 (R=1000, C=0.001→0.01)",
    ),
]


def _get_lib_cache() -> Path:
    raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    return Path(raw) if raw else (Path.home() / ".openmodelica" / "libraries")


def _run_omc(model_text: str, model_name: str, action: str) -> tuple[bool, str]:
    if action == "simulate":
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
        (tmp_path / ".omc_home" / ".openmodelica" / "cache").mkdir(
            parents=True, exist_ok=True
        )
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
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    error_text = ""
    for line in lines:
        if line.startswith('"') and len(line) > 2:
            error_text = line.strip('"')
    passed = (
        any("resultFile" in l for l in lines)
        and "Error" not in error_text
    )
    return passed, error_text if error_text else output[:1200]


def _remove_ground_connects(text: str) -> tuple[str, list[str]]:
    lines = text.splitlines()
    new_lines, removed = [], []
    for line in lines:
        if GROUND_CONNECT_RE.match(line):
            removed.append(line.strip())
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n", removed


def _rename_model(text: str, old_name: str, new_name: str) -> str:
    return (
        text
        .replace(f"model {old_name}", f"model {new_name}")
        .replace(f"end {old_name};", f"end {new_name};")
    )


def _run_oracle(current_text: str, source_text: str) -> dict | None:
    return evaluate_semantic_time_constant_contract(
        current_text=current_text,
        source_model_text=source_text,
        failure_type="behavioral_contract_fail",
    )


def _build_candidate(spec: CompoundSpec) -> dict | None:
    source_path = SEMANTIC_V0_19_15_DIR / f"{spec.v01915_base_id}_source.mo"
    intermediate_path = SEMANTIC_V0_19_15_DIR / f"{spec.v01915_base_id}.mo"

    if not source_path.exists():
        raise RuntimeError(f"v0.19.15 source file not found: {source_path}")
    if not intermediate_path.exists():
        raise RuntimeError(f"v0.19.15 mutated file not found: {intermediate_path}")

    raw_source_text = source_path.read_text(encoding="utf-8")
    raw_intermediate_text = intermediate_path.read_text(encoding="utf-8")

    source_text = _rename_model(raw_source_text, spec.v01915_model_name, spec.compound_model_name)
    intermediate_text = _rename_model(raw_intermediate_text, spec.v01915_model_name, spec.compound_model_name)

    compound_text, removed_lines = _remove_ground_connects(intermediate_text)
    if not removed_lines:
        raise RuntimeError(f"no ground connects found in {spec.v01915_base_id}.mo")

    print(f"  Removed {len(removed_lines)} ground connect(s)")

    # Gate 1: source model must simulate
    print("  [Gate 1] source simulate...")
    src_ok, src_log = _run_omc(source_text, spec.compound_model_name, "simulate")
    if not src_ok:
        print(f"  [REJECT] source simulate FAIL: {src_log[:300]}")
        return None
    print("  [Gate 1] PASS")

    # Gate 2: compound model must fail simulate (floating nodes)
    print("  [Gate 2] compound simulate (expect FAIL)...")
    compound_ok, compound_log = _run_omc(compound_text, spec.compound_model_name, "simulate")
    if compound_ok:
        print("  [REJECT] compound model still simulates — structural mutation not detected")
        return None
    if "imbalanced" not in compound_log.lower() and "independent subset" not in compound_log.lower():
        print(f"  [WARN] compound fails but not with expected floating-node error: {compound_log[:300]}")
    print(f"  [Gate 2] PASS (simulate FAIL as expected)")

    # Gate 3: intermediate model (wrong C, correct grounds) must simulate
    print("  [Gate 3] intermediate simulate (wrong C, correct grounds)...")
    inter_ok, inter_log = _run_omc(intermediate_text, spec.compound_model_name, "simulate")
    if not inter_ok:
        print(f"  [REJECT] intermediate simulate FAIL: {inter_log[:300]}")
        return None
    print("  [Gate 3] PASS")

    # Gate 4: oracle must PASS for source
    print("  [Gate 4] oracle(source) — expect PASS...")
    src_oracle = _run_oracle(source_text, source_text)
    if src_oracle is None:
        print("  [REJECT] oracle returned None for source — oracle not applicable")
        return None
    if not bool(src_oracle.get("pass")):
        print(f"  [REJECT] source oracle FAIL: {src_oracle}")
        return None
    print("  [Gate 4] PASS")

    # Gate 5: oracle must FAIL for intermediate
    print("  [Gate 5] oracle(intermediate) — expect FAIL...")
    inter_oracle = _run_oracle(intermediate_text, source_text)
    if inter_oracle is None:
        print("  [REJECT] oracle returned None for intermediate")
        return None
    if bool(inter_oracle.get("pass")):
        print(f"  [REJECT] intermediate oracle PASS — wrong C not detected by oracle")
        return None
    print(f"  [Gate 5] PASS (oracle FAIL as expected, bucket={inter_oracle.get('contract_fail_bucket')})")

    # Write compound and source model files
    compound_path = OUT_DIR / f"{spec.compound_candidate_id}.mo"
    source_out_path = OUT_DIR / f"{spec.compound_candidate_id}_source.mo"
    compound_path.write_text(compound_text, encoding="utf-8")
    source_out_path.write_text(source_text, encoding="utf-8")

    return {
        "candidate_id": spec.compound_candidate_id,
        "task_id": spec.compound_candidate_id,
        "benchmark_family": "compound_mutation_family",
        "mutation_family": "compound_underdetermined_plus_semantic",
        "benchmark_version": "v0.19.18",
        "description": f"Compound mutation (missing_ground + wrong_capacitor): {spec.description_suffix}",
        "source_model_path": str(source_out_path),
        "mutated_model_path": str(compound_path),
        "failure_type": "behavioral_contract_fail",
        "expected_stage": "simulate",
        "expected_turns": 3,
        "difficulty_prior": "hard",
        "workflow_goal": (
            "Restore the circuit so it simulates without floating-node errors "
            "and VS1.v follows the expected RC charging response at the declared "
            "time constant. The circuit may have both structural and parameter faults."
        ),
        "requires_nonlocal_or_semantic_reasoning": True,
        "admission_status": "PASS",
        "admission_source": "omc_and_oracle_compound_verified",
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "compound_mutation_bugs": ["missing_ground_connects", "wrong_capacitor_value"],
        "removed_ground_connects": removed_lines,
        "n_removed_connects": len(removed_lines),
        "compound_simulate_excerpt": compound_log[:600],
        "semantic_oracle": {
            "kind": "simulation_based_time_constant",
            "observation_var": "VS1.v",
            "fault_injection": "wrong_capacitance_plus_missing_ground",
        },
        "base_v01915_candidate_id": spec.v01915_base_id,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    admitted, rejected = [], []

    for spec in SPECS:
        print(f"\nBuilding {spec.compound_candidate_id} ...")
        try:
            candidate = _build_candidate(spec)
        except RuntimeError as exc:
            print(f"  [ERROR] {exc}")
            rejected.append(spec.compound_candidate_id)
            continue
        if candidate:
            admitted.append(candidate)
            print(f"  [ADMIT] {spec.compound_candidate_id}")
        else:
            rejected.append(spec.compound_candidate_id)
            print(f"  [REJECT] {spec.compound_candidate_id}")

    out_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        for row in admitted:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "probe_version": "v0.19.18",
        "experiment": "compound_underdetermined_plus_semantic_mutation",
        "hypothesis": (
            "LLM must navigate two distinct oracle signal types in sequence: "
            "OMC structural error (floating nodes) in Round 1, "
            "then behavioral oracle failure (wrong time constant) in Round 2."
        ),
        "total_specs": len(SPECS),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "rejected_ids": rejected,
        "output": str(out_jsonl),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n" + json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
