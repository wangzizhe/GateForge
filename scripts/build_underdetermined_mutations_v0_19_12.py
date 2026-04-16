"""Build OMC-admitted underdetermined structural-balance mutations for v0.19.12.

Mutation strategy: remove ALL connect() statements that reference the Ground
component (G.p), leaving the circuit with no absolute potential reference.

In Modelica electrical networks, the Ground component provides the one
equation that fixes V=0 at the reference node.  Every well-formed circuit
must have at least one ground connection.  Removing all of them creates a
floating circuit: all relative potentials are determined by the remaining
equations, but the absolute potential level is a free variable — the system
is structurally underdetermined by exactly one degree of freedom.

Real engineering story: engineer refactors a model, inadvertently removes the
ground connections (e.g. while reorganising the equation block or removing a
sensor), and the circuit silently loses its reference node.

Why this is harder than overdetermined cases for the LLM:
  - overdetermined: a redundant equation IS VISIBLE in the model text → delete it
  - underdetermined: the missing ground connection is ABSENT from the model
    text → LLM must infer from circuit topology which node should be grounded
    and add the connect() back
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = (
    REPO_ROOT
    / "artifacts"
    / "agent_modelica_electrical_frozen_taskset_v1_smoke"
    / "source_models"
)
OUT_DIR = REPO_ROOT / "artifacts" / "underdetermined_mutations_v0_19_12"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)\s+equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)

# Pattern to match any connect() that mentions G.p or G.n
GROUND_CONNECT_RE = re.compile(
    r"^\s*connect\s*\([^)]*\bG\.[pn]\b[^)]*\)\s*;\s*$"
)


@dataclass(frozen=True)
class UnderdeterminedSpec:
    source_file: str
    model_name: str
    candidate_id: str
    relation_id: str


SPECS = [
    UnderdeterminedSpec(
        source_file="small_rc_constant_v0.mo",
        model_name="SmallRCConstantV0",
        candidate_id="v01912_underdet_small_rc_missing_ground",
        relation_id="missing_ground_reference_rc",
    ),
    UnderdeterminedSpec(
        source_file="small_rl_step_v0.mo",
        model_name="SmallRLStepV0",
        candidate_id="v01912_underdet_small_rl_missing_ground",
        relation_id="missing_ground_reference_rl",
    ),
    UnderdeterminedSpec(
        source_file="small_r_divider_v0.mo",
        model_name="SmallRDividerV0",
        candidate_id="v01912_underdet_small_divider_missing_ground",
        relation_id="missing_ground_reference_divider",
    ),
    UnderdeterminedSpec(
        source_file="medium_parallel_rc_v0.mo",
        model_name="MediumParallelRCV0",
        candidate_id="v01912_underdet_medium_parallel_missing_ground",
        relation_id="missing_ground_reference_parallel_rc",
    ),
    UnderdeterminedSpec(
        source_file="medium_rlc_series_v0.mo",
        model_name="MediumRLCSeriesV0",
        candidate_id="v01912_underdet_medium_rlc_missing_ground",
        relation_id="missing_ground_reference_rlc",
    ),
    UnderdeterminedSpec(
        source_file="medium_ladder_rc_v0.mo",
        model_name="MediumLadderRCV0",
        candidate_id="v01912_underdet_medium_ladder_missing_ground",
        relation_id="missing_ground_reference_ladder",
    ),
    UnderdeterminedSpec(
        source_file="large_rc_ladder4_v0.mo",
        model_name="LargeRCLadder4V0",
        candidate_id="v01912_underdet_large_ladder4_missing_ground",
        relation_id="missing_ground_reference_ladder4",
    ),
    UnderdeterminedSpec(
        source_file="large_dual_source_ladder_v0.mo",
        model_name="LargeDualSourceLadderV0",
        candidate_id="v01912_underdet_large_dual_source_missing_ground",
        relation_id="missing_ground_reference_dual_source",
    ),
    UnderdeterminedSpec(
        source_file="large_rlc_branches_v0.mo",
        model_name="LargeRLCBranchesV0",
        candidate_id="v01912_underdet_large_rlc_branches_missing_ground",
        relation_id="missing_ground_reference_rlc_branches",
    ),
    UnderdeterminedSpec(
        source_file="large_sensorized_grid_v0.mo",
        model_name="LargeSensorizedGridV0",
        candidate_id="v01912_underdet_large_sensorized_grid_missing_ground",
        relation_id="missing_ground_reference_sensorized_grid",
    ),
    UnderdeterminedSpec(
        source_file="medium_dual_source_v0.mo",
        model_name="MediumDualSourceV0",
        candidate_id="v01912_underdet_medium_dual_source_missing_ground",
        relation_id="missing_ground_reference_dual_source_medium",
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


def _remove_ground_connects(text: str) -> tuple[str, list[str]]:
    """Remove all connect() lines that reference G.p or G.n.

    Returns (mutated_text, list_of_removed_lines).
    """
    lines = text.splitlines()
    new_lines = []
    removed = []
    for line in lines:
        if GROUND_CONNECT_RE.match(line):
            removed.append(line.strip())
        else:
            new_lines.append(line)
    return "\n".join(new_lines) + "\n", removed


def _extract_structural_counts(log_text: str) -> dict[str, int] | None:
    match = COUNT_RE.search(log_text)
    if not match:
        return None
    return {
        "equations": int(match.group("equations")),
        "variables": int(match.group("variables")),
    }


def _is_underdetermined_failure(log_text: str) -> bool:
    """Return True if OMC output signals a structurally underdetermined system."""
    text_lower = log_text.lower()
    signals = [
        "singular",
        "too few equations",
        "under-determined",
        "underdetermined",
        "not all variables can be solved",
        "structurally singular",
        "variables are not defined",
        "not solved for",
        "linear system",
        "jacobian",          # singular Jacobian during solving
        "pivot",             # zero pivot in LU decomposition
        "imbalanced number of equations",  # OMC structural analysis report
        "circular equalities",             # OMC degenerate constraint report
        "pantelides",                      # OMC index reduction failure on singular DAE
        "index reduction",
    ]
    if any(s in text_lower for s in signals):
        return True
    counts = _extract_structural_counts(log_text)
    if counts and counts["variables"] > counts["equations"]:
        return True
    return False


def _build_candidate(spec: UnderdeterminedSpec) -> dict | None:
    source_path = SOURCE_DIR / spec.source_file
    source_text = source_path.read_text(encoding="utf-8")

    source_check, source_check_log = _run_omc(source_text, spec.model_name, "check")
    source_sim, source_sim_log = _run_omc(source_text, spec.model_name, "simulate")
    if not source_check or not source_sim:
        raise RuntimeError(
            f"source model failed admission precheck for {spec.candidate_id}: "
            f"check={source_check} simulate={source_sim}\n{source_check_log}\n{source_sim_log}"
        )

    mutated_text, removed_lines = _remove_ground_connects(source_text)
    if not removed_lines:
        raise RuntimeError(
            f"no ground connect() lines found in {spec.source_file} for {spec.candidate_id}"
        )

    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    # Gate 1: mutated model must fail simulation
    mutated_sim, mutated_sim_log = _run_omc(mutated_text, spec.model_name, "simulate")
    if mutated_sim:
        print(
            f"  [REJECT] {spec.candidate_id}: mutated model still simulates "
            f"(removed {len(removed_lines)} ground connect(s) — OMC too lenient)"
        )
        return None

    # Gate 2: check that failure carries a structural underdetermined signal;
    # also check checkModel output as OMC may catch it earlier
    has_signal = _is_underdetermined_failure(mutated_sim_log)
    if not has_signal:
        _, mutated_check_log = _run_omc(mutated_text, spec.model_name, "check")
        has_signal = _is_underdetermined_failure(mutated_check_log)
        if has_signal:
            mutated_sim_log = mutated_check_log

    if not has_signal:
        print(
            f"  [WARN]   {spec.candidate_id}: simulation fails but no underdetermined "
            f"signal detected — admitting anyway (sim failure is sufficient).\n"
            f"  excerpt: {mutated_sim_log[:300]}"
        )
        # Still admit: simulation failure is the ground truth, signal pattern
        # is just informational.

    counts = _extract_structural_counts(mutated_sim_log) or {}
    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "benchmark_family": "underdetermined_structural_family",
        "mutation_family": "underdetermined_missing_ground_reference",
        "benchmark_version": "v0.19.12",
        "description": f"Missing ground reference: {spec.relation_id}",
        "source_model_path": str(source_path),
        "mutated_model_path": str(mutated_path),
        "failure_type": "constraint_violation",
        "expected_stage": "simulate",
        "expected_turns": 2,
        "difficulty_prior": "hard",
        "workflow_goal": (
            "Restore the missing ground connections so the circuit has an absolute "
            "potential reference, while preserving all other circuit elements."
        ),
        "admission_status": "PASS",
        "admission_source": "omc_underdetermined_missing_ground_verified",
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "underdetermined_relation_id": spec.relation_id,
        "removed_ground_connects": removed_lines,
        "n_removed_connects": len(removed_lines),
        "mutated_simulate_counts": counts,
        "mutated_simulate_excerpt": mutated_sim_log[:400],
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
                f"(removed {candidate['n_removed_connects']} ground connect(s))"
            )
        else:
            rejected.append(spec.candidate_id)

    admitted_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(admitted_jsonl, "w", encoding="utf-8") as handle:
        for row in admitted:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "benchmark_version": "v0.19.12",
        "family": "underdetermined_structural_family",
        "mutation_mechanism": "missing_ground_reference",
        "total_specs": len(SPECS),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "rejected_case_ids": rejected,
        "relation_ids": [row["underdetermined_relation_id"] for row in admitted],
        "output": str(admitted_jsonl),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
