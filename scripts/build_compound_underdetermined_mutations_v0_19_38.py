"""Build compound underdetermined mutation cases for v0.19.38.

Compound mutation: apply parameter_promotion AND phantom_variable simultaneously
to the same source model.  The resulting model has TWO structural deficits:

  1. A promoted parameter (no defining equation for the free variable)
  2. A phantom variable (extra declaration with no defining equation)

The LLM must identify and fix BOTH issues in a single turn or across multiple
turns.  This is strictly harder than either individual mutation:
  - Two root causes to localize
  - Two different fix strategies (restore parameter value vs delete phantom decl)

Sampling strategy: at most MAX_PER_SOURCE compound cases per source model,
produced by pairing the first PP candidates with the first PV candidates.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from scripts.diagnostic_context_dm_v0_19_35 import build_dm_diagnostic_context

VERSION = "v0.19.38"
OUT_DIR = REPO_ROOT / "artifacts" / "compound_underdetermined_experiment_v0_19_38"
STANDALONE_SOURCE_DIR = (
    REPO_ROOT
    / "assets_private"
    / "standalone_explicit_equation_source_models_v0_19_34"
)
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
MAX_PER_SOURCE = 5

# ── regex (same as v0.19.34) ─────────────────────────────────────────────────

MODEL_NAME_RE = re.compile(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
UNDERDETERMINED_RE = re.compile(
    r"(not determined|no equation|singular|underdetermined|under.?determined|"
    r"under.?constrained|fewer equation|too few equation|variable.*equation)",
    re.IGNORECASE,
)
_PARAM_WITH_DESC_RE = re.compile(
    r'^(\s*)parameter\s+Real\s+([A-Za-z_][A-Za-z0-9_]*)([^=\n]*)=[^"\n]+"([^"]+)"\s*;',
)
_ALG_DECL_RE = re.compile(
    r'^\s*Real\s+([A-Za-z_][A-Za-z0-9_]*)\s+"([^"]+)"\s*;'
)


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class SourceSpec:
    source_file: str
    source_path: Path
    model_name: str


@dataclass
class EquationStatement:
    start_line_index: int
    end_line_index: int
    text: str
    lhs_variable: str


@dataclass
class PPSpec:
    line_idx: int
    var_name: str
    description: str
    new_line: str


@dataclass
class PVSpec:
    decl_line_idx: int
    var_name: str
    phantom_name: str
    description: str
    use_eq: EquationStatement


# ── equation parser (copied from v0.19.34) ───────────────────────────────────

def _parse_equation_section(lines: list[str]) -> list[EquationStatement]:
    results: list[EquationStatement] = []
    in_eq = False
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if re.match(r"^initial\s+equation\s*$", s):
            in_eq = False
            i += 1; continue
        if re.match(r"^equation\s*$", s):
            in_eq = True
            i += 1; continue
        if re.match(r"^(algorithm|initial\s+algorithm|end\s+)", s):
            in_eq = False
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
            lhs_variable=lhs_var,
        ))
        i += 1
    return results


# ── mutation spec collectors ──────────────────────────────────────────────────

def _collect_pp_specs(lines: list[str]) -> list[PPSpec]:
    specs = []
    for i, line in enumerate(lines):
        m = _PARAM_WITH_DESC_RE.match(line)
        if not m:
            continue
        indent, var_name, units_part, desc = m.group(1), m.group(2), m.group(3).rstrip(), m.group(4)
        new_line = f'{indent}Real {var_name}{units_part}  "{desc}";'
        specs.append(PPSpec(line_idx=i, var_name=var_name, description=desc, new_line=new_line))
    return specs


def _collect_pv_specs(lines: list[str], equations: list[EquationStatement]) -> list[PVSpec]:
    specs = []
    for i, line in enumerate(lines):
        m = _ALG_DECL_RE.match(line)
        if not m:
            continue
        var_name, desc = m.group(1), m.group(2)
        phantom_name = f"{var_name}_phantom"
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
        specs.append(PVSpec(
            decl_line_idx=i,
            var_name=var_name,
            phantom_name=phantom_name,
            description=desc,
            use_eq=use_eq,
        ))
    return specs


# ── compound mutation applicator ─────────────────────────────────────────────

def _apply_compound(
    source_lines: list[str],
    pp: PPSpec,
    pv: PVSpec,
) -> str:
    """Apply PP and PV mutations on source_lines; return compound mutated text.

    PP replaces one line (no count change), so PV indices from source scan
    remain valid.  PV inserts one phantom declaration line.
    """
    new_lines = list(source_lines)

    # Apply PP: replace parameter declaration line
    new_lines[pp.line_idx] = pp.new_line

    # Apply PV: substitute pv.var_name with phantom in use_eq range
    token_re = re.compile(r"\b" + re.escape(pv.var_name) + r"\b")
    for eq_i in range(pv.use_eq.start_line_index, pv.use_eq.end_line_index + 1):
        new_lines[eq_i] = token_re.sub(pv.phantom_name, new_lines[eq_i])

    # Insert phantom declaration after original variable declaration
    phantom_decl = f'  Real {pv.phantom_name}  "{pv.description}";'
    new_lines.insert(pv.decl_line_idx + 1, phantom_decl)

    return "\n".join(new_lines) + "\n"


# ── OMC check ─────────────────────────────────────────────────────────────────

def _run_check(model_text: str, model_name: str, source_file: str) -> tuple[bool, str]:
    with temporary_workspace("gf_comp38_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(source_file),
            primary_model_name=model_name,
            source_library_path="",
            source_package_name="",
            source_library_model_path="",
            source_qualified_model_name=model_name,
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        _, output, check_ok, _ = run_check_and_simulate(
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
        return bool(check_ok), str(output or "")


# ── main ──────────────────────────────────────────────────────────────────────

def _collect_sources() -> list[SourceSpec]:
    rows = []
    for p in sorted(STANDALONE_SOURCE_DIR.glob("*.mo")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = MODEL_NAME_RE.search(text)
        if m:
            rows.append(SourceSpec(source_file=p.name, source_path=p, model_name=m.group(1)))
    return rows


def _unique_id(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    for n in range(2, 999):
        candidate = f"{base}_{n}"
        if candidate not in existing:
            return candidate
    return base


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sources = _collect_sources()
    admitted: list[dict] = []
    admitted_ids: set[str] = set()

    for spec in sources:
        source_text = spec.source_path.read_text(encoding="utf-8")

        # Viability check
        ok, _ = _run_check(source_text, spec.model_name, spec.source_file)
        if not ok:
            print(f"[viability FAIL] {spec.source_file}")
            continue
        print(f"[viability PASS] {spec.source_file}")

        lines = source_text.splitlines()
        equations = _parse_equation_section(lines)
        pp_specs = _collect_pp_specs(lines)
        pv_specs = _collect_pv_specs(lines, equations)

        print(f"  PP candidates: {len(pp_specs)}, PV candidates: {len(pv_specs)}")

        count_this_source = 0
        for pp, pv in product(pp_specs, pv_specs):
            if count_this_source >= MAX_PER_SOURCE:
                break
            # Avoid PP-promoting the same variable that PV targets
            if pp.var_name == pv.var_name:
                continue

            compound_text = _apply_compound(lines, pp, pv)

            check_ok, output = _run_check(compound_text, spec.model_name, spec.source_file)
            if check_ok:
                continue
            if not UNDERDETERMINED_RE.search(output):
                continue

            cid = _unique_id(
                f"v01938_{spec.source_path.stem}_pp_{pp.var_name.lower()[:12]}_pv_{pv.var_name.lower()[:12]}",
                admitted_ids,
            )
            admitted_ids.add(cid)

            mutated_path = OUT_DIR / f"{cid}.mo"
            mutated_path.write_text(compound_text, encoding="utf-8")

            dm_ctx = build_dm_diagnostic_context(compound_text)

            row = {
                "candidate_id": cid,
                "task_id": cid,
                "version": VERSION,
                "source_file": spec.source_file,
                "model_name": spec.model_name,
                "source_model_path": str(spec.source_path),
                "mutated_model_path": str(mutated_path),
                "mutation_type": "compound_underdetermined",
                "pp_target": pp.var_name,
                "pp_description": pp.description,
                "pv_target": pv.phantom_name,
                "pv_base_var": pv.var_name,
                "pv_description": pv.description,
                "failure_type": "underdetermined_structural",
                "mutated_failure_excerpt": output[:2000],
                "dm_diagnostic_context": dm_ctx,
                "workflow_goal": (
                    "Repair the Modelica model so it passes checkModel. "
                    "The model has a structural equation/variable imbalance. "
                    "Identify all missing or incorrect definitions and fix them."
                ),
                "expected_stage": "check",
                "planner_backend": "auto",
                "backend": "openmodelica_docker",
            }
            admitted.append(row)
            count_this_source += 1
            print(f"  ADMIT {cid}: PP={pp.var_name}, PV={pv.phantom_name}")

        print(f"  Admitted {count_this_source} compound cases from {spec.source_file}")

    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in admitted) + "\n",
        encoding="utf-8",
    )
    summary = {
        "version": VERSION,
        "mutation_type": "compound_underdetermined",
        "admitted_count": len(admitted),
        "by_source": {
            spec.source_path.stem: sum(1 for r in admitted if r["source_file"] == spec.source_file)
            for spec in sources
        },
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n=== BUILD SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
