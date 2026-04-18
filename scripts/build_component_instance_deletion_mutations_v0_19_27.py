"""Build natural component-instance deletion mutations for v0.19.27.

Goal:
  - Move from easy simulate-layer connect deletions to stronger structural
    failures that land in checkModel.
  - Delete a real passive component declaration while leaving the surrounding
    wiring intact. This mirrors realistic edit mistakes during refactors.

Strategy:
  - Use existing higher-connectivity MSL source models only.
  - Enumerate passive component instance declarations (R/C/L families).
  - Keep only components that participate in at least two connect() lines.
  - Admit only cases where source passes and mutant fails at checkModel.
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
OUT_DIR = REPO_ROOT / "artifacts" / "component_instance_deletion_mutations_v0_19_27"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
TARGET_SOURCE_FILES = {
    "large_sensorized_grid_v0.mo",
    "large_rlc_branches_v0.mo",
    "medium_ladder_rc_v0.mo",
    "large_rc_ladder4_v0.mo",
}

MODEL_RE = re.compile(r"^\s*model\s+(?P<name>[A-Za-z0-9_]+)\s*$", re.MULTILINE)
DECL_RE = re.compile(
    r"^\s*Modelica\.Electrical\.Analog\.(?:Basic|Sources|Sensors)\.[A-Za-z0-9_]+\s+"
    r"(?P<instance>[A-Za-z_][A-Za-z0-9_]*)\b.*;\s*$"
)
CONNECT_RE = re.compile(r"^\s*connect\s*\((?P<lhs>[^,]+)\s*,\s*(?P<rhs>[^)]+)\)\s*;\s*$")
COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)\s+equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ComponentRow:
    index: int
    line: str
    instance: str
    component_kind: str


@dataclass(frozen=True)
class ComponentDeletionCandidate:
    source_file: str
    model_name: str
    candidate_id: str
    component: ComponentRow
    connect_count: int


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
    return passed, error_text if error_text else output[:1200]


def _load_source_models() -> list[tuple[Path, str, str]]:
    rows = []
    for path in sorted(SOURCE_DIR.glob("*.mo")):
        if TARGET_SOURCE_FILES and path.name not in TARGET_SOURCE_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        match = MODEL_RE.search(text)
        if not match:
            continue
        rows.append((path, match.group("name"), text))
    return rows


def _classify_component_kind(line: str) -> str:
    if ".Resistor " in line:
        return "resistor"
    if ".Capacitor " in line:
        return "capacitor"
    if ".Inductor " in line:
        return "inductor"
    if ".Ground " in line:
        return "ground"
    if ".VoltageSensor " in line or ".CurrentSensor " in line:
        return "sensor"
    if ".Voltage " in line or ".Current " in line:
        return "source"
    return "other"


def _extract_passive_components(model_text: str) -> list[ComponentRow]:
    rows: list[ComponentRow] = []
    for idx, line in enumerate(model_text.splitlines()):
        match = DECL_RE.match(line)
        if not match:
            continue
        decl = line.rstrip()
        instance = str(match.group("instance")).strip()
        kind = _classify_component_kind(decl)
        if kind not in {"resistor", "capacitor", "inductor"}:
            continue
        rows.append(
            ComponentRow(
                index=idx,
                line=decl.strip(),
                instance=instance,
                component_kind=kind,
            )
        )
    return rows


def _count_instance_connects(model_text: str, instance: str) -> int:
    prefix = f"{instance}."
    count = 0
    for line in model_text.splitlines():
        match = CONNECT_RE.match(line)
        if not match:
            continue
        lhs = str(match.group("lhs")).strip()
        rhs = str(match.group("rhs")).strip()
        if lhs.startswith(prefix) or rhs.startswith(prefix):
            count += 1
    return count


def _sanitize_token(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", token).strip("_").lower()


def _build_candidates() -> list[ComponentDeletionCandidate]:
    rows: list[ComponentDeletionCandidate] = []
    for source_path, model_name, source_text in _load_source_models():
        order = 0
        for component in _extract_passive_components(source_text):
            connect_count = _count_instance_connects(source_text, component.instance)
            if connect_count < 2:
                continue
            order += 1
            rows.append(
                ComponentDeletionCandidate(
                    source_file=source_path.name,
                    model_name=model_name,
                    candidate_id=f"v01927_{source_path.stem}_compdel_{order:02d}_{_sanitize_token(component.instance)}",
                    component=component,
                    connect_count=connect_count,
                )
            )
    return rows


def _build_mutated_text(source_text: str, idx: int) -> str:
    lines = source_text.splitlines()
    del lines[idx]
    return "\n".join(lines) + "\n"


def _extract_structural_counts(log_text: str) -> dict[str, int] | None:
    match = COUNT_RE.search(log_text)
    if not match:
        return None
    return {
        "equations": int(match.group("equations")),
        "variables": int(match.group("variables")),
    }


def _classify_check_failure(log_text: str) -> str:
    text = str(log_text or "").lower()
    counts = _extract_structural_counts(log_text or "")
    if counts and counts["equations"] > counts["variables"]:
        return "constraint_violation"
    if any(s in text for s in ("overdetermined", "too many equations", "overconstrained")):
        return "constraint_violation"
    return "model_check_error"


def _precheck_sources(source_map: dict[str, tuple[str, str]]) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    for source_file, (model_name, source_text) in source_map.items():
        source_check, source_check_log = _run_omc(source_text, model_name, "check")
        source_sim, source_sim_log = _run_omc(source_text, model_name, "simulate")
        cache[source_file] = {
            "source_check": source_check,
            "source_check_log": source_check_log,
            "source_sim": source_sim,
            "source_sim_log": source_sim_log,
        }
    return cache


def _admit_candidate(spec: ComponentDeletionCandidate, source_text: str, precheck: dict) -> dict | None:
    if not precheck["source_check"] or not precheck["source_sim"]:
        raise RuntimeError(
            f"source model failed precheck for {spec.candidate_id}: "
            f"check={precheck['source_check']} simulate={precheck['source_sim']}\n"
            f"{precheck['source_check_log']}\n{precheck['source_sim_log']}"
        )

    mutated_text = _build_mutated_text(source_text, spec.component.index)
    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    mutated_check, mutated_check_log = _run_omc(mutated_text, spec.model_name, "check")
    if mutated_check:
        return None

    failure_type = _classify_check_failure(mutated_check_log)
    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "source_file": spec.source_file,
        "model_name": spec.model_name,
        "source_model_path": str(SOURCE_DIR / spec.source_file),
        "mutated_model_path": str(mutated_path),
        "workflow_goal": (
            "Repair the structural component deletion so the Modelica model passes "
            "checkModel again while preserving the original circuit intent."
        ),
        "failure_type": failure_type,
        "expected_stage": "check",
        "mutation_family": "component_instance_deletion_reference",
        "mutation_mechanism": "deleted_passive_component_instance",
        "deleted_component_line": spec.component.line,
        "deleted_component_instance": spec.component.instance,
        "deleted_component_kind": spec.component.component_kind,
        "deleted_component_connect_count": spec.connect_count,
        "planner_backend": "auto",
        "backend": "openmodelica_docker",
        "admission_source": "omc_component_instance_deletion_check_verified",
        "source_check_pass": True,
        "source_simulate_pass": True,
        "mutated_check_pass": False,
        "mutated_failure_excerpt": mutated_check_log[:1200],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source_map = {path.name: (name, text) for path, name, text in _load_source_models()}
    prechecks = _precheck_sources(source_map)
    all_candidates = []
    admitted = []
    by_component_kind: dict[str, int] = {}
    by_failure_type: dict[str, int] = {}

    for spec in _build_candidates():
        all_candidates.append(
            {
                "candidate_id": spec.candidate_id,
                "source_file": spec.source_file,
                "model_name": spec.model_name,
                "deleted_component_line": spec.component.line,
                "deleted_component_instance": spec.component.instance,
                "deleted_component_kind": spec.component.component_kind,
                "deleted_component_connect_count": spec.connect_count,
            }
        )
        row = _admit_candidate(spec, source_map[spec.source_file][1], prechecks[spec.source_file])
        if row is None:
            continue
        admitted.append(row)
        ckind = str(row["deleted_component_kind"])
        by_component_kind[ckind] = by_component_kind.get(ckind, 0) + 1
        ftype = str(row["failure_type"])
        by_failure_type[ftype] = by_failure_type.get(ftype, 0) + 1

    (OUT_DIR / "all_candidates.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_candidates) + ("\n" if all_candidates else ""),
        encoding="utf-8",
    )
    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in admitted) + ("\n" if admitted else ""),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.19.27",
        "candidate_pool_size": len(all_candidates),
        "admitted_case_count": len(admitted),
        "admitted_by_failure_type": by_failure_type,
        "admitted_by_component_kind": by_component_kind,
        "source_model_count": len(source_map),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
