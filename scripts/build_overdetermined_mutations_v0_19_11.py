"""Build OMC-admitted overdetermined structural-balance mutations for v0.19.11."""
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
OUT_DIR = REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_11"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)\s+equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OverdeterminedSpec:
    source_file: str
    model_name: str
    candidate_id: str
    relation_id: str
    redundant_equation: str


SPECS = [
    OverdeterminedSpec(
        source_file="small_rc_constant_v0.mo",
        model_name="SmallRCConstantV0",
        candidate_id="v01911_overdet_small_rc_kvl",
        relation_id="loop_kvl_source_resistor_capacitor",
        redundant_equation="  R1.v + C1.v = V1.v;",
    ),
    OverdeterminedSpec(
        source_file="small_rl_step_v0.mo",
        model_name="SmallRLStepV0",
        candidate_id="v01911_overdet_small_rl_kvl",
        relation_id="loop_kvl_source_inductor_resistor",
        redundant_equation="  L1.v + R1.v = V1.v;",
    ),
    OverdeterminedSpec(
        source_file="small_r_divider_v0.mo",
        model_name="SmallRDividerV0",
        candidate_id="v01911_overdet_small_divider_kvl",
        relation_id="divider_kvl_total_drop",
        redundant_equation="  R1.v + R2.v = V1.v;",
    ),
    OverdeterminedSpec(
        source_file="medium_ladder_rc_v0.mo",
        model_name="MediumLadderRCV0",
        candidate_id="v01911_overdet_medium_ladder_terminal_kvl",
        relation_id="terminal_branch_kvl",
        redundant_equation="  R1.v + R2.v + C2.v = V1.v;",
    ),
    OverdeterminedSpec(
        source_file="medium_parallel_rc_v0.mo",
        model_name="MediumParallelRCV0",
        candidate_id="v01911_overdet_medium_parallel_branch_kvl",
        relation_id="parallel_branch_kvl",
        redundant_equation="  R1.v + C1.v = V1.v;",
    ),
    OverdeterminedSpec(
        source_file="medium_rlc_series_v0.mo",
        model_name="MediumRLCSeriesV0",
        candidate_id="v01911_overdet_medium_rlc_kvl",
        relation_id="series_kvl_total_drop",
        redundant_equation="  R1.v + L1.v + C1.v = V1.v;",
    ),
    OverdeterminedSpec(
        source_file="large_rc_ladder4_v0.mo",
        model_name="LargeRCLadder4V0",
        candidate_id="v01911_overdet_large_ladder_terminal_kvl",
        relation_id="deep_terminal_branch_kvl",
        redundant_equation="  R1.v + R2.v + R3.v + R4.v + C4.v = V1.v;",
    ),
    OverdeterminedSpec(
        source_file="large_dual_source_ladder_v0.mo",
        model_name="LargeDualSourceLadderV0",
        candidate_id="v01911_overdet_large_dual_source_branch_kvl",
        relation_id="source_one_branch_kvl",
        redundant_equation="  R1.v + L1.v + R3.v + C1.v = V1.v;",
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


def _extract_structural_counts(log_text: str) -> dict[str, int] | None:
    match = COUNT_RE.search(log_text)
    if not match:
        return None
    return {
        "equations": int(match.group("equations")),
        "variables": int(match.group("variables")),
    }


def _is_overdetermined_failure(log_text: str) -> bool:
    counts = _extract_structural_counts(log_text)
    return bool(
        counts
        and counts["equations"] > counts["variables"]
        and "too many equations" in log_text.lower()
    )


def _build_candidate(spec: OverdeterminedSpec) -> dict | None:
    source_path = SOURCE_DIR / spec.source_file
    source_text = source_path.read_text(encoding="utf-8")
    source_check, source_check_log = _run_omc(source_text, spec.model_name, "check")
    source_sim, source_sim_log = _run_omc(source_text, spec.model_name, "simulate")
    if not source_check or _is_overdetermined_failure(source_check_log) or not source_sim:
        raise RuntimeError(
            f"source model failed admission precheck for {spec.candidate_id}: "
            f"check={source_check} simulate={source_sim}\n{source_check_log}\n{source_sim_log}"
        )

    mutated_text = _insert_after_equation(source_text, spec.redundant_equation)
    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    mutated_simulate, mutated_sim_log = _run_omc(mutated_text, spec.model_name, "simulate")
    if mutated_simulate:
        return None
    if not _is_overdetermined_failure(mutated_sim_log):
        return None

    counts = _extract_structural_counts(mutated_sim_log) or {}
    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "benchmark_family": "overdetermined_structural_family",
        "mutation_family": "overdetermined_redundant_relation",
        "benchmark_version": "v0.19.11",
        "description": f"Overdetermined redundant relation: {spec.relation_id}",
        "source_model_path": str(source_path),
        "mutated_model_path": str(mutated_path),
        "failure_type": "constraint_violation",
        "expected_stage": "simulate",
        "expected_turns": 2,
        "difficulty_prior": "hard",
        "workflow_goal": "Remove the redundant structural relation while preserving the source electrical model.",
        "admission_status": "PASS",
        "admission_source": "omc_overdetermined_relation_verified",
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "overdetermined_relation_id": spec.relation_id,
        "redundant_relation_equation": spec.redundant_equation.strip(),
        "mutated_simulate_counts": counts,
        "mutated_simulate_excerpt": mutated_sim_log[:400],
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    admitted = []
    rejected = []
    for spec in SPECS:
        candidate = _build_candidate(spec)
        if candidate:
            admitted.append(candidate)
        else:
            rejected.append(spec.candidate_id)

    admitted_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(admitted_jsonl, "w", encoding="utf-8") as handle:
        for row in admitted:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "benchmark_version": "v0.19.11",
        "family": "overdetermined_structural_family",
        "total_specs": len(SPECS),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "rejected_case_ids": rejected,
        "relation_ids": [row["overdetermined_relation_id"] for row in admitted],
        "output": str(admitted_jsonl),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
