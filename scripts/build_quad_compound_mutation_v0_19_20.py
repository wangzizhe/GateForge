"""Build OMC-admitted quad compound mutation cases for v0.19.20.

Quad compound mutation design
------------------------------
Each case applies FOUR bugs simultaneously to a semantic RC source model:

  Bug 1 (structural)  — remove all ground connects
                         → OMC simulate fails with floating-node error
  Bug 2 (semantic C)  — change C_store to wrong value (5× larger)
                         → behavioral oracle fails (RC tau too slow)
  Bug 3 (semantic R)  — change R_charge to wrong value (2× larger)
                         → behavioral oracle fails (RC tau still too slow)
  Bug 4 (topology)    — add parallel leak resistor R_leak = R_charge
                         across C1 (R_leak.p → R1.n, R_leak.n → C1.n)
                         → behavioral oracle fails (effective tau halved,
                           steady-state voltage halved)

Expected repair trajectory
--------------------------
  Round 1 : OMC simulate fails (floating) → LLM adds ground connects
  Round 2 : OMC PASS, oracle fails (fraction ≈ 0.26 due to R_wrong, C_wrong,
             R_leak all present; deviation huge)
             → LLM fixes C and R parameters simultaneously
  Round 3 : OMC PASS, oracle fails (fraction ≈ 0.865; tau now too short
             because R_leak still creates parallel path)
             → LLM identifies spurious R_leak component and removes it
  Round 4 : PASS

New test dimension vs v0.19.19
-------------------------------
In v0.19.19 both parameter bugs pushed fraction too LOW (tau too slow).
After fixing C and R, the oracle now shows fraction > expected (tau too FAST),
signaling a topology problem rather than a parameter problem.
The LLM must switch reasoning mode from parameter adjustment to component removal.

Eight-gate admission
--------------------
  1. source           : OMC simulate PASS + oracle PASS
  2. compound         : OMC simulate FAIL  (no grounds → floating nodes)
  3. intermediate_1   : OMC simulate PASS  (R wrong, C wrong, R_leak, grounds)
  4. intermediate_2   : OMC simulate PASS  (R wrong, C correct, R_leak, grounds)
  5. intermediate_3   : OMC simulate PASS  (R correct, C correct, R_leak, grounds)
  6. oracle(source, source)          → PASS
  7. oracle(intermediate_1, source)  → FAIL
  8. oracle(intermediate_3, source)  → FAIL  (proves R_leak alone is detectable)

Gate 8 is the key new admission check: if inter3 oracle PASS the 4th-layer bug
would be undetectable and the spec must be rejected.
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
OUT_DIR = REPO_ROOT / "artifacts" / "quad_compound_mutation_v0_19_20"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

GROUND_CONNECT_RE = re.compile(
    r"^\s*connect\s*\([^)]*\bG\.[pn]\b[^)]*\)\s*;\s*$"
)
PARAM_RE = re.compile(
    r"(parameter\s+Real\s+{name}\s*=\s*)([\d.eE+\-]+)(;)"
)


@dataclass(frozen=True)
class QuadSpec:
    v01915_base_id: str
    v01915_model_name: str
    compound_candidate_id: str
    compound_model_name: str
    wrong_resistance_factor: float
    description_suffix: str


SPECS = [
    QuadSpec(
        v01915_base_id="v01915_semantic_rc_const_tau1_a",
        v01915_model_name="V01915SemanticRCConstTau1A",
        compound_candidate_id="v01920_quad_rc_const_tau1_a",
        compound_model_name="V01920QuadRCConstTau1A",
        wrong_resistance_factor=2.0,
        description_suffix="constant source, tau=1.0 (R=100→200, C=0.01→0.05, R_leak=100)",
    ),
    QuadSpec(
        v01915_base_id="v01915_semantic_rc_step_tau05",
        v01915_model_name="V01915SemanticRCStepTau05",
        compound_candidate_id="v01920_quad_rc_step_tau05",
        compound_model_name="V01920QuadRCStepTau05",
        wrong_resistance_factor=2.0,
        description_suffix="step source, tau=0.5 (R=50→100, C=0.01→0.05, R_leak=50)",
    ),
    QuadSpec(
        v01915_base_id="v01915_semantic_rc_const_tau02",
        v01915_model_name="V01915SemanticRCConstTau02",
        compound_candidate_id="v01920_quad_rc_const_tau02",
        compound_model_name="V01920QuadRCConstTau02",
        wrong_resistance_factor=2.0,
        description_suffix="constant source, tau=0.2 (R=20→40, C=0.01→0.05, R_leak=20)",
    ),
    QuadSpec(
        v01915_base_id="v01915_semantic_rc_const_tau1_b",
        v01915_model_name="V01915SemanticRCConstTau1B",
        compound_candidate_id="v01920_quad_rc_const_tau1_b",
        compound_model_name="V01920QuadRCConstTau1B",
        wrong_resistance_factor=2.0,
        description_suffix="constant source, tau=1.0 (R=500→1000, C=0.002→0.01, R_leak=500)",
    ),
    QuadSpec(
        v01915_base_id="v01915_semantic_rc_step_tau1",
        v01915_model_name="V01915SemanticRCStepTau1",
        compound_candidate_id="v01920_quad_rc_step_tau1",
        compound_model_name="V01920QuadRCStepTau1",
        wrong_resistance_factor=2.0,
        description_suffix="step source, tau=1.0 (R=1000→2000, C=0.001→0.01, R_leak=1000)",
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


def _substitute_param(text: str, param_name: str, new_value: float) -> tuple[str, float]:
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


def _inject_parallel_resistor(text: str, r_leak_val: float) -> tuple[str, bool]:
    """Insert R_leak (parameter + component + 2 connects) in parallel with C1.

    R_leak.p connects to R1.n (= C1.p junction).
    R_leak.n connects to C1.n (= ground junction).
    This places R_leak in parallel with C1, creating a voltage divider.
    """
    # Insert parameter declaration and component before the 'equation' keyword.
    new_text = re.sub(
        r'\bequation\b',
        (
            f"  parameter Real R_leak_val = {r_leak_val};\n"
            f"  Modelica.Electrical.Analog.Basic.Resistor R_leak(R=R_leak_val);\n"
            "equation"
        ),
        text, count=1,
    )
    if new_text == text:
        return text, False
    # Insert two connect statements before the annotation line.
    new_text = re.sub(
        r"([ \t]*annotation\s*\()",
        r"  connect(R_leak.p, R1.n);\n  connect(R_leak.n, C1.n);\n\1",
        new_text, count=1,
    )
    return new_text, True


def _run_oracle(current_text: str, source_text: str) -> dict | None:
    return evaluate_semantic_time_constant_contract(
        current_text=current_text,
        source_model_text=source_text,
        failure_type="behavioral_contract_fail",
    )


def _build_candidate(spec: QuadSpec) -> dict | None:
    source_path = SEMANTIC_V0_19_15_DIR / f"{spec.v01915_base_id}_source.mo"
    mutated_path = SEMANTIC_V0_19_15_DIR / f"{spec.v01915_base_id}.mo"

    if not source_path.exists():
        raise RuntimeError(f"v0.19.15 source file not found: {source_path}")
    if not mutated_path.exists():
        raise RuntimeError(f"v0.19.15 mutated file not found: {mutated_path}")

    raw_source_text = source_path.read_text(encoding="utf-8")
    raw_mutated_text = mutated_path.read_text(encoding="utf-8")  # has C_wrong, correct R

    # Rename all models to v01920 names
    source_text = _rename_model(raw_source_text, spec.v01915_model_name, spec.compound_model_name)
    c_wrong_base = _rename_model(raw_mutated_text, spec.v01915_model_name, spec.compound_model_name)

    # Extract parameter values
    r_correct = _extract_param(source_text, "R_charge")
    c_correct = _extract_param(source_text, "C_store")
    c_wrong = _extract_param(c_wrong_base, "C_store")
    r_wrong = round(r_correct * spec.wrong_resistance_factor, 6)
    r_leak_val = r_correct  # R_leak = R_charge for maximum oracle signal
    expected_tau = r_correct * c_correct

    # Effective tau with both R_wrong and R_leak present: (R_wrong || R_leak) × C_wrong
    r_parallel = (r_wrong * r_leak_val) / (r_wrong + r_leak_val)  # R_wrong || R_leak
    tau_compound = round(r_parallel * c_wrong, 6)
    # After fixing R and C but R_leak still present: (R_correct || R_leak) × C_correct
    r_parallel_inter3 = (r_correct * r_leak_val) / (r_correct + r_leak_val)
    tau_inter3 = round(r_parallel_inter3 * c_correct, 6)

    print(f"  R_correct={r_correct}, R_wrong={r_wrong}, R_leak={r_leak_val}")
    print(f"  C_correct={c_correct}, C_wrong={c_wrong}")
    print(f"  expected_tau={expected_tau:.4f}")
    print(f"  tau_compound (all bugs)={tau_compound:.4f} (×{tau_compound/expected_tau:.2f})")
    print(f"  tau_inter3 (R_leak only)={tau_inter3:.4f} (×{tau_inter3/expected_tau:.2f})")

    # --- Build all intermediate model texts ---

    # intermediate_1: R wrong, C wrong, R_leak injected, grounds present
    inter1_rc_wrong, _ = _substitute_param(c_wrong_base, "R_charge", r_wrong)
    inter1_text, ok1 = _inject_parallel_resistor(inter1_rc_wrong, r_leak_val)
    if not ok1:
        raise RuntimeError("_inject_parallel_resistor failed for intermediate_1")

    # intermediate_2: R wrong, C correct, R_leak injected, grounds present
    inter2_r_wrong, _ = _substitute_param(source_text, "R_charge", r_wrong)
    inter2_text, ok2 = _inject_parallel_resistor(inter2_r_wrong, r_leak_val)
    if not ok2:
        raise RuntimeError("_inject_parallel_resistor failed for intermediate_2")

    # intermediate_3: R correct, C correct, R_leak injected, grounds present
    inter3_text, ok3 = _inject_parallel_resistor(source_text, r_leak_val)
    if not ok3:
        raise RuntimeError("_inject_parallel_resistor failed for intermediate_3")

    # compound: inter1 with grounds removed
    compound_text, removed_lines = _remove_ground_connects(inter1_text)
    if not removed_lines:
        raise RuntimeError(f"no ground connects found in {spec.v01915_base_id}.mo")
    print(f"  Removed {len(removed_lines)} ground connect(s)")

    # ===== Eight-gate admission =====

    # Gate 1: source must simulate
    print("  [Gate 1] source simulate...")
    src_ok, src_log = _run_omc(source_text, spec.compound_model_name)
    if not src_ok:
        print(f"  [REJECT] source simulate FAIL: {src_log[:200]}")
        return None
    print("  [Gate 1] PASS")

    # Gate 2: compound must fail simulate (floating nodes)
    print("  [Gate 2] compound simulate (expect FAIL)...")
    comp_ok, comp_log = _run_omc(compound_text, spec.compound_model_name)
    if comp_ok:
        print("  [REJECT] compound model still simulates — structural mutation not detected")
        return None
    print(f"  [Gate 2] PASS (simulate FAIL as expected)")

    # Gate 3: intermediate_1 (R wrong, C wrong, R_leak, grounds) must simulate
    print("  [Gate 3] intermediate_1 simulate (R wrong, C wrong, R_leak)...")
    inter1_ok, inter1_log = _run_omc(inter1_text, spec.compound_model_name)
    if not inter1_ok:
        print(f"  [REJECT] intermediate_1 simulate FAIL: {inter1_log[:200]}")
        return None
    print("  [Gate 3] PASS")

    # Gate 4: intermediate_2 (R wrong, C correct, R_leak, grounds) must simulate
    print("  [Gate 4] intermediate_2 simulate (R wrong, C correct, R_leak)...")
    inter2_ok, inter2_log = _run_omc(inter2_text, spec.compound_model_name)
    if not inter2_ok:
        print(f"  [REJECT] intermediate_2 simulate FAIL: {inter2_log[:200]}")
        return None
    print("  [Gate 4] PASS")

    # Gate 5: intermediate_3 (R correct, C correct, R_leak, grounds) must simulate
    print("  [Gate 5] intermediate_3 simulate (R correct, C correct, R_leak)...")
    inter3_ok, inter3_log = _run_omc(inter3_text, spec.compound_model_name)
    if not inter3_ok:
        print(f"  [REJECT] intermediate_3 simulate FAIL: {inter3_log[:200]}")
        return None
    print("  [Gate 5] PASS")

    # Gate 6: oracle must PASS for source
    print("  [Gate 6] oracle(source) — expect PASS...")
    src_oracle = _run_oracle(source_text, source_text)
    if src_oracle is None or not bool(src_oracle.get("pass")):
        print(f"  [REJECT] source oracle FAIL: {src_oracle}")
        return None
    print("  [Gate 6] PASS")

    # Gate 7: oracle must FAIL for intermediate_1
    print("  [Gate 7] oracle(intermediate_1) — expect FAIL...")
    inter1_oracle = _run_oracle(inter1_text, source_text)
    if inter1_oracle is None or bool(inter1_oracle.get("pass")):
        print(f"  [REJECT] intermediate_1 oracle PASS unexpectedly")
        return None
    sr1 = (inter1_oracle.get("scenario_results") or [{}])[0]
    print(f"  [Gate 7] PASS (deviation={sr1.get('deviation_from_source', '?'):.4f})")

    # Gate 8: oracle must FAIL for intermediate_3 (R_leak alone detectable)
    print("  [Gate 8] oracle(intermediate_3, R_leak only) — expect FAIL...")
    inter3_oracle = _run_oracle(inter3_text, source_text)
    if inter3_oracle is None or bool(inter3_oracle.get("pass")):
        print(f"  [REJECT] intermediate_3 oracle PASS — R_leak not detectable; spec rejected")
        return None
    sr3 = (inter3_oracle.get("scenario_results") or [{}])[0]
    inter3_deviation = sr3.get("deviation_from_source", 0.0)
    print(f"  [Gate 8] PASS (deviation={inter3_deviation:.4f}, min_required=0.12)")

    # Write model files
    compound_path = OUT_DIR / f"{spec.compound_candidate_id}.mo"
    source_out_path = OUT_DIR / f"{spec.compound_candidate_id}_source.mo"
    inter3_path = OUT_DIR / f"{spec.compound_candidate_id}_inter3.mo"
    compound_path.write_text(compound_text, encoding="utf-8")
    source_out_path.write_text(source_text, encoding="utf-8")
    inter3_path.write_text(inter3_text, encoding="utf-8")

    return {
        "candidate_id": spec.compound_candidate_id,
        "task_id": spec.compound_candidate_id,
        "benchmark_family": "quad_compound_mutation_family",
        "mutation_family": "quad_structural_plus_two_semantic_plus_topology",
        "benchmark_version": "v0.19.20",
        "description": (
            f"Quad compound mutation (missing_ground + wrong_C + wrong_R + R_leak_parallel): "
            f"{spec.description_suffix}"
        ),
        "source_model_path": str(source_out_path),
        "mutated_model_path": str(compound_path),
        "failure_type": "behavioral_contract_fail",
        "expected_stage": "simulate",
        "expected_turns": 4,
        "difficulty_prior": "very_hard",
        "workflow_goal": (
            "Restore the circuit so it simulates without floating-node errors "
            "and VS1.v follows the expected RC charging response at the declared "
            "time constant. The circuit may have structural faults, parameter "
            "faults, and/or spurious components."
        ),
        "requires_nonlocal_or_semantic_reasoning": True,
        "admission_status": "PASS",
        "admission_source": "omc_and_oracle_quad_compound_verified",
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "compound_mutation_bugs": [
            "missing_ground_connects",
            "wrong_capacitor_value",
            "wrong_resistance_value",
            "parallel_leak_resistor",
        ],
        "removed_ground_connects": removed_lines,
        "n_removed_connects": len(removed_lines),
        "compound_simulate_excerpt": comp_log[:600],
        "semantic_oracle": {
            "kind": "simulation_based_time_constant",
            "observation_var": "VS1.v",
            "fault_injection": "wrong_C_plus_wrong_R_plus_R_leak_plus_missing_ground",
        },
        "parameter_mutations": {
            "R_charge": {
                "correct": r_correct,
                "wrong": r_wrong,
                "factor": spec.wrong_resistance_factor,
            },
            "C_store": {
                "correct": c_correct,
                "wrong": c_wrong,
                "factor": round(c_wrong / c_correct, 2),
            },
            "R_leak": {
                "injected_value": r_leak_val,
                "relative_to_R_charge": 1.0,
                "effect": "parallel path across C1 halves effective tau and steady-state voltage",
            },
            "expected_tau_correct": expected_tau,
            "tau_compound": tau_compound,
            "tau_inter3": tau_inter3,
            "inter3_deviation_from_source": inter3_deviation,
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
        "probe_version": "v0.19.20",
        "experiment": "quad_structural_plus_two_semantic_plus_topology_mutation",
        "hypothesis": (
            "After fixing the structural bug (Round 1) and semantic bugs (Round 2), "
            "the oracle shows fraction > expected (tau too fast), signaling a topology "
            "fault. LLM must switch from parameter adjustment to component removal "
            "(identify and remove spurious R_leak parallel resistor)."
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
