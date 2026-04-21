"""Build overdetermined structural mutation cases for v0.19.41.

Redesigned from v0.19.40:
  - No comment on extra equation (removes trivial hint to LLM)
  - Extra equation uses LARGE_VALUE = 1.0e10 so that wrong removal
    (keeping extra equation, discarding original) → simulate FAIL
  - Four-gate admission:
    1. Source: checkModel + simulate PASS
    2. Mutated: checkModel FAIL (overdetermined)
    3. Wrong removal (keep extra, remove original): simulate FAIL
    4. Correct removal = source model: PASS (already gate 1)

Only variables whose extra equation propagates to a der() call
will reliably pass gate 3; variables that are terminal outputs
(not used in any derivative) are filtered out naturally.
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

VERSION = "v0.19.41"
LARGE_VALUE = "sqrt(-1.0)"
OUT_DIR = REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_41"
STANDALONE_SOURCE_DIR = (
    REPO_ROOT / "assets_private"
    / "standalone_explicit_equation_source_models_v0_19_34"
)
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

MODEL_NAME_RE = re.compile(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
EQ_VAR_COUNT_RE = re.compile(
    r"has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)"
)
_ALG_DECL_RE = re.compile(
    r'^\s*Real\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*\([^)]*\))?'
    r'(?:\s*=[^;"]*)?(?:\s*"[^"]*")?\s*;'
)


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


def _parse_equation_section(lines: list[str]) -> list[EquationStatement]:
    results = []
    in_eq = False
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if re.match(r"^initial\s+equation\s*$", s):
            in_eq = False; i += 1; continue
        if re.match(r"^equation\s*$", s):
            in_eq = True; i += 1; continue
        if re.match(r"^(algorithm|initial\s+algorithm|end\s+)", s):
            in_eq = False; i += 1; continue
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
            i += 1; parts.append(lines[i])
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


def _collect_mutations(
    lines: list[str],
    equations: list[EquationStatement],
) -> list[tuple[str, str, str, int, int]]:
    """Return (var_name, mutated_text, wrong_removal_text, orig_start, orig_end).

    mutated_text: source with extra equation appended (overdetermined).
    wrong_removal_text: mutated model with original equation removed (keeps extra).
    orig_start/orig_end: line indices of the original equation in source/mutated.
    """
    alg_vars: set[str] = set()
    for line in lines:
        m = _ALG_DECL_RE.match(line)
        if not m:
            continue
        if "start" in line:
            continue
        alg_vars.add(m.group(1))

    defined_alg = {
        eq.lhs_variable: eq
        for eq in equations
        if not eq.text.strip().startswith("der(") and eq.lhs_variable in alg_vars
    }

    end_eq_idx = max((eq.end_line_index for eq in equations), default=None)
    if end_eq_idx is None:
        return []

    results = []
    for var in sorted(defined_alg):
        orig_eq = defined_alg[var]
        extra_eq_line = f"  {var} = {LARGE_VALUE};"
        mutated = list(lines)
        mutated.insert(end_eq_idx + 1, extra_eq_line)
        mutated_text = "\n".join(mutated) + "\n"

        # Wrong removal: remove original equation from mutated model.
        # Original equation occupies orig_eq.start_line_index..orig_eq.end_line_index
        # in both source and mutated (extra was inserted AFTER end_eq_idx >= end_line_index).
        wrong = [
            line for i, line in enumerate(mutated)
            if i < orig_eq.start_line_index or i > orig_eq.end_line_index
        ]
        wrong_text = "\n".join(wrong) + "\n"

        results.append((var, mutated_text, wrong_text,
                        orig_eq.start_line_index, orig_eq.end_line_index))
    return results


def _run_check_and_sim(model_text: str, spec: SourceSpec) -> tuple[bool, bool, str]:
    """Return (check_ok, sim_ok, output)."""
    with temporary_workspace("gf_overdet41_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(spec.source_file),
            primary_model_name=spec.model_name,
            source_library_path="", source_package_name="",
            source_library_model_path="", source_qualified_model_name=spec.model_name,
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        _, output, check_ok, sim_ok = run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=300,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=0.05, intervals=5, extra_model_loads=[],
        )
        return bool(check_ok), bool(sim_ok), str(output or "")


def _is_overdetermined(output: str) -> bool:
    m = EQ_VAR_COUNT_RE.search(output)
    if m:
        return int(m.group(1)) > int(m.group(2))
    return False


def _collect_sources() -> list[SourceSpec]:
    rows = []
    for p in sorted(STANDALONE_SOURCE_DIR.glob("*.mo")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = MODEL_NAME_RE.search(text)
        if m:
            rows.append(SourceSpec(
                source_file=p.name, source_path=p, model_name=m.group(1)
            ))
    return rows


def _unique_id(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    for n in range(2, 999):
        c = f"{base}_{n}"
        if c not in existing:
            return c
    return base


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = _collect_sources()
    admitted: list[dict] = []
    admitted_ids: set[str] = set()

    for spec in sources:
        source_text = spec.source_path.read_text(encoding="utf-8")

        # Gate 1: source passes check + simulate
        check_ok, sim_ok, _ = _run_check_and_sim(source_text, spec)
        if not check_ok or not sim_ok:
            print(f"[gate1 FAIL] {spec.source_file}")
            continue
        print(f"[gate1 PASS] {spec.source_file}")

        lines = source_text.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        print(f"  candidates: {len(mutations)}")

        for var_name, mutated_text, wrong_text, orig_start, orig_end in mutations:
            # Gate 2: mutated fails checkModel (overdetermined)
            check_mut, _, output_mut = _run_check_and_sim(mutated_text, spec)
            if check_mut:
                print(f"  SKIP {var_name}: gate2 — mutant unexpectedly passed check")
                continue
            if not _is_overdetermined(output_mut):
                print(f"  SKIP {var_name}: gate2 — not overdetermined")
                continue

            # Gate 3: wrong removal fails simulate (check passes, sim fails)
            check_wr, sim_wr, _ = _run_check_and_sim(wrong_text, spec)
            if not check_wr:
                print(f"  SKIP {var_name}: gate3 — wrong removal failed check (unexpected)")
                continue
            if sim_wr:
                print(f"  SKIP {var_name}: gate3 — wrong removal passed simulate (ambiguous)")
                continue

            cid = _unique_id(
                f"v01941_{spec.source_path.stem}_extra_{var_name.lower()[:20]}",
                admitted_ids,
            )
            admitted_ids.add(cid)
            mutated_path = OUT_DIR / f"{cid}.mo"
            mutated_path.write_text(mutated_text, encoding="utf-8")

            row = {
                "candidate_id": cid,
                "task_id": cid,
                "version": VERSION,
                "source_file": spec.source_file,
                "model_name": spec.model_name,
                "source_model_path": str(spec.source_path),
                "mutated_model_path": str(mutated_path),
                "mutation_type": "extra_equation_large_value",
                "target_variable": var_name,
                "extra_equation_value": LARGE_VALUE,
                "failure_type": "overdetermined_structural",
                "mutated_failure_excerpt": output_mut[:2000],
                "workflow_goal": (
                    "Repair the Modelica model so it passes both checkModel and simulate. "
                    "The model has a structural equation/variable imbalance: "
                    "there are more equations than variables. "
                    "Identify and remove the redundant or conflicting equation. "
                    "Note: removing the wrong equation will cause the simulation to fail."
                ),
                "expected_stage": "check",
                "planner_backend": "auto",
                "backend": "openmodelica_docker",
            }
            admitted.append(row)
            print(f"  ADMIT {cid}: extra eq for {var_name}")

    (OUT_DIR / "admitted_cases.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in admitted) + "\n",
        encoding="utf-8",
    )
    summary = {
        "version": VERSION,
        "mutation_type": "extra_equation_large_value",
        "extra_equation_value": LARGE_VALUE,
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
