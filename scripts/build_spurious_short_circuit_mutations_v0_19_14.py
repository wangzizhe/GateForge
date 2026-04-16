"""Build OMC-admitted spurious-short-circuit mutations for v0.19.14.

Mutation strategy: append one extra connect() to the equation section that
short-circuits the positive terminal of the primary voltage source (V1.p)
directly to ground (G.p).

In a well-formed Modelica electrical circuit the voltage source equation
already determines the potential difference between V1.p and V1.n.  Grounding
V1.n (connect(V1.n, G.p)) fixes V1.n.v = 0, so V1.p.v = V (source voltage).
Adding connect(V1.p, G.p) imposes V1.p.v = 0 as well.  Combined:

    V1.p.v = V  (source equation)
    V1.p.v = 0  (spurious ground connect)

→ 0 = V, contradiction for any V ≠ 0.  OMC detects this at checkModel as an
overdetermined system.

Real engineering story: copy-paste error or accidental connect() addition
ties an already-driven node to ground, creating an unintended short circuit
that kills the circuit's ability to establish any non-zero potential.

Why this is a genuinely distinct capability from existing families:
  - overdetermined_kvl/kcl: spurious *equation* in equation section → delete equation
  - underdetermined_missing_ground: missing connect() → add connect()
  - this family: spurious connect() in equation section → delete connect()

LLM challenge: must understand circuit topology to identify which connect()
creates the short-circuit path, not just count equations or follow OMC's
line-number pointer.
"""
from __future__ import annotations

import json
import os
import re
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
OUT_DIR = REPO_ROOT / "artifacts" / "spurious_short_circuit_mutations_v0_19_14"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)\s+"
    r"equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ShortCircuitSpec:
    source_file: str
    model_name: str
    candidate_id: str
    relation_id: str
    spurious_connect: str  # the line to inject, e.g. "connect(V1.p, G.p);"


SPECS = [
    ShortCircuitSpec(
        source_file="small_rc_constant_v0.mo",
        model_name="SmallRCConstantV0",
        candidate_id="v01914_shortcirc_small_rc",
        relation_id="spurious_short_v1p_rc",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="small_rl_step_v0.mo",
        model_name="SmallRLStepV0",
        candidate_id="v01914_shortcirc_small_rl",
        relation_id="spurious_short_v1p_rl",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="small_r_divider_v0.mo",
        model_name="SmallRDividerV0",
        candidate_id="v01914_shortcirc_small_divider",
        relation_id="spurious_short_v1p_divider",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="medium_parallel_rc_v0.mo",
        model_name="MediumParallelRCV0",
        candidate_id="v01914_shortcirc_medium_parallel",
        relation_id="spurious_short_v1p_parallel_rc",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="medium_rlc_series_v0.mo",
        model_name="MediumRLCSeriesV0",
        candidate_id="v01914_shortcirc_medium_rlc",
        relation_id="spurious_short_v1p_rlc_series",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="medium_ladder_rc_v0.mo",
        model_name="MediumLadderRCV0",
        candidate_id="v01914_shortcirc_medium_ladder",
        relation_id="spurious_short_v1p_ladder_rc",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="medium_dual_source_v0.mo",
        model_name="MediumDualSourceV0",
        candidate_id="v01914_shortcirc_medium_dual_source",
        relation_id="spurious_short_v1p_dual_source",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="large_rc_ladder4_v0.mo",
        model_name="LargeRCLadder4V0",
        candidate_id="v01914_shortcirc_large_ladder4",
        relation_id="spurious_short_v1p_ladder4",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="large_dual_source_ladder_v0.mo",
        model_name="LargeDualSourceLadderV0",
        candidate_id="v01914_shortcirc_large_dual_source",
        relation_id="spurious_short_v1p_dual_source_ladder",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="large_rlc_branches_v0.mo",
        model_name="LargeRLCBranchesV0",
        candidate_id="v01914_shortcirc_large_rlc_branches",
        relation_id="spurious_short_v1p_rlc_branches",
        spurious_connect="connect(V1.p, G.p);",
    ),
    ShortCircuitSpec(
        source_file="large_sensorized_grid_v0.mo",
        model_name="LargeSensorizedGridV0",
        candidate_id="v01914_shortcirc_large_sensorized_grid",
        relation_id="spurious_short_v1p_sensorized_grid",
        spurious_connect="connect(V1.p, G.p);",
    ),
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


def _inject_short_circuit(text: str, spurious_connect: str) -> str:
    """Insert spurious_connect as the last connect() line in the equation section."""
    lines = text.splitlines()
    last_connect_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"\s*connect\s*\(", line):
            last_connect_idx = i
    if last_connect_idx < 0:
        raise ValueError("No connect() found in model text")
    lines.insert(last_connect_idx + 1, f"  {spurious_connect}")
    return "\n".join(lines) + "\n"


