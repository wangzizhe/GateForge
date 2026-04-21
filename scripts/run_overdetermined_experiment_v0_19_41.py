"""Run overdetermined experiment v0.19.41.

Condition A: raw OMC error ("N+1 eq, N var" — no variable named).
Condition B: overdetermined diagnostic context (names conflicting variable
             and both equations, labels the redundant one).

Evaluation is valid within OMC scope: wrong removal → simulate FAIL.
LLM must identify which of the two equations is the extra one.

Usage:
  python3 scripts/run_overdetermined_experiment_v0_19_41.py [--sample N]
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

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "100")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from scripts.diagnostic_context_overdetermined_v0_19_40 import (
    build_overdetermined_diagnostic_context,
)

ADMITTED_PATH = REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_41" / "admitted_cases.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "overdetermined_experiment_v0_19_41"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"


def _classify_llm_error(err: str) -> str:
    if not err:
        return ""
    e = err.lower()
    if any(x in e for x in ("503", "502", "service_unavailable", "rate_limited",
                             "timeout", "url_error", "budget_exceeded")):
        return "service_error"
    return "llm_fail"


def _run_check_and_sim(model_text: str, model_name: str) -> tuple[bool, bool, str]:
    """Return (check_ok, sim_ok, output)."""
    with temporary_workspace("gf_exp41_") as ws:
        workspace = Path(ws)
        layout = prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=Path(f"{model_name}.mo"),
            primary_model_name=model_name,
            source_library_path="", source_package_name="",
            source_library_model_path="", source_qualified_model_name=model_name,
        )
        layout.model_write_path.write_text(model_text, encoding="utf-8")
        _, output, check_ok, sim_ok = run_check_and_simulate(
            workspace=workspace,
            model_load_files=list(layout.model_load_files),
            model_name=layout.model_identifier,
            timeout_sec=180,
            backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            stop_time=0.05, intervals=5, extra_model_loads=[],
        )
        return bool(check_ok), bool(sim_ok), str(output or "")


def _run_condition(
    *,
    broken_text: str,
    model_name: str,
    workflow_goal: str,
    error_excerpt: str,
    condition_label: str,
) -> tuple[dict, str | None]:
    patched, err, _ = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=broken_text,
        failure_type="overdetermined_structural",
        expected_stage="check",
        error_excerpt=error_excerpt,
        repair_actions=["Remove the redundant or conflicting equation."],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=1,
    )
    if err or patched is None:
        err_str = err or "no_output"
        return {
            "condition": condition_label,
            "fix_pass": False,
            "llm_error": err_str,
            "error_class": _classify_llm_error(err_str),
            "check_ok": False,
            "sim_ok": False,
            "omc_output_snippet": "",
        }, None

    check_ok, sim_ok, omc_out = _run_check_and_sim(patched, model_name)
    return {
        "condition": condition_label,
        "fix_pass": check_ok and sim_ok,
        "llm_error": "",
        "error_class": "",
        "check_ok": check_ok,
        "sim_ok": sim_ok,
        "omc_output_snippet": omc_out[:500],
    }, patched


def run_experiment(sample: int | None = None) -> None:
    if not ADMITTED_PATH.exists():
        print(f"ERROR: admitted cases not found at {ADMITTED_PATH}")
        sys.exit(1)

    cases = [json.loads(l) for l in ADMITTED_PATH.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(cases)} overdetermined cases.")

    if sample and len(cases) > sample:
        import random; random.seed(42)
        cases = random.sample(cases, sample)
        print(f"Sampled {sample} cases.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    patched_dir = OUT_DIR / "patched_models"
    patched_dir.mkdir(exist_ok=True)

    results: list[dict] = []

    for idx, case in enumerate(cases):
        cid = case["candidate_id"]
        broken_path = Path(case["mutated_model_path"])
        if not broken_path.exists():
            print(f"  SKIP {cid}: file not found")
            continue

        broken_text = broken_path.read_text(encoding="utf-8")
        model_name = case["model_name"]
        raw_error = case["mutated_failure_excerpt"]
        workflow_goal = case["workflow_goal"]
        diag_ctx = build_overdetermined_diagnostic_context(broken_text)

        print(f"[{idx + 1}/{len(cases)}] {cid}  (target={case.get('target_variable', '?')})")

        result_a, patched_a = _run_condition(
            broken_text=broken_text, model_name=model_name,
            workflow_goal=workflow_goal,
            error_excerpt=raw_error[:1500], condition_label="A_raw_error",
        )
        result_b, patched_b = _run_condition(
            broken_text=broken_text, model_name=model_name,
            workflow_goal=workflow_goal,
            error_excerpt=diag_ctx[:2000], condition_label="B_overdet_diag",
        )

        if patched_a is not None:
            (patched_dir / f"{cid}_A.mo").write_text(patched_a, encoding="utf-8")
        if patched_b is not None:
            (patched_dir / f"{cid}_B.mo").write_text(patched_b, encoding="utf-8")

        row = {
            "candidate_id": cid,
            "source_file": case.get("source_file", ""),
            "target_variable": case.get("target_variable", ""),
            "extra_equation_value": case.get("extra_equation_value", ""),
            "condition_a": result_a,
            "condition_b": result_b,
        }
        results.append(row)
        a_label = "PASS" if result_a["fix_pass"] else (
            "CHECK_FAIL" if not result_a.get("check_ok") else "SIM_FAIL"
        )
        b_label = "PASS" if result_b["fix_pass"] else (
            "CHECK_FAIL" if not result_b.get("check_ok") else "SIM_FAIL"
        )
        print(f"  A={a_label}  B={b_label}")

    (OUT_DIR / "experiment_results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )

    n = len(results)
    a_valid = [r for r in results if r["condition_a"].get("error_class") != "service_error"]
    b_valid = [r for r in results if r["condition_b"].get("error_class") != "service_error"]
    a_pass_n = sum(1 for r in a_valid if r["condition_a"]["fix_pass"])
    b_pass_n = sum(1 for r in b_valid if r["condition_b"]["fix_pass"])
    a_rate = round(a_pass_n / len(a_valid), 3) if a_valid else 0.0
    b_rate = round(b_pass_n / len(b_valid), 3) if b_valid else 0.0

    both_valid = [
        r for r in results
        if r["condition_a"].get("error_class") != "service_error"
        and r["condition_b"].get("error_class") != "service_error"
    ]
    summary = {
        "total_cases": n,
        "mutation_type": "extra_equation_large_value",
        "condition_a_fix_rate": a_rate,
        "condition_b_fix_rate": b_rate,
        "delta_b_minus_a": round(b_rate - a_rate, 3),
        "matched_pair": {
            "both_valid_n": len(both_valid),
            "a_pass_b_fail": sum(1 for r in both_valid if r["condition_a"]["fix_pass"] and not r["condition_b"]["fix_pass"]),
            "a_fail_b_pass": sum(1 for r in both_valid if not r["condition_a"]["fix_pass"] and r["condition_b"]["fix_pass"]),
        },
    }
    (OUT_DIR / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n=== EXPERIMENT SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None)
    args = parser.parse_args()
    run_experiment(sample=args.sample)
