"""Build natural non-ground connect-deletion structural mutations for v0.19.26.

Design:
  - Start from existing MSL electrical source models only.
  - Enumerate all connect() lines.
  - Exclude ground-reference connects (already heavily covered by v0.19.12).
  - Remove exactly one non-ground connect() line to produce a natural deletion mutant.
  - Admit only source-PASS / mutant-FAIL structural cases.

This version is intentionally candidate-heavy and qualification-light:
Codex generates the candidate pool; OMC admission is the hard quality gate.
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
OUT_DIR = REPO_ROOT / "artifacts" / "non_ground_connect_deletion_mutations_v0_19_26"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
TARGET_SOURCE_FILES = {
    "large_sensorized_grid_v0.mo",
    "large_rlc_branches_v0.mo",
    "medium_ladder_rc_v0.mo",
    "large_rc_ladder4_v0.mo",
}

CONNECT_RE = re.compile(r"^\s*connect\s*\((?P<lhs>[^,]+)\s*,\s*(?P<rhs>[^)]+)\)\s*;\s*$")
MODEL_RE = re.compile(r"^\s*model\s+(?P<name>[A-Za-z0-9_]+)\s*$", re.MULTILINE)
COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)\s+equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConnectDeletionCandidate:
    source_file: str
    model_name: str
    candidate_id: str
    relation_id: str
    connect_line: str
    connect_kind: str
    connect_index: int


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
    models = []
    for path in sorted(SOURCE_DIR.glob("*.mo")):
        if TARGET_SOURCE_FILES and path.name not in TARGET_SOURCE_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        match = MODEL_RE.search(text)
        if not match:
            continue
        models.append((path, match.group("name"), text))
    return models


def _classify_connect_kind(connect_line: str) -> str:
    text = str(connect_line or "")
    if "G.p" in text or "G.n" in text:
        return "ground"
    if ".Sensors." in text:
        return "sensor"
    if any(token in text for token in ("VS", "CS")):
        return "sensor"
    if "V1." in text or "V2." in text or "V3." in text:
        return "source"
    return "internal_branch"


def _extract_non_ground_connects(model_text: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    for idx, line in enumerate(model_text.splitlines()):
        match = CONNECT_RE.match(line)
        if not match:
            continue
        connect_line = line.rstrip()
        kind = _classify_connect_kind(connect_line)
        if kind == "ground":
            continue
        rows.append((idx, connect_line, kind))
    return rows


def _sanitize_relation_id(connect_line: str) -> str:
    compact = re.sub(r"\s+", "", connect_line)
    compact = compact.replace("connect(", "").replace(");", "")
    compact = compact.replace(",", "__")
    compact = compact.replace(".", "_")
    compact = compact.replace("(", "_").replace(")", "_")
    compact = re.sub(r"[^A-Za-z0-9_]+", "_", compact)
    return compact.strip("_").lower()


def _build_mutated_text(source_text: str, connect_index: int) -> str:
    lines = source_text.splitlines()
    del lines[connect_index]
    return "\n".join(lines) + "\n"


def _extract_structural_counts(log_text: str) -> dict[str, int] | None:
    match = COUNT_RE.search(log_text)
    if not match:
        return None
    return {
        "equations": int(match.group("equations")),
        "variables": int(match.group("variables")),
    }


def _classify_failure(log_text: str, *, check_pass: bool, simulate_pass: bool) -> tuple[str, str]:
    text = str(log_text or "").lower()
    counts = _extract_structural_counts(log_text or "")
    if not check_pass:
        if counts and counts["equations"] > counts["variables"]:
            return "constraint_violation", "check"
        if counts and counts["variables"] > counts["equations"]:
            return "model_check_error", "check"
        if any(s in text for s in ("overdetermined", "too many equations", "overconstrained")):
            return "constraint_violation", "check"
        return "model_check_error", "check"
    if not simulate_pass:
        if any(
            s in text
            for s in (
                "pantelides",
                "index reduction",
                "empty set of continuous equations",
                "structurally singular",
                "not enough equations",
                "underdetermined",
                "under-determined",
            )
        ):
            return "simulate_error", "simulate"
        return "simulate_error", "simulate"
    return "none", "none"


def _build_candidates() -> list[ConnectDeletionCandidate]:
    rows: list[ConnectDeletionCandidate] = []
    for source_path, model_name, source_text in _load_source_models():
        connect_rows = _extract_non_ground_connects(source_text)
        for order, (idx, connect_line, kind) in enumerate(connect_rows, 1):
            relation_id = _sanitize_relation_id(connect_line)
            candidate_id = f"v01926_{source_path.stem}_delc_{order:02d}"
            rows.append(
                ConnectDeletionCandidate(
                    source_file=source_path.name,
                    model_name=model_name,
                    candidate_id=candidate_id,
                    relation_id=relation_id,
                    connect_line=connect_line.strip(),
                    connect_kind=kind,
                    connect_index=idx,
                )
            )
    return rows


def _admit_candidate(spec: ConnectDeletionCandidate, source_text: str) -> dict | None:
    source_check, source_check_log = _run_omc(source_text, spec.model_name, "check")
    source_sim, source_sim_log = _run_omc(source_text, spec.model_name, "simulate")
    if not source_check or not source_sim:
        raise RuntimeError(
            f"source model failed precheck for {spec.candidate_id}: "
            f"check={source_check} simulate={source_sim}\n{source_check_log}\n{source_sim_log}"
        )

    mutated_text = _build_mutated_text(source_text, spec.connect_index)
    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    mutated_check, mutated_check_log = _run_omc(mutated_text, spec.model_name, "check")
    mutated_sim, mutated_sim_log = _run_omc(mutated_text, spec.model_name, "simulate")
    if mutated_check and mutated_sim:
        return None

    log_text = mutated_check_log if not mutated_check else mutated_sim_log
    failure_type, expected_stage = _classify_failure(
        log_text,
        check_pass=mutated_check,
        simulate_pass=mutated_sim,
    )

    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "source_file": spec.source_file,
        "model_name": spec.model_name,
        "source_model_path": str(SOURCE_DIR / spec.source_file),
        "mutated_model_path": str(mutated_path),
        "workflow_goal": (
            "Repair the structural wiring mistake so the Modelica model compiles "
            "and simulates again while preserving the original circuit intent."
        ),
        "failure_type": failure_type,
        "expected_stage": expected_stage,
        "mutation_family": "non_ground_connect_deletion_reference",
        "mutation_mechanism": "deleted_non_ground_connect",
        "deleted_connect": spec.connect_line,
        "deleted_connect_kind": spec.connect_kind,
        "relation_id": spec.relation_id,
        "connect_index": spec.connect_index,
        "planner_backend": "auto",
        "backend": "openmodelica_docker",
        "admission_source": "omc_non_ground_connect_deletion_verified",
        "source_check_pass": True,
        "source_simulate_pass": True,
        "mutated_check_pass": mutated_check,
        "mutated_simulate_pass": mutated_sim,
        "mutated_failure_excerpt": log_text[:1200],
    }


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


def _admit_candidate_with_precheck(
    spec: ConnectDeletionCandidate,
    source_text: str,
    precheck: dict,
) -> dict | None:
    if not precheck["source_check"] or not precheck["source_sim"]:
        raise RuntimeError(
            f"source model failed precheck for {spec.candidate_id}: "
            f"check={precheck['source_check']} simulate={precheck['source_sim']}\n"
            f"{precheck['source_check_log']}\n{precheck['source_sim_log']}"
        )

    mutated_text = _build_mutated_text(source_text, spec.connect_index)
    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    mutated_check, mutated_check_log = _run_omc(mutated_text, spec.model_name, "check")
    mutated_sim, mutated_sim_log = _run_omc(mutated_text, spec.model_name, "simulate")
    if mutated_check and mutated_sim:
        return None

    log_text = mutated_check_log if not mutated_check else mutated_sim_log
    failure_type, expected_stage = _classify_failure(
        log_text,
        check_pass=mutated_check,
        simulate_pass=mutated_sim,
    )

    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "source_file": spec.source_file,
        "model_name": spec.model_name,
        "source_model_path": str(SOURCE_DIR / spec.source_file),
        "mutated_model_path": str(mutated_path),
        "workflow_goal": (
            "Repair the structural wiring mistake so the Modelica model compiles "
            "and simulates again while preserving the original circuit intent."
        ),
        "failure_type": failure_type,
        "expected_stage": expected_stage,
        "mutation_family": "non_ground_connect_deletion_reference",
        "mutation_mechanism": "deleted_non_ground_connect",
        "deleted_connect": spec.connect_line,
        "deleted_connect_kind": spec.connect_kind,
        "relation_id": spec.relation_id,
        "connect_index": spec.connect_index,
        "planner_backend": "auto",
        "backend": "openmodelica_docker",
        "admission_source": "omc_non_ground_connect_deletion_verified",
        "source_check_pass": True,
        "source_simulate_pass": True,
        "mutated_check_pass": mutated_check,
        "mutated_simulate_pass": mutated_sim,
        "mutated_failure_excerpt": log_text[:1200],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source_map = {path.name: (name, text) for path, name, text in _load_source_models()}
    source_prechecks = _precheck_sources(source_map)
    all_candidates = []
    admitted = []
    by_kind: dict[str, int] = {}
    by_stage: dict[str, int] = {}

    for spec in _build_candidates():
        all_candidates.append(
            {
                "candidate_id": spec.candidate_id,
                "source_file": spec.source_file,
                "model_name": spec.model_name,
                "relation_id": spec.relation_id,
                "deleted_connect": spec.connect_line,
                "deleted_connect_kind": spec.connect_kind,
                "connect_index": spec.connect_index,
            }
        )
        row = _admit_candidate_with_precheck(
            spec,
            source_map[spec.source_file][1],
            source_prechecks[spec.source_file],
        )
        if row is None:
            continue
        admitted.append(row)
        by_kind[row["deleted_connect_kind"]] = by_kind.get(row["deleted_connect_kind"], 0) + 1
        by_stage[row["expected_stage"]] = by_stage.get(row["expected_stage"], 0) + 1

    (OUT_DIR / "all_candidates.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_candidates) + ("\n" if all_candidates else ""),
        encoding="utf-8",
    )
    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in admitted) + ("\n" if admitted else ""),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.19.26",
        "candidate_pool_size": len(all_candidates),
        "admitted_case_count": len(admitted),
        "admitted_by_deleted_connect_kind": by_kind,
        "admitted_by_expected_stage": by_stage,
        "source_model_count": len(source_map),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