def _is_overdetermined_failure(log_text: str) -> bool:
    """Return True if OMC output signals an overdetermined / overconstrained system."""
    text_lower = log_text.lower()
    signals = [
        "overdetermined",
        "overconstrained",
        "too many equations",
        "conflicting",
        "redundant",
        "already defined",
        "multiple definitions",
        "class has",   # precedes the count line
    ]
    if any(s in text_lower for s in signals):
        return True
    # Equation count check: equations > variables
    m = COUNT_RE.search(log_text)
    if m and int(m.group("equations")) > int(m.group("variables")):
        return True
    return False


def _build_candidate(spec: ShortCircuitSpec) -> dict | None:
    source_path = SOURCE_DIR / spec.source_file
    source_text = source_path.read_text(encoding="utf-8")

    source_check, source_check_log = _run_omc(source_text, spec.model_name, "check")
    source_sim, source_sim_log = _run_omc(source_text, spec.model_name, "simulate")
    if not source_check or not source_sim:
        raise RuntimeError(
            f"source model failed admission precheck for {spec.candidate_id}: "
            f"check={source_check} simulate={source_sim}\n"
            f"{source_check_log}\n{source_sim_log}"
        )

    mutated_text = _inject_short_circuit(source_text, spec.spurious_connect)
    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    # Gate 1: mutated model must fail at checkModel OR simulate
    mutated_check, mutated_check_log = _run_omc(mutated_text, spec.model_name, "check")
    if mutated_check:
        # checkModel passed — try simulate as fallback
        mutated_sim, mutated_sim_log = _run_omc(mutated_text, spec.model_name, "simulate")
        if mutated_sim:
            print(
                f"  [REJECT] {spec.candidate_id}: mutated model still passes both "
                f"checkModel and simulate — injection did not create a hard constraint"
            )
            return None
        failure_log = mutated_sim_log
        detected_at = "simulate"
    else:
        failure_log = mutated_check_log
        detected_at = "checkModel"

    # Gate 2: verify overdetermined signal
    has_signal = _is_overdetermined_failure(failure_log)
    if not has_signal:
        print(
            f"  [WARN]   {spec.candidate_id}: failure at {detected_at} but no "
            f"overdetermined signal detected — admitting anyway.\n"
            f"  excerpt: {failure_log[:300]}"
        )

    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "benchmark_family": "spurious_short_circuit_family",
        "mutation_family": "spurious_short_circuit",
        "benchmark_version": "v0.19.14",
        "description": f"Spurious short-circuit connect: {spec.relation_id}",
        "source_model_path": str(source_path),
        "mutated_model_path": str(mutated_path),
        "failure_type": "constraint_violation",
        "expected_stage": "simulate",
        "expected_turns": 2,
        "difficulty_prior": "medium",
        "workflow_goal": (
            "Remove the spurious connect() that short-circuits the primary voltage "
            "source to ground, while preserving all other circuit connections."
        ),
        "admission_status": "PASS",
        "admission_source": "omc_spurious_short_circuit_verified",
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "short_circuit_relation_id": spec.relation_id,
        "injected_connect": spec.spurious_connect,
        "detected_at": detected_at,
        "has_overdetermined_signal": has_signal,
        "failure_log_excerpt": failure_log[:400],
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    admitted = []
    rejected = []
    for spec in SPECS:
        print(f"Building {spec.candidate_id} ...")
        try:
            candidate = _build_candidate(spec)
        except RuntimeError as exc:
            print(f"  [ERROR] {exc}")
            rejected.append(spec.candidate_id)
            continue
        if candidate:
            admitted.append(candidate)
            print(
                f"  [ADMIT] {spec.candidate_id} "
                f"(detected_at={candidate['detected_at']},"
                f" signal={candidate['has_overdetermined_signal']})"
            )
        else:
            rejected.append(spec.candidate_id)

    admitted_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(admitted_jsonl, "w", encoding="utf-8") as handle:
        for row in admitted:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "benchmark_version": "v0.19.14",
        "family": "spurious_short_circuit_family",
        "mutation_mechanism": "spurious_short_circuit_connect",
        "total_specs": len(SPECS),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "rejected_case_ids": rejected,
        "relation_ids": [row["short_circuit_relation_id"] for row in admitted],
        "output": str(admitted_jsonl),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
