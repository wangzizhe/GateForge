"""Build pair connect-deletion structural mutations for v0.19.27.

Goal:
  - Move beyond single deleted non-ground connects (v0.19.26), which only
    produced stable single-fix anchors.
  - Generate more complex natural structural failures that are more likely to
    fail already at checkModel.

Strategy:
  - Use a small set of existing higher-connectivity MSL source models.
  - Enumerate pairs of non-ground connect() lines.
  - Restrict to pairs that share at least one exact endpoint token, e.g.
      connect(R1.n, R2.p);
      connect(R1.n, C1.p);
    This models a realistic refactor error around one structural node.
  - Exclude sensor-side connects in this first pair-deletion batch.
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
OUT_DIR = REPO_ROOT / "artifacts" / "pair_connect_deletion_mutations_v0_19_27"
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
class ConnectRow:
    index: int
    line: str
    kind: str
    lhs: str
    rhs: str


@dataclass(frozen=True)
class PairDeletionCandidate:
    source_file: str
    model_name: str
    candidate_id: str
    relation_id: str
    row_a: ConnectRow
    row_b: ConnectRow
    shared_endpoint: str


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


def _classify_connect_kind(connect_line: str) -> str:
    text = str(connect_line or "")
    if "G.p" in text or "G.n" in text:
        return "ground"
    if any(token in text for token in ("VS", "CS")):
        return "sensor"
    if "V1." in text or "V2." in text or "V3." in text:
        return "source"
    return "internal_branch"


def _extract_non_ground_non_sensor_connects(model_text: str) -> list[ConnectRow]:
    rows: list[ConnectRow] = []
    for idx, line in enumerate(model_text.splitlines()):
        match = CONNECT_RE.match(line)
        if not match:
            continue
        connect_line = line.rstrip()
        kind = _classify_connect_kind(connect_line)
        if kind in {"ground", "sensor"}:
            continue
        rows.append(
            ConnectRow(
                index=idx,
                line=connect_line.strip(),
                kind=kind,
                lhs=str(match.group("lhs")).strip(),
                rhs=str(match.group("rhs")).strip(),
            )
        )
    return rows


def _shared_endpoint(a: ConnectRow, b: ConnectRow) -> str:
    aset = {a.lhs, a.rhs}
    bset = {b.lhs, b.rhs}
    inter = sorted(aset & bset)
    return inter[0] if inter else ""


def _sanitize_token(token: str) -> str:
    token = token.replace(".", "_")
    token = re.sub(r"[^A-Za-z0-9_]+", "_", token)
    return token.strip("_").lower()


def _build_pair_candidates() -> list[PairDeletionCandidate]:
    rows: list[PairDeletionCandidate] = []
    for source_path, model_name, source_text in _load_source_models():
        connect_rows = _extract_non_ground_non_sensor_connects(source_text)
        order = 0
        for i, row_a in enumerate(connect_rows):
            for row_b in connect_rows[i + 1:]:
                shared = _shared_endpoint(row_a, row_b)
                if not shared:
                    continue
                order += 1
                candidate_id = f"v01927_{source_path.stem}_pairc_{order:02d}"
                relation_id = (
                    f"{_sanitize_token(shared)}__"
                    f"{_sanitize_token(row_a.lhs)}_{_sanitize_token(row_a.rhs)}__"
                    f"{_sanitize_token(row_b.lhs)}_{_sanitize_token(row_b.rhs)}"
                )
                rows.append(
                    PairDeletionCandidate(
                        source_file=source_path.name,
                        model_name=model_name,
                        candidate_id=candidate_id,
                        relation_id=relation_id,
                        row_a=row_a,
                        row_b=row_b,
                        shared_endpoint=shared,
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
            f"check={precheck['source_check']} simulate={precheck['source_sim']}\n"
            f"{precheck['source_check_log']}\n{precheck['source_sim_log']}"
        )

    mutated_text = _build_mutated_text(source_text, spec.row_a.index, spec.row_b.index)
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
            "Repair the structural wiring mistake so the Modelica model passes "
            "checkModel again while preserving the original circuit intent."
        ),
        "failure_type": failure_type,
        "expected_stage": "check",
        "mutation_family": "pair_connect_deletion_reference",
        "mutation_mechanism": "deleted_pair_of_non_ground_connects",
        "deleted_connects": [spec.row_a.line, spec.row_b.line],
        "deleted_connect_kinds": [spec.row_a.kind, spec.row_b.kind],
        "shared_endpoint": spec.shared_endpoint,
        "relation_id": spec.relation_id,
        "planner_backend": "auto",
        "backend": "openmodelica_docker",
        "admission_source": "omc_pair_connect_deletion_check_verified",
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
    by_shared_endpoint: dict[str, int] = {}
    by_failure_type: dict[str, int] = {}

    for spec in _build_pair_candidates():
        all_candidates.append(
            {
                "candidate_id": spec.candidate_id,
                "source_file": spec.source_file,
                "model_name": spec.model_name,
                "relation_id": spec.relation_id,
                "deleted_connects": [spec.row_a.line, spec.row_b.line],
                "deleted_connect_kinds": [spec.row_a.kind, spec.row_b.kind],
                "shared_endpoint": spec.shared_endpoint,
            }
        )
        row = _admit_candidate(spec, source_map[spec.source_file][1], prechecks[spec.source_file])
        if row is None:
            continue
        admitted.append(row)
        endpoint = str(row["shared_endpoint"])
        by_shared_endpoint[endpoint] = by_shared_endpoint.get(endpoint, 0) + 1
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
        "admitted_by_shared_endpoint": by_shared_endpoint,
        "source_model_count": len(source_map),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
