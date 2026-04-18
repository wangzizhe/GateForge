"""Build explicit-equation deletion mutations for v0.19.31.

Goal:
  - move from declaration-missing mutations to equation-balance mutations
  - focus on checkModel-only qualification
  - prefer deeper OpenIPSL models with explicit equations
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


OUT_DIR = REPO_ROOT / "artifacts" / "equation_deletion_mutations_v0_19_31"
OPENIPSL_FIXTURE_DIR = (
    REPO_ROOT
    / "assets_private"
    / "agent_modelica_cross_domain_openipsl_v1_fixture_v1"
    / "source_models"
)
OPENIPSL_LIBRARY_ROOT = (
    REPO_ROOT / "assets_private" / "modelica_sources" / "openipsl" / "OpenIPSL"
)
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

WITHIN_RE = re.compile(r"^\s*within\s+([^;]+);\s*$", re.MULTILINE)
MODEL_RE = re.compile(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
COUNT_RE = re.compile(
    r"(?:Class\s+(?P<class_model>\S+)\s+has|model\s+has)\s+(?P<equations>\d+)\s+"
    r"equation\(s\)\s+and\s+(?P<variables>\d+)\s+variable\(s\)\.",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceSpec:
    source_file: str
    source_path: Path
    library_root: Path
    package_name: str
    qualified_model_name: str
    source_library_model_path: Path


@dataclass(frozen=True)
class EquationCandidate:
    source_spec: SourceSpec
    candidate_id: str
    line_index: int
    line_no: int
    line_text: str
    section: str


@dataclass(frozen=True)
class EquationPairCandidate:
    source_spec: SourceSpec
    candidate_id: str
    first: EquationCandidate
    second: EquationCandidate


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
    rel_parts = parts[1:] if parts and parts[0] == library_root.name else parts
    return library_root.joinpath(*rel_parts[:-1], f"{parts[-1]}.mo")


def _collect_sources() -> list[SourceSpec]:
    rows = []
    for name in ("GENROE_12c13f38c4.mo", "CSVGN1_dc3e8a4ebd.mo"):
        source_path = OPENIPSL_FIXTURE_DIR / name
        if not source_path.exists():
            continue
        text = _read_text(source_path)
        qualified = _extract_qualified_model_name(text)
        rows.append(
            SourceSpec(
                source_file=source_path.name,
                source_path=source_path,
                library_root=OPENIPSL_LIBRARY_ROOT,
                package_name="OpenIPSL",
                qualified_model_name=qualified,
                source_library_model_path=_infer_library_model_path(OPENIPSL_LIBRARY_ROOT, qualified),
            )
        )
    return rows


def _run_model_text(*, model_text: str, source_spec: SourceSpec, stop_time: float = 0.05, intervals: int = 10):
    model_name = source_spec.qualified_model_name.rsplit(".", 1)[-1]
    with temporary_workspace("gf_eqdel_v01931_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(source_spec.source_file),
            primary_model_name=model_name,
            source_library_path=str(source_spec.library_root),
            source_package_name=source_spec.package_name,
            source_library_model_path=str(source_spec.source_library_model_path),
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


def _source_check_viable(source_spec: SourceSpec) -> dict:
    text = _read_text(source_spec.source_path)
    rc, output, check_ok, simulate_ok = _run_model_text(model_text=text, source_spec=source_spec)
    return {
        "source_check_pass": bool(check_ok),
        "source_simulate_pass": bool(simulate_ok),
        "source_viable": bool(check_ok),
        "rc": int(rc) if rc is not None else None,
        "stderr_snippet": str(output or "")[-2000:],
    }


def _lhs_signature(line: str) -> str:
    raw = str(line or "").strip()
    if "=" in raw:
        raw = raw.split("=", 1)[0].strip()
    raw = raw.replace(" ", "")
    raw = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_").lower()
    return raw[:48] or "equation"


def _find_equation_candidates(source_spec: SourceSpec) -> list[EquationCandidate]:
    text = _read_text(source_spec.source_path)
    lines = text.splitlines()
    section = ""
    rows: list[EquationCandidate] = []
    order = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "initial equation":
            section = "initial_equation"
            continue
        if stripped == "equation":
            section = "equation"
            continue
        if stripped in {"algorithm", "initial algorithm", "annotation"}:
            section = ""
        if section not in {"equation", "initial_equation"}:
            continue
        if not stripped or stripped.startswith("connect(") or stripped.startswith("annotation"):
            continue
        if "=" not in stripped or not stripped.endswith(";"):
            continue
        lhs = stripped.split("=", 1)[0].strip()
        if any(token in lhs for token in ("color", "smooth", "points", "origin", "extent", "rotation")):
            continue
        if "Line(" in stripped:
            continue
        if "{" in lhs and not lhs.startswith("["):
            continue
        order += 1
        rows.append(
            EquationCandidate(
                source_spec=source_spec,
                candidate_id=(
                    f"v01931_{source_spec.source_path.stem}_eqdel_{order:02d}_"
                    f"{_lhs_signature(stripped)}"
                ),
                line_index=idx,
                line_no=idx + 1,
                line_text=line.rstrip(),
                section=section,
            )
        )
    return rows


def _is_core_equation(candidate: EquationCandidate) -> bool:
    if candidate.section != "equation":
        return False
    lhs = str(candidate.line_text or "").split("=", 1)[0].strip()
    if candidate.source_spec.source_file == "GENROE_12c13f38c4.mo":
        return lhs in {
            "der(Epq)",
            "der(Epd)",
            "der(PSIkd)",
            "der(PSIkq)",
            "PSId",
            "PSIq",
            "PSIppd",
            "-PSIppq",
            "PSIpp",
        }
    if candidate.source_spec.source_file == "CSVGN1_dc3e8a4ebd.mo":
        return lhs in {
            "[p.ir; p.ii]",
            "[p.vr; p.vi]",
            "vq",
            "vd",
            "-P",
            "-Q",
        }
    return False


def _build_pair_candidates(source_spec: SourceSpec) -> list[EquationPairCandidate]:
    singles = [row for row in _find_equation_candidates(source_spec) if _is_core_equation(row)]
    rows: list[EquationPairCandidate] = []
    order = 0
    for i in range(len(singles)):
        for j in range(i + 1, len(singles)):
            first = singles[i]
            second = singles[j]
            order += 1
            rows.append(
                EquationPairCandidate(
                    source_spec=source_spec,
                    candidate_id=(
                        f"v01931_{source_spec.source_path.stem}_eqpairdel_{order:02d}_"
                        f"{_lhs_signature(first.line_text)}__{_lhs_signature(second.line_text)}"
                    ),
                    first=first,
                    second=second,
                )
            )
    return rows


def _build_mutated_text(source_text: str, line_indexes: list[int]) -> str:
    lines = source_text.splitlines()
    for idx in sorted(line_indexes, reverse=True):
        del lines[idx]
    return "\n".join(lines) + "\n"


def _classify_failure(log_text: str) -> str:
    text = str(log_text or "").lower()
    match = COUNT_RE.search(text)
    if match:
        try:
            equations = int(match.group("equations"))
            variables = int(match.group("variables"))
            if equations < variables:
                return "underdetermined"
            if equations > variables:
                return "overdetermined"
        except Exception:
            pass
    if any(s in text for s in ("not enough equations", "not assigned", "not determined", "not enough initial equations")):
        return "underdetermined"
    if any(s in text for s in ("overdetermined", "too many equations", "overconstrained")):
        return "overdetermined"
    return "model_check_error"


def _admit_candidate(spec: EquationPairCandidate) -> dict | None:
    source_text = _read_text(spec.source_spec.source_path)
    mutated_text = _build_mutated_text(source_text, [spec.first.line_index, spec.second.line_index])
    mutated_path = OUT_DIR / f"{spec.candidate_id}.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")
    rc, output, check_ok, _simulate_ok = _run_model_text(
        model_text=mutated_text,
        source_spec=spec.source_spec,
    )
    if check_ok:
        return None
    imbalance_type = _classify_failure(output)
    return {
        "candidate_id": spec.candidate_id,
        "task_id": spec.candidate_id,
        "source_file": spec.source_spec.source_file,
        "model_name": spec.source_spec.qualified_model_name.rsplit(".", 1)[-1],
        "source_model_path": str(spec.source_spec.source_path),
        "mutated_model_path": str(mutated_path),
        "source_library_path": str(spec.source_spec.library_root),
        "source_package_name": spec.source_spec.package_name,
        "source_library_model_path": str(spec.source_spec.source_library_model_path),
        "source_qualified_model_name": spec.source_spec.qualified_model_name,
        "workflow_goal": (
            "Repair the explicit equation-pair deletion so the Modelica model passes "
            "checkModel again while preserving the original model equations."
        ),
        "failure_type": "model_check_error",
        "expected_stage": "check",
        "validation_mode": "check_only",
        "mutation_family": "equation_pair_deletion_reference",
        "mutation_mechanism": "deleted_explicit_equation_pair",
        "deleted_equation_lines": [spec.first.line_text.strip(), spec.second.line_text.strip()],
        "deleted_equation_line_nos": [spec.first.line_no, spec.second.line_no],
        "deleted_equation_section": spec.first.section,
        "imbalance_type": imbalance_type,
        "planner_backend": "auto",
        "backend": "openmodelica_docker",
        "admission_source": "omc_equation_deletion_check_verified",
        "source_check_pass": True,
        "source_simulate_pass": False,
        "mutated_check_pass": False,
        "mutated_check_rc": int(rc) if rc is not None else None,
        "mutated_failure_excerpt": str(output or "")[:1200],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_viability_rows = []
    viable_specs = []
    for spec in _collect_sources():
        viability = _source_check_viable(spec)
        source_viability_rows.append(
            {
                "source_file": spec.source_file,
                "qualified_model_name": spec.qualified_model_name,
                **viability,
            }
        )
        if viability["source_viable"]:
            viable_specs.append(spec)

    all_candidates = []
    admitted = []
    by_imbalance_type: dict[str, int] = {}
    by_section: dict[str, int] = {}
    for spec in viable_specs:
        for candidate in _build_pair_candidates(spec):
            all_candidates.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "source_file": candidate.source_spec.source_file,
                    "deleted_equation_lines": [
                        candidate.first.line_text.strip(),
                        candidate.second.line_text.strip(),
                    ],
                    "deleted_equation_line_nos": [candidate.first.line_no, candidate.second.line_no],
                    "deleted_equation_section": candidate.first.section,
                }
            )
            row = _admit_candidate(candidate)
            if row is None:
                continue
            admitted.append(row)
            itype = str(row["imbalance_type"])
            by_imbalance_type[itype] = by_imbalance_type.get(itype, 0) + 1
            sec = str(row["deleted_equation_section"])
            by_section[sec] = by_section.get(sec, 0) + 1

    (OUT_DIR / "all_candidates.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in all_candidates) + ("\n" if all_candidates else ""),
        encoding="utf-8",
    )
    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in admitted) + ("\n" if admitted else ""),
        encoding="utf-8",
    )
    summary = {
        "version": "v0.19.31",
        "candidate_pool_size": len(all_candidates),
        "admitted_case_count": len(admitted),
        "admitted_by_imbalance_type": by_imbalance_type,
        "admitted_by_section": by_section,
        "source_viability_rows": source_viability_rows,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
