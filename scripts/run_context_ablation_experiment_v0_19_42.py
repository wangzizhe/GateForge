"""Context ablation experiment for structural underdetermined families (v0.19.42).

Families:
  - parameter_promotion
  - phantom_variable
  - compound_underdetermined

Conditions:
  - A: raw OMC (reused from earlier artifacts)
  - C1: DM root-cause only (new)
  - C2: DM + generic fix hint (new for compound, reused for single-root)
  - C3: DM + per-variable fix hint (reused where available)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "120")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from scripts.diagnostic_context_dm_v0_19_35 import build_dm_diagnostic_context

ADMITTED_V34 = REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34" / "admitted_cases.jsonl"
ADMITTED_V38 = REPO_ROOT / "artifacts" / "compound_underdetermined_experiment_v0_19_38" / "admitted_cases.jsonl"
V35_RESULTS = REPO_ROOT / "artifacts" / "dm_context_experiment_v0_19_35" / "experiment_results.jsonl"
V36_RESULTS = REPO_ROOT / "artifacts" / "dm_context_experiment_v0_19_36" / "experiment_results.jsonl"
V39_RESULTS = REPO_ROOT / "artifacts" / "compound_dm_context_experiment_v0_19_39" / "experiment_results.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "context_ablation_experiment_v0_19_42"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _classify_llm_error(err: str) -> str:
    if not err:
        return ""
    e = err.lower()
    if any(x in e for x in ("503", "502", "service_unavailable", "rate_limited", "timeout", "url_error", "budget_exceeded")):
        return "service_error"
    if any(x in e for x in ("missing_patched_model_text", "no_output", "json")):
        return "format_err"
    return "llm_fail"


def _run_check(model_text: str, model_name: str) -> tuple[bool, str]:
    with temporary_workspace("gf_exp42_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(f"{model_name}.mo"),
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
            timeout_sec=180,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=0.05,
            intervals=5,
            extra_model_loads=[],
        )
        return bool(check_ok), str(output or "")


def _dm_root_only_context(model_text: str) -> str:
    dm = build_dm_diagnostic_context(model_text)
    lines = [ln for ln in dm.splitlines() if ln.strip()]
    roots: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("Root cause variable (no defining equation):"):
            roots = [s.split(":", 1)[1].strip().split()[0]]
            break
        if s.startswith("Root cause variables (no defining equation):"):
            roots = [x.strip() for x in s.split(":", 1)[1].split(",") if x.strip()]
            break
    if not roots:
        return dm
    return "STRUCTURAL DIAGNOSTIC (root-cause only)\n\nRoot cause variables: " + ", ".join(roots)


def _dm_generic_hint_context(model_text: str) -> str:
    dm = build_dm_diagnostic_context(model_text)
    lines = [ln for ln in dm.splitlines() if ln.strip()]
    roots: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("Root cause variable (no defining equation):"):
            roots = [s.split(":", 1)[1].strip().split()[0]]
            break
        if s.startswith("Root cause variables (no defining equation):"):
            roots = [x.strip() for x in s.split(":", 1)[1].split(",") if x.strip()]
            break
    if not roots:
        return dm
    return (
        "STRUCTURAL DIAGNOSTIC (generic fix hint)\n\n"
        f"Root cause variables: {', '.join(roots)}\n"
        "Fix: restore all missing defining equations or declarations for these variables."
    )


def _load_baselines() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    admitted34 = {row["candidate_id"]: row for row in _read_jsonl(ADMITTED_V34)}
    admitted38 = {row["candidate_id"]: row for row in _read_jsonl(ADMITTED_V38)}
    v35 = {row["candidate_id"]: row for row in _read_jsonl(V35_RESULTS)}
    v36 = {row["candidate_id"]: row for row in _read_jsonl(V36_RESULTS)}
    v39 = {row["candidate_id"]: row for row in _read_jsonl(V39_RESULTS)}
    return admitted34, admitted38, v35, v36, v39


def _run_condition(*, model_text: str, model_name: str, failure_type: str, workflow_goal: str, error_excerpt: str, label: str) -> tuple[dict, str | None]:
    patched, err, _ = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=model_text,
        failure_type=failure_type,
        expected_stage="check",
        error_excerpt=error_excerpt,
        repair_actions=["Restore all missing defining equations or declarations required to make the model structurally well-defined."],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=1,
    )
    if err or patched is None:
        err_str = err or "no_output"
        return {
            "condition": label,
            "fix_pass": False,
            "llm_error": err_str,
            "error_class": _classify_llm_error(err_str),
            "omc_output_snippet": "",
        }, None
    check_pass, omc_out = _run_check(patched, model_name)
    return {
        "condition": label,
        "fix_pass": check_pass,
        "llm_error": "",
        "error_class": "",
        "omc_output_snippet": omc_out[:500],
    }, patched


def _family_rows(sample: int | None = None, per_family_sample: int | None = None) -> list[dict]:
    admitted34, admitted38, _, _, _ = _load_baselines()
    rows = []
    for row in admitted34.values():
        if row.get("mutation_type") in {"parameter_promotion", "phantom_variable"}:
            rows.append(row)
    for row in admitted38.values():
        rows.append(row)
    rows.sort(key=lambda r: (str(r.get("mutation_type") or r.get("mutation_family") or ""), str(r["candidate_id"])))
    if per_family_sample is not None:
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            fam = str(row.get("mutation_type") or row.get("mutation_family") or "")
            grouped.setdefault(fam, []).append(row)
        trimmed: list[dict] = []
        for fam in sorted(grouped):
            trimmed.extend(grouped[fam][:per_family_sample])
        return trimmed
    if sample is not None and len(rows) > sample:
        return rows[:sample]
    return rows


def run_experiment(sample: int | None = None, per_family_sample: int | None = None) -> None:
    admitted34, admitted38, v35, v36, v39 = _load_baselines()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    patched_dir = OUT_DIR / "patched_models"
    patched_dir.mkdir(exist_ok=True)

    rows = []
    for idx, case in enumerate(_family_rows(sample, per_family_sample), 1):
        cid = case["candidate_id"]
        family = case.get("mutation_type") or case.get("mutation_family")
        broken_text = Path(case["mutated_model_path"]).read_text(encoding="utf-8")
        model_name = case["model_name"]
        failure_type = case["failure_type"]
        workflow_goal = case["workflow_goal"]
        print(f"[{idx}] {cid} family={family}")

        if family == "parameter_promotion":
            base = v35[cid]
            condition_a = base["condition_a"]
            condition_c2 = base["condition_c"]  # generic hint from v0.19.35
            dm_root = _dm_root_only_context(broken_text)
            condition_c1, patched_c1 = _run_condition(
                model_text=broken_text, model_name=model_name, failure_type=failure_type,
                workflow_goal=workflow_goal, error_excerpt=dm_root[:2000], label="C1_dm_root_only"
            )
            if patched_c1 is not None:
                (patched_dir / f"{cid}_C1.mo").write_text(patched_c1, encoding="utf-8")
            row = {
                "candidate_id": cid,
                "family": family,
                "condition_a": condition_a,
                "condition_c1": condition_c1,
                "condition_c2": condition_c2,
                "condition_c3": condition_c2,
            }
        elif family == "phantom_variable":
            base = v36[cid]
            condition_a = base["condition_a"]
            condition_c2 = base["condition_c"]  # single-root path unchanged
            dm_root = _dm_root_only_context(broken_text)
            condition_c1, patched_c1 = _run_condition(
                model_text=broken_text, model_name=model_name, failure_type=failure_type,
                workflow_goal=workflow_goal, error_excerpt=dm_root[:2000], label="C1_dm_root_only"
            )
            if patched_c1 is not None:
                (patched_dir / f"{cid}_C1.mo").write_text(patched_c1, encoding="utf-8")
            row = {
                "candidate_id": cid,
                "family": family,
                "condition_a": condition_a,
                "condition_c1": condition_c1,
                "condition_c2": condition_c2,
                "condition_c3": condition_c2,
            }
        else:
            base = v39[cid]
            condition_a = base["condition_a"]
            condition_c3 = base["condition_c"]
            dm_root = _dm_root_only_context(broken_text)
            dm_generic = _dm_generic_hint_context(broken_text)
            condition_c1, patched_c1 = _run_condition(
                model_text=broken_text, model_name=model_name, failure_type=failure_type,
                workflow_goal=workflow_goal, error_excerpt=dm_root[:2000], label="C1_dm_root_only"
            )
            condition_c2, patched_c2 = _run_condition(
                model_text=broken_text, model_name=model_name, failure_type=failure_type,
                workflow_goal=workflow_goal, error_excerpt=dm_generic[:2000], label="C2_dm_generic"
            )
            if patched_c1 is not None:
                (patched_dir / f"{cid}_C1.mo").write_text(patched_c1, encoding="utf-8")
            if patched_c2 is not None:
                (patched_dir / f"{cid}_C2.mo").write_text(patched_c2, encoding="utf-8")
            row = {
                "candidate_id": cid,
                "family": family,
                "condition_a": condition_a,
                "condition_c1": condition_c1,
                "condition_c2": condition_c2,
                "condition_c3": condition_c3,
            }
        rows.append(row)

    (OUT_DIR / "experiment_results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )

    summary: dict[str, dict] = {"version": "v0.19.42", "families": {}}
    for family in sorted({r["family"] for r in rows}):
        family_rows = [r for r in rows if r["family"] == family]
        family_summary: dict[str, dict] = {"n_cases": len(family_rows)}
        for condition in ("condition_a", "condition_c1", "condition_c2", "condition_c3"):
            valid = [r[condition] for r in family_rows if r[condition].get("error_class") != "service_error"]
            passed = sum(1 for x in valid if x["fix_pass"])
            family_summary[condition] = {
                "valid_n": len(valid),
                "pass_n": passed,
                "pass_rate": round(passed / len(valid), 3) if valid else 0.0,
            }
        summary["families"][family] = family_summary

    (OUT_DIR / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--per-family-sample", type=int, default=None)
    args = parser.parse_args()
    run_experiment(sample=args.sample, per_family_sample=args.per_family_sample)
