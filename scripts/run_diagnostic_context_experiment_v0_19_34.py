"""Run the Condition A vs Condition B diagnostic context experiment (v0.19.34).

Loads admitted cases from the builder, then for a sample of cases runs:

  Condition A: LLM sees raw OMC error message
  Condition B: LLM sees structured diagnostic context (variable label + equations)

Both conditions use a single repair turn (max_turns=1).
Fix quality is measured by OMC checkModel on the LLM-proposed output.

Usage:
  python3 scripts/run_diagnostic_context_experiment_v0_19_34.py [--sample N]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Each case makes 2 LLM calls (condition A + B); allow up to 200 cases
os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "400")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)

ADMITTED_PATH = (
    REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34" / "admitted_cases.jsonl"
)
OUT_DIR = REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"

# ── 错误分类 ──────────────────────────────────────────────────────────────────

def _classify_llm_error(err: str) -> str:
    """区分服务器错误和 LLM 逻辑失败。

    返回值:
      "service_error"  — 503 / 502 / 429 / timeout / network（服务不可用，非 LLM 能力问题）
      "llm_fail"       — LLM 返回了响应但格式错误或内容不可用
    """
    if not err:
        return ""
    e = err.lower()
    if any(x in e for x in ("503", "502", "service_unavailable", "rate_limited",
                             "timeout", "url_error", "budget_exceeded")):
        return "service_error"
    return "llm_fail"


def _run_check(model_text: str, model_name: str) -> tuple[bool, str]:
    """Run OMC checkModel; return (pass, output)."""
    with temporary_workspace("gf_exp34_") as ws:
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


def _run_condition(
    *,
    broken_text: str,
    model_name: str,
    failure_type: str,
    workflow_goal: str,
    error_excerpt: str,
    condition_label: str,
) -> dict:
    """Run one LLM repair attempt; return result dict."""
    patched, err, provider = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=broken_text,
        failure_type=failure_type,
        expected_stage="check",
        error_excerpt=error_excerpt,
        repair_actions=["Restore or add the missing defining equation or declaration."],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=1,
    )
    if err or patched is None:
        err_str = err or "no_output"
        err_class = _classify_llm_error(err_str)
        return {
            "condition": condition_label,
            "fix_pass": False,
            "llm_error": err_str,
            "error_class": err_class,  # "service_error" | "llm_fail"
        }

    check_pass, omc_out = _run_check(patched, model_name)
    return {
        "condition": condition_label,
        "fix_pass": check_pass,
        "llm_error": "",
        "error_class": "",
        "omc_output_snippet": omc_out[:500],
    }


def run_experiment(sample: int = 20) -> None:
    if not ADMITTED_PATH.exists():
        print(f"ERROR: admitted cases not found at {ADMITTED_PATH}")
        print("Run build_structural_mutation_experiment_v0_19_34.py first.")
        sys.exit(1)

    cases = [json.loads(l) for l in ADMITTED_PATH.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(cases)} admitted cases.")

    if len(cases) > sample:
        random.seed(42)
        cases = random.sample(cases, sample)
        print(f"Sampled {sample} cases for experiment.")

    results: list[dict] = []
    for idx, case in enumerate(cases):
        cid = case["candidate_id"]
        mut_type = case.get("mutation_type", "unknown")
        broken_path = Path(case["mutated_model_path"])
        if not broken_path.exists():
            print(f"  SKIP {cid}: mutated file not found")
            continue

        broken_text = broken_path.read_text(encoding="utf-8")
        model_name = case["model_name"]
        failure_type = case["failure_type"]
        raw_error = case["mutated_failure_excerpt"]
        diag_ctx = case["diagnostic_context"]
        base_goal = case["workflow_goal"]

        print(f"[{idx+1}/{len(cases)}] {cid} ({mut_type})")

        # Condition A: raw OMC error only
        result_a = _run_condition(
            broken_text=broken_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=base_goal,
            error_excerpt=raw_error[:1500],
            condition_label="A_raw_error",
        )

        # Condition B: diagnostic context replaces raw error in error_excerpt.
        # workflow_goal stays clean to avoid breaking LLM JSON output format.
        result_b = _run_condition(
            broken_text=broken_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=base_goal,
            error_excerpt=diag_ctx[:2000],
            condition_label="B_diagnostic",
        )

        row = {
            "candidate_id": cid,
            "mutation_type": mut_type,
            "source_file": case.get("source_file", ""),
            "target_name": case.get("target_name", ""),
            "condition_a": result_a,
            "condition_b": result_b,
        }
        results.append(row)
        a_pass = "PASS" if result_a["fix_pass"] else "FAIL"
        b_pass = "PASS" if result_b["fix_pass"] else "FAIL"
        print(f"  A={a_pass}  B={b_pass}")

    # Write results
    results_path = OUT_DIR / "experiment_results.jsonl"
    results_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )

    # Summary — service_error 不计入修复率分母
    n = len(results)
    a_service = sum(1 for r in results if r["condition_a"].get("error_class") == "service_error")
    b_service = sum(1 for r in results if r["condition_b"].get("error_class") == "service_error")
    a_valid = [r for r in results if r["condition_a"].get("error_class") != "service_error"]
    b_valid = [r for r in results if r["condition_b"].get("error_class") != "service_error"]
    a_pass = sum(1 for r in a_valid if r["condition_a"]["fix_pass"])
    b_pass = sum(1 for r in b_valid if r["condition_b"]["fix_pass"])

    by_type: dict[str, dict] = {}
    for r in results:
        t = r["mutation_type"]
        if t not in by_type:
            by_type[t] = {"a_pass": 0, "b_pass": 0, "n": 0,
                          "a_service_err": 0, "b_service_err": 0}
        by_type[t]["n"] += 1
        if r["condition_a"].get("error_class") == "service_error":
            by_type[t]["a_service_err"] += 1
        elif r["condition_a"]["fix_pass"]:
            by_type[t]["a_pass"] += 1
        if r["condition_b"].get("error_class") == "service_error":
            by_type[t]["b_service_err"] += 1
        elif r["condition_b"]["fix_pass"]:
            by_type[t]["b_pass"] += 1

    def _rate(passed: int, total: int, svc_err: int) -> float:
        denom = total - svc_err
        return round(passed / denom, 3) if denom > 0 else 0.0

    summary = {
        "total_cases": n,
        "condition_a_service_errors": a_service,
        "condition_b_service_errors": b_service,
        "condition_a_fix_rate": round(a_pass / len(a_valid), 3) if a_valid else 0,
        "condition_b_fix_rate": round(b_pass / len(b_valid), 3) if b_valid else 0,
        "delta_b_minus_a": round(
            (b_pass / len(b_valid) if b_valid else 0)
            - (a_pass / len(a_valid) if a_valid else 0), 3
        ),
        "by_mutation_type": {
            t: {
                "n": v["n"],
                "a_rate": _rate(v["a_pass"], v["n"], v["a_service_err"]),
                "b_rate": _rate(v["b_pass"], v["n"], v["b_service_err"]),
                "a_service_err": v["a_service_err"],
                "b_service_err": v["b_service_err"],
            }
            for t, v in by_type.items()
        },
    }
    (OUT_DIR / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n=== EXPERIMENT SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=20,
                        help="Max cases to evaluate (default 20)")
    args = parser.parse_args()
    run_experiment(sample=args.sample)
