"""Build branch-closing passive component pair deletions for v0.19.29."""
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
OUT_DIR = REPO_ROOT / "artifacts" / "branch_component_pair_deletion_mutations_v0_19_29"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
TARGET_SOURCE_FILES = {
    "large_sensorized_grid_v0.mo",
    "large_rlc_branches_v0.mo",
    "medium_ladder_rc_v0.mo",
    "large_rc_ladder4_v0.mo",
}

MODEL_RE = re.compile(r"^\s*model\s+(?P<name>[A-Za-z0-9_]+)\s*$", re.MULTILINE)
DECL_RE = re.compile(
    r"^\s*Modelica\.Electrical\.Analog\.Basic\.(?P<class_name>[A-Za-z0-9_]+)\s+"
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
class PairDeletionCandidate:
    source_file: str
    model_name: str
    candidate_id: str
    component_a: ComponentRow
    component_b: ComponentRow
    connecting_line: str


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


def _map_passive_components(model_text: str) -> dict[str, ComponentRow]:
    rows: dict[str, ComponentRow] = {}
    for idx, line in enumerate(model_text.splitlines()):
        match = DECL_RE.match(line)
        if not match:
            continue
        class_name = str(match.group("class_name")).strip()
        if class_name not in {"Resistor", "Capacitor", "Inductor"}:
            continue
        instance = str(match.group("instance")).strip()
        rows[instance] = ComponentRow(
            index=idx,
            line=line.rstrip().strip(),
            instance=instance,
            component_kind=class_name.lower(),
        )
    return rows


def _sanitize_token(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", token).strip("_").lower()


def _build_candidates() -> list[PairDeletionCandidate]:
    rows: list[PairDeletionCandidate] = []
    for source_path, model_name, source_text in _load_source_models():
        components = _map_passive_components(source_text)
        seen: set[tuple[str, str]] = set()
        order = 0
        for line in source_text.splitlines():
            match = CONNECT_RE.match(line)
            if not match:
                continue
            lhs = str(match.group("lhs")).strip()
            rhs = str(match.group("rhs")).strip()
            if "." not in lhs or "." not in rhs:
                continue
            comp_a = lhs.split(".", 1)[0]
            comp_b = rhs.split(".", 1)[0]
            if comp_a == comp_b or comp_a not in components or comp_b not in components:
                continue
            key = tuple(sorted((comp_a, comp_b)))
            if key in seen:
                continue
            seen.add(key)
            order += 1
            rows.append(
                PairDeletionCandidate(
                    source_file=source_path.name,
                    model_name=model_name,
                    candidate_id=(
                        f"v01929_{source_path.stem}_branchpair_{order:02d}_"
                        f"{_sanitize_token(key[0])}_{_sanitize_token(key[1])}"
                    ),
                    component_a=components[key[0]],
                    component_b=components[key[1]],
                    connecting_line=line.strip(),
                )
            )
    return rows


def _build_mutated_text(source_text: str, idx_a: int, idx_b: int) -> str:
    lines = source_text.splitlines()
    for idx in sorted([idx_a, idx_b], reverse=True):
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


def _admit_candidate(spec: PairDeletionCandidate, source_text: str, precheck: dict) -> dict | None:
    if not precheck["source_check"] or not precheck["source_sim"]:
        raise RuntimeError(
            f"source model failed precheck for {spec.candidate_id}: "
            f"check={precheck['source_check']} simulate={precheck['source_sim']}"
        )

    mutated_text = _build_mutated_text(source_text, spec.component_a.index, spec.component_b.index)
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
            "Repair the structural branch deletion so the Modelica model passes "
            "checkModel again while preserving the original circuit intent."
        ),
        "failure_type": failure_type,
        "expected_stage": "check",
        "mutation_family": "branch_component_pair_deletion_reference",
        "mutation_mechanism": "deleted_passive_component_pair_on_same_branch",
        "deleted_component_lines": [spec.component_a.line, spec.component_b.line],
        "deleted_component_instances": [spec.component_a.instance, spec.component_b.instance],
        "deleted_component_kinds": [spec.component_a.component_kind, spec.component_b.component_kind],
        "connecting_line": spec.connecting_line,
        "planner_backend": "auto",
        "backend": "openmodelica_docker",
        "admission_source": "omc_branch_component_pair_deletion_check_verified",
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
    by_failure_type: dict[str, int] = {}
    by_pair_signature: dict[str, int] = {}

    for spec in _build_candidates():
        pair_signature = "+".join(sorted([spec.component_a.component_kind, spec.component_b.component_kind]))
        all_candidates.append(
            {
                "candidate_id": spec.candidate_id,
                "source_file": spec.source_file,
                "deleted_component_lines": [spec.component_a.line, spec.component_b.line],
                "deleted_component_instances": [spec.component_a.instance, spec.component_b.instance],
                "deleted_component_kinds": [spec.component_a.component_kind, spec.component_b.component_kind],
                "connecting_line": spec.connecting_line,
                "pair_signature": pair_signature,
            }
        )
        row = _admit_candidate(spec, source_map[spec.source_file][1], prechecks[spec.source_file])
        if row is None:
            continue
        admitted.append(row)
        ftype = str(row["failure_type"])
        by_failure_type[ftype] = by_failure_type.get(ftype, 0) + 1
        by_pair_signature[pair_signature] = by_pair_signature.get(pair_signature, 0) + 1

    (OUT_DIR / "all_candidates.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_candidates) + ("\n" if all_candidates else ""),
        encoding="utf-8",
    )
    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in admitted) + ("\n" if admitted else ""),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.19.29",
        "candidate_pool_size": len(all_candidates),
        "admitted_case_count": len(admitted),
        "admitted_by_failure_type": by_failure_type,
        "admitted_by_pair_signature": by_pair_signature,
        "source_model_count": len(source_map),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
