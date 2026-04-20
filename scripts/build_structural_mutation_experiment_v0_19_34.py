"""Build structural mutation experiment cases for v0.19.34.

Three mutation types, all targeting standalone explicit-equation DAE models:

  A: equation_deletion   – delete one explicit equation (from v0.19.33)
  B: parameter_promotion – `parameter Real X = v "desc"` → `Real X "desc"`
  C: phantom_variable    – add `Real X_phantom "desc"` used in one equation
                           but never defined

Types B and C model realistic modeling errors: a time constant promoted to a
free variable (forgot to write the equation that drives it), or a refactored
intermediate variable left without a defining equation.

All admitted mutations produce underdetermined_structural failure.
Each admitted case also carries a pre-computed diagnostic_context field
(from diagnostic_context_v0_19_34) for the Condition B experiment arm.
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
from scripts.diagnostic_context_v0_19_34 import build_diagnostic_context

VERSION = "v0.19.34"
OUT_DIR = REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34"

STANDALONE_SOURCE_DIR = (
    REPO_ROOT
    / "assets_private"
    / "standalone_explicit_equation_source_models_v0_19_34"
)
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

# ── regex ────────────────────────────────────────────────────────────────────

MODEL_NAME_RE = re.compile(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
NOT_FOUND_RE = re.compile(
    r"(not found|not declared|undeclared|undefined identifier|class\s+\S+\s+not found)",
    re.IGNORECASE,
)
UNDERDETERMINED_RE = re.compile(
    r"(not determined|no equation|singular|underdetermined|under.?determined|"
    r"under.?constrained|fewer equation|too few equation|variable.*equation)",
    re.IGNORECASE,
)
# Matches: parameter Real name [units] = value "description" ;
_PARAM_WITH_DESC_RE = re.compile(
    r'^(\s*)parameter\s+Real\s+([A-Za-z_][A-Za-z0-9_]*)([^=\n]*)=[^"\n]+"([^"]+)"\s*;',
)
# Matches: Real name "description" ;   (algebraic — no start=, no parameter)
_ALG_DECL_RE = re.compile(
    r'^\s*Real\s+([A-Za-z_][A-Za-z0-9_]*)\s+"([^"]+)"\s*;'
)


# ── data model ───────────────────────────────────────────────────────────────

@dataclass
class SourceSpec:
    source_file: str
    source_path: Path
    qualified_model_name: str


@dataclass
class EquationStatement:
    start_line_index: int
    end_line_index: int
    text: str
    is_der: bool
    lhs_variable: str


# ── source collection ─────────────────────────────────────────────────────────

def _collect_standalone_sources() -> list[SourceSpec]:
    rows = []
    for p in sorted(STANDALONE_SOURCE_DIR.glob("*.mo")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = MODEL_NAME_RE.search(text)
        if m:
            rows.append(SourceSpec(
                source_file=p.name,
                source_path=p,
                qualified_model_name=m.group(1),
            ))
    return rows


# ── OMC check ─────────────────────────────────────────────────────────────────

def _run_check_only(*, model_text: str, spec: SourceSpec) -> tuple[int | None, str, bool]:
    with temporary_workspace("gf_strexp_v01934_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(spec.source_file),
            primary_model_name=spec.qualified_model_name,
            source_library_path="",
            source_package_name="",
            source_library_model_path="",
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


def _classify_failure(log_text: str) -> str:
    if UNDERDETERMINED_RE.search(log_text):
        return "underdetermined_structural"
    if NOT_FOUND_RE.search(log_text):
        return "not_found_declaration"
    return "model_check_error_other"


# ── equation section parser (shared with v0.19.33) ───────────────────────────

def _parse_equation_section(lines: list[str]) -> list[EquationStatement]:
    results: list[EquationStatement] = []
    in_eq = False
    in_initial = False
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if re.match(r"^initial\s+equation\s*$", s):
            in_initial, in_eq = True, False
            i += 1; continue
        if re.match(r"^equation\s*$", s):
            in_initial, in_eq = False, True
            i += 1; continue
        if re.match(r"^(algorithm|initial\s+algorithm|end\s+)", s):
            in_eq = in_initial = False
            i += 1; continue
        if not in_eq or not s or s.startswith("//"):
            i += 1; continue
        if s.startswith("connect(") or s.startswith("annotation"):
            while i < len(lines) and ";" not in lines[i]:
                i += 1
            i += 1; continue
        if "=" not in s:
            i += 1; continue
        start = i
        parts = [lines[i]]
        while ";" not in lines[i] and i + 1 < len(lines):
            i += 1
            parts.append(lines[i])
        stmt = "\n".join(parts)
        lhs_raw = stmt.split("=")[0].strip().lstrip("-").strip()
        is_der = lhs_raw.startswith("der(")
        if is_der:
            m = re.match(r"der\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", lhs_raw)
            lhs_var = m.group(1) if m else lhs_raw
        else:
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", lhs_raw)
            lhs_var = m.group(1) if m else lhs_raw
        results.append(EquationStatement(
            start_line_index=start,
            end_line_index=i,
            text=stmt.strip(),
            is_der=is_der,
            lhs_variable=lhs_var,
        ))
        i += 1
    return results


# ── mutation generators ───────────────────────────────────────────────────────

def _delete_equation(lines: list[str], eq: EquationStatement) -> str:
    new_lines = lines[: eq.start_line_index] + lines[eq.end_line_index + 1:]
    return "\n".join(new_lines) + "\n"


def _collect_type_a_mutations(
    lines: list[str],
) -> list[tuple[str, str, str]]:
    """Equation deletion.  Returns list of (target_name, kind, mutated_text)."""
    results = []
    for eq in _parse_equation_section(lines):
        kind = "der" if eq.is_der else "algebraic"
        mutated = _delete_equation(lines, eq)
        results.append((eq.lhs_variable, kind, mutated))
    return results


def _collect_type_b_mutations(
    lines: list[str],
) -> list[tuple[str, str, str]]:
    """Parameter promotion.  Returns list of (var_name, description, mutated_text)."""
    results = []
    for i, line in enumerate(lines):
        m = _PARAM_WITH_DESC_RE.match(line)
        if not m:
            continue
        indent = m.group(1)
        var_name = m.group(2)
        # group(3) = optional units/parens between name and =
        units_part = m.group(3).rstrip()
        description = m.group(4)
        new_line = f'{indent}Real {var_name}{units_part}  "{description}";'
        new_lines = lines[:i] + [new_line] + lines[i + 1:]
        results.append((var_name, description, "\n".join(new_lines) + "\n"))
    return results


def _collect_type_c_mutations(
    lines: list[str],
) -> list[tuple[str, str, str]]:
    """Phantom variable.  Returns list of (phantom_name, description, mutated_text)."""
    equations = _parse_equation_section(lines)
    results = []

    for i, line in enumerate(lines):
        m = _ALG_DECL_RE.match(line)
        if not m:
            continue
        var_name, description = m.group(1), m.group(2)
        phantom_name = f"{var_name}_phantom"

        # Find a use-equation (var appears but is not the LHS)
        token_re = re.compile(r"\b" + re.escape(var_name) + r"\b")
        use_eq: EquationStatement | None = None
        for eq in equations:
            if eq.lhs_variable == var_name:
                continue
            if token_re.search(eq.text):
                use_eq = eq
                break
        if use_eq is None:
            continue

        # Build mutated model:
        #   1. Insert phantom declaration after the original declaration
        #   2. Replace var_name with phantom_name in the use-equation lines
        phantom_decl = f'  Real {phantom_name}  "{description}";'
        new_lines = list(lines)

        # Substitute in use-equation lines
        for eq_i in range(use_eq.start_line_index, use_eq.end_line_index + 1):
            new_lines[eq_i] = re.sub(
                r"\b" + re.escape(var_name) + r"\b",
                phantom_name,
                new_lines[eq_i],
            )

        # Insert phantom declaration after original (index shift from insertion)
        new_lines.insert(i + 1, phantom_decl)

        results.append((phantom_name, description, "\n".join(new_lines) + "\n"))
    return results


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sources = _collect_standalone_sources()
    if not sources:
        print(json.dumps({"error": "no standalone source models found"}))
        return

    # Viability pass
    viable: list[SourceSpec] = []
    for spec in sources:
        text = spec.source_path.read_text(encoding="utf-8")
        _, _, ok = _run_check_only(model_text=text, spec=spec)
        print(f"[viability] {spec.source_file}: {'PASS' if ok else 'FAIL'}")
        if ok:
            viable.append(spec)

    admitted: list[dict] = []
    stats: dict[str, int] = {}

    for spec in viable:
        source_text = spec.source_path.read_text(encoding="utf-8")
        lines = source_text.splitlines()

        # Collect all candidates across three types
        candidates: list[tuple[str, str, str, str]] = []  # (type, target, extra, text)
        for var_name, kind, mutated in _collect_type_a_mutations(lines):
            candidates.append(("equation_deletion", var_name, kind, mutated))
        for var_name, desc, mutated in _collect_type_b_mutations(lines):
            candidates.append(("parameter_promotion", var_name, desc, mutated))
        for phantom_name, desc, mutated in _collect_type_c_mutations(lines):
            candidates.append(("phantom_variable", phantom_name, desc, mutated))

        print(f"[candidates] {spec.source_file}: {len(candidates)} mutations")

        for mut_type, target_name, extra, mutated_text in candidates:
            cid = (
                f"v01934_{spec.source_path.stem}"
                f"_{mut_type[:4]}_{target_name.lower()[:20]}"
            )
            # Make IDs unique if there happen to be duplicates
            cid = _unique_id(cid, {r["candidate_id"] for r in admitted})

            mutated_path = OUT_DIR / f"{cid}.mo"
            mutated_path.write_text(mutated_text, encoding="utf-8")

            rc, output, check_ok = _run_check_only(model_text=mutated_text, spec=spec)
            if check_ok:
                print(f"  SKIP {cid}: mutant check passed")
                continue
            failure_type = _classify_failure(output)
            if failure_type != "underdetermined_structural":
                print(f"  SKIP {cid}: failure_type={failure_type}")
                continue

            # Pre-compute diagnostic context for Condition B
            diag_ctx = build_diagnostic_context(mutated_text, output)

            row = {
                "candidate_id": cid,
                "task_id": cid,
                "version": VERSION,
                "source_file": spec.source_file,
                "model_name": spec.qualified_model_name,
                "source_model_path": str(spec.source_path),
                "mutated_model_path": str(mutated_path),
                "mutation_type": mut_type,
                "target_name": target_name,
                "mutation_extra": extra,
                "failure_type": failure_type,
                "mutated_failure_excerpt": output[:2000],
                "diagnostic_context": diag_ctx,
                "workflow_goal": (
                    "Repair the Modelica model so it passes checkModel. "
                    "The model has a structural equation/variable imbalance. "
                    "Identify the missing or incorrect definition and fix it."
                ),
                "expected_stage": "check",
                "planner_backend": "auto",
                "backend": "openmodelica_docker",
            }
            admitted.append(row)
            stats[mut_type] = stats.get(mut_type, 0) + 1
            print(f"  ADMIT {cid}: {mut_type} / {failure_type}")

    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in admitted) + "\n",
        encoding="utf-8",
    )
    summary = {
        "version": VERSION,
        "viable_source_count": len(viable),
        "admitted_count": len(admitted),
        "admitted_by_type": stats,
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def _unique_id(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    for n in range(2, 999):
        candidate = f"{base}_{n}"
        if candidate not in existing:
            return candidate
    return base


if __name__ == "__main__":
    main()
