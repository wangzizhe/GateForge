"""Run the DM diagnostic context experiment (v0.19.36).

Extends v0.19.35 to the phantom_variable mutation family.

  Condition A: LLM sees raw OMC error message (baseline)
  Condition C: LLM sees DM-based diagnostic context (root cause + subgraph)

Both conditions run fresh in the same batch for clean matched-pair comparison.
Fix quality is measured by OMC checkModel + simulation on the LLM-proposed output.

The patched model text is saved per case for post-hoc failure analysis.

Usage:
  python3 scripts/run_dm_context_experiment_v0_19_36.py [--sample N]
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

# 16 cases × 2 conditions = 32 calls
os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "100")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from scripts.diagnostic_context_dm_v0_19_35 import build_dm_diagnostic_context

ADMITTED_PATH = (
    REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34" / "admitted_cases.jsonl"
)
OUT_DIR = REPO_ROOT / "artifacts" / "dm_context_experiment_v0_19_36"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"
MUTATION_TYPE_FILTER = "phantom_variable"


# ── helpers ───────────────────────────────────────────────────────────────────

def _classify_llm_error(err: str) -> str:
    if not err:
        return ""
    e = err.lower()
    if any(x in e for x in ("503", "502", "service_unavailable", "rate_limited",
                             "timeout", "url_error", "budget_exceeded")):
        return "service_error"
    return "llm_fail"


def _run_check(model_text: str, model_name: str) -> tuple[bool, str]:
    with temporary_workspace("gf_exp36_") as ws:
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
) -> tuple[dict, str | None]:
    """Run one LLM repair attempt. Returns (result_dict, patched_text_or_None)."""
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
        return {
            "condition": condition_label,
            "fix_pass": False,
            "llm_error": err_str,
            "error_class": _classify_llm_error(err_str),
            "omc_output_snippet": "",
        }, None

    check_pass, omc_out = _run_check(patched, model_name)
    return {
        "condition": condition_label,
        "fix_pass": check_pass,
        "llm_error": "",
        "error_class": "",
        "omc_output_snippet": omc_out[:500],
    }, patched


# ── main ──────────────────────────────────────────────────────────────────────

def run_experiment(sample: int | None = None) -> None:
    if not ADMITTED_PATH.exists():
        print(f"ERROR: admitted cases not found at {ADMITTED_PATH}")
        sys.exit(1)

    all_cases = [
        json.loads(l) for l in ADMITTED_PATH.read_text().splitlines() if l.strip()
    ]
    cases = [c for c in all_cases if c.get("mutation_type") == MUTATION_TYPE_FILTER]
    print(f"Loaded {len(cases)} {MUTATION_TYPE_FILTER} cases.")

    if sample and len(cases) > sample:
        import random
        random.seed(42)
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
            print(f"  SKIP {cid}: mutated file not found")
            continue

        broken_text = broken_path.read_text(encoding="utf-8")
        model_name = case["model_name"]
        failure_type = case["failure_type"]
        raw_error = case["mutated_failure_excerpt"]
        workflow_goal = case["workflow_goal"]

        dm_ctx = build_dm_diagnostic_context(broken_text)

        print(f"[{idx + 1}/{len(cases)}] {cid}")
        rc = _extract_root_cause(dm_ctx)
        print(f"  DM root cause: {rc or '(none detected)'}")

        result_a, patched_a = _run_condition(
            broken_text=broken_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=workflow_goal,
            error_excerpt=raw_error[:1500],
            condition_label="A_raw_error",
        )

        result_c, patched_c = _run_condition(
            broken_text=broken_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=workflow_goal,
            error_excerpt=dm_ctx[:2000],
            condition_label="C_dm_context",
        )

        if patched_a is not None:
            (patched_dir / f"{cid}_A.mo").write_text(patched_a, encoding="utf-8")
        if patched_c is not None:
            (patched_dir / f"{cid}_C.mo").write_text(patched_c, encoding="utf-8")

        row = {
            "candidate_id": cid,
            "source_file": case.get("source_file", ""),
            "target_name": case.get("target_name", ""),
            "dm_root_cause": rc,
            "condition_a": result_a,
            "condition_c": result_c,
        }
        results.append(row)

        a_pass = "PASS" if result_a["fix_pass"] else "FAIL"
        c_pass = "PASS" if result_c["fix_pass"] else "FAIL"
        print(f"  A={a_pass}  C={c_pass}")

    (OUT_DIR / "experiment_results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )

    n = len(results)
    a_valid = [r for r in results if r["condition_a"].get("error_class") != "service_error"]
    c_valid = [r for r in results if r["condition_c"].get("error_class") != "service_error"]
    a_pass_n = sum(1 for r in a_valid if r["condition_a"]["fix_pass"])
    c_pass_n = sum(1 for r in c_valid if r["condition_c"]["fix_pass"])

    a_rate = round(a_pass_n / len(a_valid), 3) if a_valid else 0.0
    c_rate = round(c_pass_n / len(c_valid), 3) if c_valid else 0.0

    both_valid = [
        r for r in results
        if r["condition_a"].get("error_class") != "service_error"
        and r["condition_c"].get("error_class") != "service_error"
    ]
    a_pass_c_fail = sum(
        1 for r in both_valid
        if r["condition_a"]["fix_pass"] and not r["condition_c"]["fix_pass"]
    )
    a_fail_c_pass = sum(
        1 for r in both_valid
        if not r["condition_a"]["fix_pass"] and r["condition_c"]["fix_pass"]
    )

    summary = {
        "total_cases": n,
        "mutation_type": MUTATION_TYPE_FILTER,
        "condition_a_service_errors": n - len(a_valid),
        "condition_c_service_errors": n - len(c_valid),
        "condition_a_fix_rate": a_rate,
        "condition_c_fix_rate": c_rate,
        "delta_c_minus_a": round(c_rate - a_rate, 3),
        "matched_pair": {
            "both_valid_n": len(both_valid),
            "a_pass_c_fail": a_pass_c_fail,
            "a_fail_c_pass": a_fail_c_pass,
        },
    }
    (OUT_DIR / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n=== EXPERIMENT SUMMARY ===")
    print(json.dumps(summary, indent=2))


def _extract_root_cause(dm_ctx: str) -> str:
    for line in dm_ctx.splitlines():
        if "Root cause variable" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                return parts[-1].strip().split()[0] if parts[-1].strip() else ""
    return ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None,
                        help="Limit to N cases (default: all phantom_variable)")
    args = parser.parse_args()
    run_experiment(sample=args.sample)
