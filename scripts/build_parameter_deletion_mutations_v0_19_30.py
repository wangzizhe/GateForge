"""Build parameter-deletion structural mutations for v0.19.30.

Priority:
1. Try cross-domain hierarchical source models (OpenIPSL / Buildings).
2. If none are source-viable, fall back to MSL models with top-level parameter declarations.

Admission:
  - source: checkModel PASS + simulate PASS
  - mutant: checkModel FAIL
  - at least one OMC error location must differ from the deleted declaration line
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)


OUT_DIR = REPO_ROOT / "artifacts" / "parameter_deletion_mutations_v0_19_30"

OPENIPSL_FIXTURE_DIR = (
    REPO_ROOT
    / "assets_private"
    / "agent_modelica_cross_domain_openipsl_v1_fixture_v1"
    / "source_models"
)
BUILDINGS_FIXTURE_DIR = (
    REPO_ROOT
    / "assets_private"
    / "agent_modelica_cross_domain_buildings_v1_fixture_v1"
    / "source_models"
)
OPENIPSL_LIBRARY_ROOT = (
    REPO_ROOT / "assets_private" / "modelica_sources" / "openipsl" / "OpenIPSL"
)
BUILDINGS_LIBRARY_ROOT = (
    REPO_ROOT / "assets_private" / "modelica_sources" / "modelica_buildings" / "Buildings"
)
MSL_SOURCE_DIR = (
    REPO_ROOT
    / "artifacts"
    / "agent_modelica_electrical_frozen_taskset_v1_smoke"
    / "source_models"
)
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

WITHIN_RE = re.compile(r"^\s*within\s+([^;]+);\s*$", re.MULTILINE)
MODEL_RE = re.compile(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
PARAM_RE = re.compile(
    r"^\s*parameter\s+(?P<type>.+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<mods>\([^)]*\))?\s*=\s*(?P<rhs>.+?)\s*;\s*$",
    re.DOTALL,
)
ERROR_LINE_RE = re.compile(r":(?P<line>\d+):(?P<col>\d+)(?:-|:|\b)")
COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)\s+"
    r"equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceSpec:
    source_file: str
    source_path: Path
    library_root: Path | None
    package_name: str
    qualified_model_name: str
    source_library_model_path: Path | None
    source_family: str
    viability_group: str


@dataclass(frozen=True)
class ParameterCandidate:
    source_spec: SourceSpec
    candidate_id: str
    model_name: str
    line_index: int
    line_no: int
    line_text: str
    parameter_name: str
    parameter_context: str
    reference_count: int


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_qualified_model_name(model_text: str) -> str:
    within_match = WITHIN_RE.search(model_text)
    model_match = MODEL_RE.search(model_text)
    if not model_match:
        raise ValueError("model name not found")
    model_name = str(model_match.group(1)).strip()
    within_name = str(within_match.group(1)).strip() if within_match else ""
    return f"{within_name}.{model_name}" if within_name else model_name


def _infer_library_model_path(library_root: Path, qualified_model_name: str) -> Path:
    parts = qualified_model_name.split(".")
    if not parts:
        raise ValueError(f"invalid qualified model name: {qualified_model_name}")
    if parts[0] == library_root.name:
        rel_parts = parts[1:]
    else:
        rel_parts = parts
    return library_root.joinpath(*rel_parts[:-1], f"{parts[-1]}.mo")


def _collect_cross_domain_sources() -> list[SourceSpec]:
    rows = []
    targets = [
        (OPENIPSL_FIXTURE_DIR / "GENROE_12c13f38c4.mo", OPENIPSL_LIBRARY_ROOT, "OpenIPSL", "openipsl"),
        (OPENIPSL_FIXTURE_DIR / "Gen_gov_exc_stab_fbf4a905e1.mo", OPENIPSL_LIBRARY_ROOT, "OpenIPSL", "openipsl"),
        (OPENIPSL_FIXTURE_DIR / "CSVGN1_dc3e8a4ebd.mo", OPENIPSL_LIBRARY_ROOT, "OpenIPSL", "openipsl"),
        (BUILDINGS_FIXTURE_DIR / "LimPIDWithReset_03ab422590.mo", BUILDINGS_LIBRARY_ROOT, "Buildings", "buildings"),
    ]
    for source_path, library_root, package_name, family in targets:
        if not source_path.exists():
            continue
        model_text = _read_text(source_path)
        qualified_model_name = _extract_qualified_model_name(model_text)
        rows.append(
            SourceSpec(
                source_file=source_path.name,
                source_path=source_path,
                library_root=library_root,
                package_name=package_name,
                qualified_model_name=qualified_model_name,
                source_library_model_path=_infer_library_model_path(library_root, qualified_model_name),
                source_family=family,
                viability_group="cross_domain",
            )
        )
    return rows


def _collect_msl_fallback_sources() -> list[SourceSpec]:
    rows = []
    for source_path in sorted(MSL_SOURCE_DIR.glob("*.mo")):
        text = _read_text(source_path)
        if not re.search(r"^\s*parameter\b", text, re.MULTILINE):
            continue
        rows.append(
            SourceSpec(
                source_file=source_path.name,
                source_path=source_path,
                library_root=None,
                package_name="",
                qualified_model_name=_extract_qualified_model_name(text),
                source_library_model_path=None,
                source_family="msl_electrical",
                viability_group="msl_fallback",
            )
        )
    return rows


def _run_model_text(
    *,
    model_text: str,
    source_spec: SourceSpec,
    stop_time: float = 0.2,
    intervals: int = 20,
) -> tuple[int | None, str, bool, bool]:
    model_name = source_spec.qualified_model_name.rsplit(".", 1)[-1]
    with temporary_workspace("gf_param_del_v01930_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(source_spec.source_file),
            primary_model_name=model_name,
            source_library_path=str(source_spec.library_root or ""),
            source_package_name=source_spec.package_name,
            source_library_model_path=str(source_spec.source_library_model_path or ""),
            source_qualified_model_name=source_spec.qualified_model_name,
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        return run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=300,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=float(stop_time),
            intervals=int(intervals),
            extra_model_loads=[],
        )


def _source_viability(source_spec: SourceSpec) -> dict:
    model_text = _read_text(source_spec.source_path)
    rc, output, check_ok, sim_ok = _run_model_text(model_text=model_text, source_spec=source_spec)
    reason = "source_model_viable" if check_ok and sim_ok else "source_model_not_viable"
    return {
        "source_check_pass": bool(check_ok),
        "source_simulate_pass": bool(sim_ok),
        "source_viable": bool(check_ok and sim_ok),
        "reason": reason,
        "rc": int(rc) if rc is not None else None,
        "stderr_snippet": str(output or "")[-2000:],
    }


def _find_parameter_candidates(source_spec: SourceSpec) -> list[ParameterCandidate]:
    text = _read_text(source_spec.source_path)
    lines = text.splitlines()
    results: list[ParameterCandidate] = []
    in_protected = False
    model_name = source_spec.qualified_model_name.rsplit(".", 1)[-1]
    order = 0
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if stripped.startswith("protected"):
            in_protected = True
            idx += 1
            continue
        if stripped.startswith(("equation", "initial equation", "algorithm", "initial algorithm")):
            in_protected = False
        statement_lines = [line]
        end_idx = idx
        if stripped.startswith("parameter") and ";" not in line:
            while end_idx + 1 < len(lines):
                end_idx += 1
                statement_lines.append(lines[end_idx])
                if ";" in lines[end_idx]:
                    break
        statement = "\n".join(statement_lines)
        match = PARAM_RE.match(statement)
        if not match:
            idx = end_idx + 1
            continue
        name = str(match.group("name")).strip()
        occurrences = len(re.findall(rf"\b{re.escape(name)}\b", text))
        reference_count = max(0, occurrences - 1)
        if source_spec.viability_group == "cross_domain":
            if reference_count < 2:
                idx = end_idx + 1
                continue
        else:
            if reference_count < 1:
                idx = end_idx + 1
                continue
        context = "protected_parameter" if in_protected else "top_level_parameter"
        order += 1
        results.append(
            ParameterCandidate(
                source_spec=source_spec,
                candidate_id=(
                    f"v01930_{source_spec.source_path.stem}_paramdel_{order:02d}_{name.lower()}"
                ),
                model_name=model_name,
                line_index=idx,
                line_no=idx + 1,
                line_text=statement.rstrip(),
                parameter_name=name,
                parameter_context=context,
                reference_count=reference_count,
            )
        )
        idx = end_idx + 1
    return results


def _build_mutated_text(source_text: str, line_index: int) -> str:
    lines = source_text.splitlines()
    del lines[line_index]
    return "\n".join(lines) + "\n"


def _extract_error_lines(log_text: str) -> list[int]:
    values = []
    for match in ERROR_LINE_RE.finditer(str(log_text or "")):
        try:
            values.append(int(match.group("line")))
        except Exception:
            continue
    return values


def _passes_symptom_root_cause_gate(log_text: str, deleted_line_no: int) -> tuple[bool, list[int]]:
    lines = _extract_error_lines(log_text)
    return any(line != deleted_line_no for line in lines), lines


def _classify_check_failure(log_text: str) -> str:
    text = str(log_text or "").lower()
    match = COUNT_RE.search(text)
    if match:
        try:
            equations = int(match.group("equations"))
            variables = int(match.group("variables"))
            if equations > variables:
                return "constraint_violation"
        except Exception:
            pass
    if any(s in text for s in ("overdetermined", "too many equations", "overconstrained")):
        return "constraint_violation"
    return "model_check_error"


def _admit_candidate(spec: ParameterCandidate) -> dict | None:
    source_text = _read_text(spec.source_spec.source_path)
    mutated_text = _build_mutated_text(source_text, spec.line_index)
    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

    rc, output, check_ok, _sim_ok = _run_model_text(
        model_text=mutated_text,
        source_spec=spec.source_spec,
        stop_time=0.05,
        intervals=10,
    )
    if check_ok:
        return None
    symptom_root_gap, error_lines = _passes_symptom_root_cause_gate(output, spec.line_no)
    if not symptom_root_gap:
        return None
    failure_type = _classify_check_failure(output)
    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "source_file": spec.source_spec.source_file,
        "model_name": spec.model_name,
        "source_model_path": str(spec.source_spec.source_path),
        "mutated_model_path": str(mutated_path),
        "source_library_path": str(spec.source_spec.library_root or ""),
        "source_package_name": spec.source_spec.package_name,
        "source_library_model_path": str(spec.source_spec.source_library_model_path or ""),
        "source_qualified_model_name": spec.source_spec.qualified_model_name,
        "workflow_goal": (
            "Repair the structural parameter deletion so the Modelica model passes "
            "checkModel again while preserving the original model intent."
        ),
        "failure_type": failure_type,
        "expected_stage": "check",
        "mutation_family": "parameter_deletion_reference",
        "mutation_mechanism": "deleted_parameter_declaration",
        "parameter_context": spec.parameter_context,
        "deleted_parameter_name": spec.parameter_name,
        "deleted_parameter_line": spec.line_text.strip(),
        "deleted_parameter_line_no": spec.line_no,
        "deleted_parameter_reference_count": spec.reference_count,
        "source_family": spec.source_spec.source_family,
        "viability_group": spec.source_spec.viability_group,
        "planner_backend": "auto",
        "backend": "openmodelica_docker",
        "admission_source": "omc_parameter_deletion_check_verified",
        "source_check_pass": True,
        "source_simulate_pass": True,
        "mutated_check_pass": False,
        "mutated_failure_excerpt": str(output or "")[:1200],
        "mutated_check_rc": int(rc) if rc is not None else None,
        "symptom_root_cause_gap": True,
        "error_line_numbers": error_lines,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source_viability_rows = []
    cross_domain_viable_specs = []
    for spec in _collect_cross_domain_sources():
        viability = _source_viability(spec)
        row = {
            "source_file": spec.source_file,
            "source_family": spec.source_family,
            "qualified_model_name": spec.qualified_model_name,
            **viability,
        }
        source_viability_rows.append(row)
        if viability["source_viable"]:
            cross_domain_viable_specs.append(spec)

    msl_viable_specs = []
    for spec in _collect_msl_fallback_sources():
        viability = _source_viability(spec)
        row = {
            "source_file": spec.source_file,
            "source_family": spec.source_family,
            "qualified_model_name": spec.qualified_model_name,
            **viability,
        }
        source_viability_rows.append(row)
        if viability["source_viable"]:
            msl_viable_specs.append(spec)

    viable_specs = list(cross_domain_viable_specs)
    if len(cross_domain_viable_specs) <= 1:
        for spec in msl_viable_specs:
            if spec.source_file not in {row.source_file for row in viable_specs}:
                viable_specs.append(spec)

    if cross_domain_viable_specs and len(viable_specs) > len(cross_domain_viable_specs):
        builder_mode = "cross_domain_plus_msl_fallback"
    elif cross_domain_viable_specs:
        builder_mode = "cross_domain"
    else:
        builder_mode = "msl_fallback"

    all_candidates = []
    admitted = []
    by_failure_type: dict[str, int] = {}
    by_context: dict[str, int] = {}
    by_source_family: dict[str, int] = {}

    for spec in viable_specs:
        for candidate in _find_parameter_candidates(spec):
            all_candidates.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "source_file": candidate.source_spec.source_file,
                    "deleted_parameter_name": candidate.parameter_name,
                    "deleted_parameter_line": candidate.line_text.strip(),
                    "deleted_parameter_line_no": candidate.line_no,
                    "deleted_parameter_reference_count": candidate.reference_count,
                    "parameter_context": candidate.parameter_context,
                    "source_family": candidate.source_spec.source_family,
                    "viability_group": candidate.source_spec.viability_group,
                }
            )
            row = _admit_candidate(candidate)
            if row is None:
                continue
            admitted.append(row)
            ftype = str(row["failure_type"])
            by_failure_type[ftype] = by_failure_type.get(ftype, 0) + 1
            ctx = str(row["parameter_context"])
            by_context[ctx] = by_context.get(ctx, 0) + 1
            fam = str(row["source_family"])
            by_source_family[fam] = by_source_family.get(fam, 0) + 1

    (OUT_DIR / "all_candidates.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in all_candidates) + ("\n" if all_candidates else ""),
        encoding="utf-8",
    )
    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in admitted) + ("\n" if admitted else ""),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.19.30",
        "builder_mode": builder_mode,
        "cross_domain_viable_source_count": sum(
            1 for row in source_viability_rows
            if row.get("source_viable") and row.get("source_family") in {"openipsl", "buildings"}
        ),
        "msl_viable_source_count": sum(
            1 for row in source_viability_rows
            if row.get("source_viable") and row.get("source_family") == "msl_electrical"
        ),
        "source_viability_rows": source_viability_rows,
        "candidate_pool_size": len(all_candidates),
        "admitted_case_count": len(admitted),
        "admitted_by_failure_type": by_failure_type,
        "admitted_by_parameter_context": by_context,
        "admitted_by_source_family": by_source_family,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
