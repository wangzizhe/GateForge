"""Build OMC-admitted triple compound mutation cases for v0.19.19.

Triple compound mutation design
--------------------------------
Each case applies THREE bugs simultaneously to a semantic RC source model:

  Bug 1 (structural)   — remove all ground connects
                          → OMC simulate fails with floating-node error
  Bug 2 (semantic C)   — change C_store to wrong value (5× larger)
                          → behavioral oracle fails (RC tau too slow)
  Bug 3 (semantic R)   — change R_charge to wrong value (2× larger)
                          → behavioral oracle fails (RC tau too slow, different magnitude)

Expected repair trajectory
--------------------------
  Round 1 : OMC simulate fails (floating) → LLM adds ground connects
  Round 2 : OMC PASS, oracle fails (tau = R×2 × C×5 = 10× wrong)
             → LLM fixes one or both semantic bugs
  Round 3 : OMC PASS, oracle fails if only C was fixed (tau = R×2 × C_correct = 2× wrong)
             → LLM fixes remaining R bug
  Round 4 : PASS    (or 3 if LLM fixed both C and R in one step)

New test dimension vs v0.19.18
-------------------------------
After fixing the structural bug, the LLM must reason about two simultaneous
semantic faults affecting the same observable (tau).  If it fixes only C, it
must infer from a SECOND behavioral oracle failure that R is also wrong.
This is "multi-step semantic reasoning within a single oracle type".

Six-gate admission
------------------
  1. source          : OMC simulate PASS + oracle PASS
  2. compound        : OMC simulate FAIL  (no grounds)
  3. intermediate_1  : OMC simulate PASS + oracle FAIL  (R wrong, C wrong, grounds)
  4. intermediate_2  : OMC simulate PASS + oracle FAIL  (R wrong, C correct, grounds)
  5. oracle(source, source)          → PASS
  6. oracle(intermediate_2, source)  → FAIL

Gates 1, 5 already proven by v0.19.15.  Gates 2, 3 proven by v0.19.18.
Gate 4 (intermediate_2) and Gate 6 are the new checks.
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
OUT_DIR = REPO_ROOT / "artifacts" / "triple_compound_mutation_v0_19_19"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

GROUND_CONNECT_RE = re.compile(
    r"^\s*connect\s*\([^)]*\bG\.[pn]\b[^)]*\)\s*;\s*$"
)
PARAM_RE = re.compile(
    r"(parameter\s+Real\s+{name}\s*=\s*)([\d.eE+\-]+)(;)"
)


@dataclass(frozen=True)
class TripleSpec:
    v01915_base_id: str
    v01915_model_name: str
    compound_candidate_id: str
    compound_model_name: str
    wrong_resistance_factor: float
    description_suffix: str


SPECS = [
    TripleSpec(
        v01915_base_id="v01915_semantic_rc_const_tau1_a",
        v01915_model_name="V01915SemanticRCConstTau1A",
        compound_candidate_id="v01919_triple_rc_const_tau1_a",
        compound_model_name="V01919TripleRCConstTau1A",
        wrong_resistance_factor=2.0,
        description_suffix="constant source, tau=1.0 (R=100→200, C=0.01→0.05)",
    ),
    TripleSpec(
        v01915_base_id="v01915_semantic_rc_step_tau05",
        v01915_model_name="V01915SemanticRCStepTau05",
        compound_candidate_id="v01919_triple_rc_step_tau05",
        compound_model_name="V01919TripleRCStepTau05",
        wrong_resistance_factor=2.0,
        description_suffix="step source, tau=0.5 (R=50→100, C=0.01→0.05)",
    ),
    TripleSpec(
        v01915_base_id="v01915_semantic_rc_const_tau02",
        v01915_model_name="V01915SemanticRCConstTau02",
        compound_candidate_id="v01919_triple_rc_const_tau02",
        compound_model_name="V01919TripleRCConstTau02",
        wrong_resistance_factor=2.0,
        description_suffix="constant source, tau=0.2 (R=20→40, C=0.01→0.05)",
    ),
    TripleSpec(
        v01915_base_id="v01915_semantic_rc_const_tau1_b",
        v01915_model_name="V01915SemanticRCConstTau1B",
        compound_candidate_id="v01919_triple_rc_const_tau1_b",
        compound_model_name="V01919TripleRCConstTau1B",
        wrong_resistance_factor=2.0,
        description_suffix="constant source, tau=1.0 (R=500→1000, C=0.002→0.01)",
    ),
    TripleSpec(
        v01915_base_id="v01915_semantic_rc_step_tau1",
        v01915_model_name="V01915SemanticRCStepTau1",
        compound_candidate_id="v01919_triple_rc_step_tau1",
        compound_model_name="V01919TripleRCStepTau1",
        wrong_resistance_factor=2.0,
        description_suffix="step source, tau=1.0 (R=1000→2000, C=0.001→0.01)",
    ),
]


def _get_lib_cache() -> Path:
    raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    return Path(raw) if raw else (Path.home() / ".openmodelica" / "libraries")


def _run_omc(model_text: str, model_name: str) -> tuple[bool, str]:
    command = (
        f"simulate({model_name}, startTime=0.0, stopTime=0.05, "
        "numberOfIntervals=20, tolerance=1e-06);\n"
    )
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
            timeout=180,
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


def _substitute_param(text: str, param_name: str, new_value: float) -> str:
    pat = PARAM_RE.pattern.replace("{name}", param_name)
    m = re.search(pat, text)
    if not m:
        raise ValueError(f"parameter '{param_name}' not found in model text")
    old_val = float(m.group(2))
    replacement = f"{m.group(1)}{new_value}{m.group(3)}"
    return re.sub(pat, replacement, text, count=1), old_val


def _extract_param(text: str, param_name: str) -> float:
    pat = PARAM_RE.pattern.replace("{name}", param_name)
    m = re.search(pat, text)
    if not m:
        raise ValueError(f"parameter '{param_name}' not found")
    return float(m.group(2))


def _run_oracle(current_text: str, source_text: str) -> dict | None:
    return evaluate_semantic_time_constant_contract(
        current_text=current_text,
        source_model_text=source_text,
        failure_type="behavioral_contract_fail",
    )


def _build_candidate(spec: TripleSpec) -> dict | None:
    source_path = SEMANTIC_V0_19_15_DIR / f"{spec.v01915_base_id}_source.mo"
    intermediate_path = SEMANTIC_V0_19_15_DIR / f"{spec.v01915_base_id}.mo"

    if not source_path.exists():
        raise RuntimeError(f"v0.19.15 source file not found: {source_path}")
    if not intermediate_path.exists():
        raise RuntimeError(f"v0.19.15 mutated file not found: {intermediate_path}")

    raw_source_text = source_path.read_text(encoding="utf-8")
    raw_intermediate_text = intermediate_path.read_text(encoding="utf-8")  # C wrong, R correct

    # Rename models to v01919 names
    source_text = _rename_model(raw_source_text, spec.v01915_model_name, spec.compound_model_name)
    inter_c_wrong_text = _rename_model(raw_intermediate_text, spec.v01915_model_name, spec.compound_model_name)

    # Extract parameter values
    r_correct = _extract_param(source_text, "R_charge")
    c_correct = _extract_param(source_text, "C_store")
    c_wrong = _extract_param(inter_c_wrong_text, "C_store")
    r_wrong = round(r_correct * spec.wrong_resistance_factor, 6)
    expected_tau = r_correct * c_correct

    print(f"  R_correct={r_correct}, R_wrong={r_wrong}, C_correct={c_correct}, C_wrong={c_wrong}")
    print(f"  expected_tau={expected_tau:.4f}, tau_compound={r_wrong*c_wrong:.4f} (×{r_wrong*c_wrong/expected_tau:.1f})")
    print(f"  tau_inter2={r_wrong*c_correct:.4f} (×{r_wrong*c_correct/expected_tau:.1f})")

    # Build intermediate_1: R wrong, C wrong, grounds present
    inter1_text, _ = _substitute_param(inter_c_wrong_text, "R_charge", r_wrong)

    # Build intermediate_2: R wrong, C correct, grounds present
    inter2_text, _ = _substitute_param(source_text, "R_charge", r_wrong)

    # Build compound: R wrong, C wrong, no grounds
    compound_no_ground, removed_lines = _remove_ground_connects(inter1_text)
    if not removed_lines:
        raise RuntimeError(f"no ground connects found in {spec.v01915_base_id}.mo")
    print(f"  Removed {len(removed_lines)} ground connect(s)")

    # Gate 1: source must simulate
    print("  [Gate 1] source simulate...")
    src_ok, src_log = _run_omc(source_text, spec.compound_model_name)
    if not src_ok:
        print(f"  [REJECT] source simulate FAIL")
        return None
    print("  [Gate 1] PASS")

    # Gate 2: compound must fail simulate (floating)
    print("  [Gate 2] compound simulate (expect FAIL)...")
    compound_ok, compound_log = _run_omc(compound_no_ground, spec.compound_model_name)
    if compound_ok:
        print("  [REJECT] compound still simulates")
        return None
    print("  [Gate 2] PASS (simulate FAIL as expected)")

    # Gate 3: intermediate_1 (R wrong, C wrong, grounds) must simulate
    print("  [Gate 3] intermediate_1 simulate (R wrong, C wrong)...")
    inter1_ok, inter1_log = _run_omc(inter1_text, spec.compound_model_name)
    if not inter1_ok:
        print(f"  [REJECT] intermediate_1 simulate FAIL")
        return None
    print("  [Gate 3] PASS")

    # Gate 4: intermediate_2 (R wrong, C correct, grounds) must simulate
    print("  [Gate 4] intermediate_2 simulate (R wrong, C correct)...")
    inter2_ok, inter2_log = _run_omc(inter2_text, spec.compound_model_name)
    if not inter2_ok:
        print(f"  [REJECT] intermediate_2 simulate FAIL")
        return None
    print("  [Gate 4] PASS")

    # Gate 5: oracle must PASS for source
    print("  [Gate 5] oracle(source) — expect PASS...")
    src_oracle = _run_oracle(source_text, source_text)
    if src_oracle is None or not bool(src_oracle.get("pass")):
        print(f"  [REJECT] source oracle FAIL")
        return None
    print("  [Gate 5] PASS")

    # Gate 6: oracle must FAIL for intermediate_1
    print("  [Gate 6a] oracle(intermediate_1) — expect FAIL...")
    inter1_oracle = _run_oracle(inter1_text, source_text)
    if inter1_oracle is None or bool(inter1_oracle.get("pass")):
        print(f"  [REJECT] intermediate_1 oracle PASS unexpectedly")
        return None
    print(f"  [Gate 6a] PASS (bucket={inter1_oracle.get('contract_fail_bucket')})")

    # Gate 7: oracle must FAIL for intermediate_2 (R wrong, C correct)
    print("  [Gate 7] oracle(intermediate_2, R wrong C correct) — expect FAIL...")
    inter2_oracle = _run_oracle(inter2_text, source_text)
    if inter2_oracle is None or bool(inter2_oracle.get("pass")):
        print(f"  [REJECT] intermediate_2 oracle PASS — R wrong not detectable by oracle")
        return None
    sr = (inter2_oracle.get("scenario_results") or [{}])[0]
    print(f"  [Gate 7] PASS (deviation={sr.get('deviation_from_source', '?'):.4f})")

    # Write model files
    compound_path = OUT_DIR / f"{spec.compound_candidate_id}.mo"
    source_out_path = OUT_DIR / f"{spec.compound_candidate_id}_source.mo"
    inter2_path = OUT_DIR / f"{spec.compound_candidate_id}_inter2.mo"
    compound_path.write_text(compound_no_ground, encoding="utf-8")
    source_out_path.write_text(source_text, encoding="utf-8")
    inter2_path.write_text(inter2_text, encoding="utf-8")

    return {
        "candidate_id": spec.compound_candidate_id,
        "task_id": spec.compound_candidate_id,
        "benchmark_family": "triple_compound_mutation_family",
        "mutation_family": "triple_underdetermined_plus_two_semantic",
        "benchmark_version": "v0.19.19",
        "description": f"Triple compound mutation (missing_ground + wrong_C + wrong_R): {spec.description_suffix}",
        "source_model_path": str(source_out_path),
        "mutated_model_path": str(compound_path),
        "failure_type": "behavioral_contract_fail",
        "expected_stage": "simulate",
        "expected_turns": 4,
        "difficulty_prior": "very_hard",
        "workflow_goal": (
            "Restore the circuit so it simulates without floating-node errors "
            "and VS1.v follows the expected RC charging response at the declared "
            "time constant. The circuit may have structural and/or multiple parameter faults."
        ),
        "requires_nonlocal_or_semantic_reasoning": True,
        "admission_status": "PASS",
        "admission_source": "omc_and_oracle_triple_compound_verified",
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "compound_mutation_bugs": [
            "missing_ground_connects",
            "wrong_capacitor_value",
            "wrong_resistance_value",
        ],
        "removed_ground_connects": removed_lines,
        "n_removed_connects": len(removed_lines),
        "compound_simulate_excerpt": compound_log[:600],
        "semantic_oracle": {
            "kind": "simulation_based_time_constant",
            "observation_var": "VS1.v",
            "fault_injection": "wrong_capacitance_plus_wrong_resistance_plus_missing_ground",
        },
        "parameter_mutations": {
            "R_charge": {"correct": r_correct, "wrong": r_wrong, "factor": spec.wrong_resistance_factor},
            "C_store": {"correct": c_correct, "wrong": c_wrong, "factor": round(c_wrong / c_correct, 2)},
            "expected_tau_correct": expected_tau,
            "tau_compound": round(r_wrong * c_wrong, 6),
            "tau_inter2": round(r_wrong * c_correct, 6),
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
        except (RuntimeError, ValueError) as exc:
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
        "probe_version": "v0.19.19",
        "experiment": "triple_compound_underdetermined_plus_two_semantic",
        "hypothesis": (
            "After fixing the structural bug, LLM must reason about two simultaneous "
            "semantic faults affecting the same observable (RC tau). "
            "If LLM fixes only C, it must infer from a second oracle failure "
            "that R is also wrong and needs correction."
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
