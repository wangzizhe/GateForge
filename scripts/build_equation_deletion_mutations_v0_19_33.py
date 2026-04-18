"""Build equation-deletion structural mutations for v0.19.33.

Targets models with explicit differential/algebraic equations (not connect-only).
Primary source: OpenIPSL GENROE (has explicit der() and algebraic equations).

Source viability: checkModel PASS only (simulate not required - OpenIPSL models
require outer SysData which is unavailable standalone).

Mutation: delete one explicit equation from the equation section.

Admission:
  - source checkModel PASS
  - mutant checkModel FAIL
  - failure type: underdetermined/structural (not "not found" / declaration-missing)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)

VERSION = "v0.19.33"
OUT_DIR = REPO_ROOT / "artifacts" / "equation_deletion_mutations_v0_19_33"

STANDALONE_SOURCE_DIR = (
    REPO_ROOT
    / "assets_private"
    / "standalone_explicit_equation_source_models_v0_19_34"
)
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

WITHIN_RE = re.compile(r"^\s*within\s+([^;]+);\s*$", re.MULTILINE)
MODEL_NAME_RE = re.compile(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
NOT_FOUND_RE = re.compile(
    r"(not found|not declared|undeclared|undefined identifier|class\s+\S+\s+not found)",
    re.IGNORECASE,
)
UNDERDETERMINED_RE = re.compile(
    r"(not determined|no equation|singular|underdetermined|"
    r"under.?constrained|fewer equation|variable.*equation)",
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


@dataclass
class EquationStatement:
    start_line_index: int
    end_line_index: int
    text: str
    is_der: bool
    lhs_variable: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_qualified_model_name(model_text: str) -> str:
    within_match = WITHIN_RE.search(model_text)
    model_match = MODEL_NAME_RE.search(model_text)
    if not model_match:
        raise ValueError("model name not found")
    model_name = str(model_match.group(1)).strip()
    within_name = str(within_match.group(1)).strip() if within_match else ""
    return f"{within_name}.{model_name}" if within_name else model_name


def _infer_library_model_path(library_root: Path, qualified_model_name: str) -> Path:
    parts = qualified_model_name.split(".")
    if parts[0] == library_root.name:
        rel_parts = parts[1:]
    else:
        rel_parts = parts
    return library_root.joinpath(*rel_parts[:-1], f"{parts[-1]}.mo")


def _collect_standalone_sources() -> list[SourceSpec]:
    rows = []
    for source_path in sorted(STANDALONE_SOURCE_DIR.glob("*.mo")):
        try:
            text = _read_text(source_path)
            model_name = source_path.stem
            rows.append(
                SourceSpec(
                    source_file=source_path.name,
                    source_path=source_path,
                    library_root=Path(""),
                    package_name="",
                    qualified_model_name=model_name,
                    source_library_model_path=Path(""),
                )
            )
        except Exception:
            continue
    return rows


def _run_check_only(
    *,
    model_text: str,
    spec: SourceSpec,
) -> tuple[int | None, str, bool]:
    model_name = spec.qualified_model_name.rsplit(".", 1)[-1]
    with temporary_workspace("gf_eqdel_v01933_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(spec.source_file),
            primary_model_name=model_name,
            source_library_path=str(spec.library_root),
            source_package_name=spec.package_name,
            source_library_model_path=str(spec.source_library_model_path),
            source_qualified_model_name=spec.qualified_model_name,
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        rc, output, check_ok, _sim_ok = run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=300,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=0.05,
            intervals=5,
            extra_model_loads=[],
        )
        return rc, str(output or ""), bool(check_ok)


def _parse_equation_section(lines: list[str]) -> list[EquationStatement]:
    """Parse explicit equations from the equation section.

    Skips: initial equation section, connect() statements, comment-only lines,
    annotation() blocks.
    """
    results: list[EquationStatement] = []
    in_equation_section = False
    in_initial_equation = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # Detect section boundaries
        if re.match(r"^initial\s+equation\s*$", stripped):
            in_initial_equation = True
            in_equation_section = False
            i += 1
            continue
        if re.match(r"^equation\s*$", stripped):
            in_initial_equation = False
            in_equation_section = True
            i += 1
            continue
        if re.match(r"^(algorithm|initial\s+algorithm|end\s+)", stripped):
            in_equation_section = False
            in_initial_equation = False
            i += 1
            continue

        if not in_equation_section:
            i += 1
            continue

        # Skip blank lines and comments
        if not stripped or stripped.startswith("//"):
            i += 1
            continue

        # Skip connect() statements
        if stripped.startswith("connect("):
            # consume until semicolon
            while i < len(lines) and ";" not in lines[i]:
                i += 1
            i += 1
            continue

        # Skip annotation() blocks
        if stripped.startswith("annotation"):
            depth = stripped.count("(") - stripped.count(")")
            while depth > 0 and i < len(lines):
                i += 1
                if i < len(lines):
                    depth += lines[i].count("(") - lines[i].count(")")
            i += 1
            continue

        # Must contain '=' to be an equation
        if "=" not in stripped:
            i += 1
            continue

        # Accumulate multi-line equation
        start_idx = i
        stmt_lines = [lines[i]]
        while ";" not in lines[i] and i + 1 < len(lines):
            i += 1
            stmt_lines.append(lines[i])
        end_idx = i
        stmt_text = "\n".join(stmt_lines)

        # Extract LHS variable name
        lhs_raw = stmt_text.split("=")[0].strip().lstrip("-").strip()
        is_der = lhs_raw.startswith("der(")
        if is_der:
            lhs_var_match = re.match(r"der\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", lhs_raw)
            lhs_variable = lhs_var_match.group(1) if lhs_var_match else lhs_raw
        else:
            lhs_var_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", lhs_raw)
            lhs_variable = lhs_var_match.group(1) if lhs_var_match else lhs_raw

        results.append(
            EquationStatement(
                start_line_index=start_idx,
                end_line_index=end_idx,
                text=stmt_text.strip(),
                is_der=is_der,
                lhs_variable=lhs_variable,
            )
        )
        i += 1

    return results


def _delete_equation(lines: list[str], eq: EquationStatement) -> str:
    new_lines = (
        lines[: eq.start_line_index] + lines[eq.end_line_index + 1 :]
    )
    return "\n".join(new_lines) + "\n"


def _classify_failure(log_text: str) -> str:
    if UNDERDETERMINED_RE.search(log_text):
        return "underdetermined_structural"
    if NOT_FOUND_RE.search(log_text):
        return "not_found_declaration"
    return "model_check_error_other"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sources = _collect_standalone_sources()
    if not sources:
        print(json.dumps({"error": "no source models found", "version": VERSION}))
        return

    source_viability: list[dict] = []
    viable_sources: list[SourceSpec] = []

    for spec in sources:
        text = _read_text(spec.source_path)
        rc, output, check_ok = _run_check_only(model_text=text, spec=spec)
        row = {
            "source_file": spec.source_file,
            "qualified_model_name": spec.qualified_model_name,
            "source_check_pass": check_ok,
            "rc": int(rc) if rc is not None else None,
            "stderr_snippet": output[-1000:],
        }
        source_viability.append(row)
        print(f"[viability] {spec.source_file}: check={'PASS' if check_ok else 'FAIL'}")
        if check_ok:
            viable_sources.append(spec)

    all_candidates: list[dict] = []
    admitted: list[dict] = []
    by_failure_type: dict[str, int] = {}
    by_equation_type: dict[str, int] = {}
    by_source: dict[str, int] = {}

    for spec in viable_sources:
        source_text = _read_text(spec.source_path)
        lines = source_text.splitlines()
        equations = _parse_equation_section(lines)

        print(
            f"[parse] {spec.source_file}: {len(equations)} explicit equations found"
        )

        for order, eq in enumerate(equations):
            eq_kind = "der" if eq.is_der else "algebraic"
            cid = (
                f"v01933_{spec.source_path.stem}_eqdel_{order + 1:02d}_{eq.lhs_variable.lower()}"
            )
            all_candidates.append(
                {
                    "candidate_id": cid,
                    "source_file": spec.source_file,
                    "equation_text": eq.text,
                    "equation_kind": eq_kind,
                    "lhs_variable": eq.lhs_variable,
                    "start_line_no": eq.start_line_index + 1,
                    "end_line_no": eq.end_line_index + 1,
                }
            )

            mutated_text = _delete_equation(lines, eq)
            mutated_path = OUT_DIR / f"{cid}.mo"
            mutated_path.write_text(mutated_text, encoding="utf-8")

            rc, output, check_ok = _run_check_only(model_text=mutated_text, spec=spec)
            if check_ok:
                print(f"  SKIP {cid}: mutant check passed (no structural failure)")
                continue

            failure_type = _classify_failure(output)
            if failure_type == "not_found_declaration":
                print(f"  SKIP {cid}: failure is declaration-missing, not structural")
                continue

            admitted.append(
                {
                    "candidate_id": cid,
                    "task_id": cid,
                    "source_file": spec.source_file,
                    "model_name": spec.qualified_model_name.rsplit(".", 1)[-1],
                    "source_model_path": str(spec.source_path),
                    "mutated_model_path": str(mutated_path),
                    "source_library_path": str(spec.library_root),
                    "source_package_name": spec.package_name,
                    "source_library_model_path": str(spec.source_library_model_path),
                    "source_qualified_model_name": spec.qualified_model_name,
                    "workflow_goal": (
                        "Repair the Modelica model so it passes checkModel again. "
                        "A single explicit equation has been deleted from the equation "
                        "section. Restore the correct equation to make the model "
                        "structurally well-determined."
                    ),
                    "failure_type": failure_type,
                    "expected_stage": "check",
                    "mutation_family": "equation_deletion",
                    "mutation_mechanism": "deleted_explicit_equation",
                    "equation_kind": eq_kind,
                    "deleted_equation_text": eq.text,
                    "deleted_equation_lhs_variable": eq.lhs_variable,
                    "deleted_equation_start_line": eq.start_line_index + 1,
                    "deleted_equation_end_line": eq.end_line_index + 1,
                    "source_check_pass": True,
                    "mutated_check_pass": False,
                    "mutated_failure_excerpt": output[:1500],
                    "mutated_check_rc": int(rc) if rc is not None else None,
                    "planner_backend": "auto",
                    "backend": "openmodelica_docker",
                    "admission_source": "omc_equation_deletion_check_verified",
                }
            )
            by_failure_type[failure_type] = by_failure_type.get(failure_type, 0) + 1
            by_equation_type[eq_kind] = by_equation_type.get(eq_kind, 0) + 1
            by_source[spec.source_file] = by_source.get(spec.source_file, 0) + 1
            print(f"  ADMIT {cid}: {failure_type} / {eq_kind}")

    (OUT_DIR / "all_candidates.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_candidates)
        + ("\n" if all_candidates else ""),
        encoding="utf-8",
    )
    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in admitted)
        + ("\n" if admitted else ""),
        encoding="utf-8",
    )
    summary = {
        "version": VERSION,
        "source_viability": source_viability,
        "viable_source_count": len(viable_sources),
        "candidate_pool_size": len(all_candidates),
        "admitted_case_count": len(admitted),
        "admitted_by_failure_type": by_failure_type,
        "admitted_by_equation_kind": by_equation_type,
        "admitted_by_source": by_source,
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
