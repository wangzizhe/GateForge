"""Build OMC-admitted underdetermined probe cases for the deficit=3 experiment (v0.19.17).

Purpose
-------
Test whether the LLM can restore *all* missing ground connections in a single
repair step when the OMC error message explicitly exposes multiple floating
nodes at once, versus the iterative one-at-a-time behaviour observed for the
existing deficit=1 cases.

Prior evidence
--------------
- deficit=1 cases (small_divider, medium_ladder, ...): LLM adds grounds
  one per round → 3 rounds to finish
- deficit=2 case (large_sensorized_grid): LLM added both missing grounds in
  one repair step → 2 rounds (single_fix_closure)
- deficit=3: unknown — this probe answers whether that pattern holds

Source model: medium_triple_sensor_v0.mo
  Series circuit V1 → R1 → R2 → R3 → C1 → V1.n with three voltage sensors
  VS1, VS2, VS3 each measuring a different node.  Four independent ground
  connections: V1.n, VS1.n, VS2.n, VS3.n.
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
OUT_DIR = REPO_ROOT / "artifacts" / "underdetermined_deficit3_probe_v0_19_17"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)"
    r"\s+equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)
GROUND_CONNECT_RE = re.compile(
    r"^\s*connect\s*\([^)]*\bG\.[pn]\b[^)]*\)\s*;\s*$"
)
DEFICIT_RE = re.compile(
    r"imbalanced number of equations\s*\((\d+)\)\s*and variables\s*\((\d+)\)"
)


@dataclass(frozen=True)
class ProbeSpec:
    source_file: str
    model_name: str
    candidate_id: str
    relation_id: str


SPECS = [
    ProbeSpec(
        source_file="medium_triple_sensor_v0.mo",
        model_name="MediumTripleSensorV0",
        candidate_id="v01917_underdet_medium_triple_sensor_missing_ground",
        relation_id="missing_ground_reference_triple_sensor",
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
    if action == "check":
        passed = any(l == "true" for l in lines) and "Error" not in error_text
    else:
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


def _extract_deficit(log_text: str) -> dict:
    m = DEFICIT_RE.search(log_text)
    if m:
        eq, var = int(m.group(1)), int(m.group(2))
        return {"equations": eq, "variables": var, "deficit": var - eq}
    return {}


def _build_candidate(spec: ProbeSpec) -> dict | None:
    source_path = SOURCE_DIR / spec.source_file
    source_text = source_path.read_text(encoding="utf-8")

    print(f"  Checking source model...")
    src_check, src_check_log = _run_omc(source_text, spec.model_name, "check")
    src_sim, src_sim_log = _run_omc(source_text, spec.model_name, "simulate")
    if not src_check or not src_sim:
        raise RuntimeError(
            f"source model failed admission precheck:\n"
            f"check={src_check}\n{src_check_log}\n"
            f"simulate={src_sim}\n{src_sim_log}"
        )
    print(f"  Source: check=PASS simulate=PASS")

    mutated_text, removed_lines = _remove_ground_connects(source_text)
    if not removed_lines:
        raise RuntimeError(f"no ground connects found in {spec.source_file}")

    print(f"  Removed {len(removed_lines)} ground connect(s): {removed_lines}")

    mut_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mut_path.write_text(mutated_text, encoding="utf-8")

    print(f"  Checking mutated model...")
    mut_sim, mut_sim_log = _run_omc(mutated_text, spec.model_name, "simulate")
    if mut_sim:
        print(f"  [REJECT] mutated model still simulates — underdetermination not detectable")
        return None

    deficit_info = _extract_deficit(mut_sim_log)
    print(f"  Mutated simulate: FAIL  deficit_info={deficit_info}")
    print(f"  OMC excerpt: {mut_sim_log[:600]}")

    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "benchmark_family": "underdetermined_structural_family",
        "mutation_family": "underdetermined_missing_ground_reference",
        "benchmark_version": "v0.19.17",
        "description": f"Missing ground reference (triple sensor): {spec.relation_id}",
        "source_model_path": str(source_path),
        "mutated_model_path": str(mut_path),
        "failure_type": "constraint_violation",
        "expected_stage": "simulate",
        "expected_turns": 2,
        "difficulty_prior": "hard",
        "workflow_goal": (
            "Restore all missing ground connections so the circuit has an absolute "
            "potential reference, while preserving all other circuit elements."
        ),
        "admission_status": "PASS",
        "admission_source": "omc_underdetermined_missing_ground_verified",
        "planner_backend": "gemini",
        "backend": "openmodelica_docker",
        "underdetermined_relation_id": spec.relation_id,
        "removed_ground_connects": removed_lines,
        "n_removed_connects": len(removed_lines),
        "deficit_info": deficit_info,
        "mutated_simulate_excerpt": mut_sim_log[:600],
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    admitted, rejected = [], []

    for spec in SPECS:
        print(f"\nBuilding {spec.candidate_id} ...")
        try:
            candidate = _build_candidate(spec)
        except RuntimeError as exc:
            print(f"  [ERROR] {exc}")
            rejected.append(spec.candidate_id)
            continue
        if candidate:
            admitted.append(candidate)
            print(f"  [ADMIT] {spec.candidate_id}")
        else:
            rejected.append(spec.candidate_id)

    out_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        for row in admitted:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "probe_version": "v0.19.17",
        "experiment": "deficit_3_ground_restore_probe",
        "hypothesis": (
            "LLM can restore all N missing grounds in one repair step when "
            "OMC explicitly lists all N floating nodes (deficit=N visible)."
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
