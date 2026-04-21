"""Run triple compound per-variable hint experiment (v0.19.46).

Compares single-turn fix rate for triple compound (PP+PV+PV) between:
  Condition A: raw OMC error only (no hint)
  Condition B: DM diagnostic context with per-variable hints (3 hints)

This fills the missing lower-right cell in the matrix:

              raw-only multi-turn  single-turn + hint
  double      68.4%              90%
  triple      73.7%              ?

Usage:
  python3 scripts/run_triple_hint_experiment_v0_19_46.py
  python3 scripts/run_triple_hint_experiment_v0_19_46.py --sample 4
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "80")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)
from scripts.diagnostic_context_dm_v0_19_35 import build_dm_diagnostic_context

ADMITTED_TRIPLE = REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45_pp_pv_pv" / "admitted_cases.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "triple_hint_experiment_v0_19_46"
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


def _load_existing_case_result(out_dir: Path, candidate_id: str) -> dict[str, Any] | None:
    path = out_dir / f"{candidate_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    a_total = len(results)
    a_pass = sum(1 for r in results if r["condition_a"]["fix_pass"])
    b_total = len(results)
    b_pass = sum(1 for r in results if r["condition_b"]["fix_pass"])
    service_a = sum(1 for r in results if r["condition_a"]["error_class"] == "service_error")
    service_b = sum(1 for r in results if r["condition_b"]["error_class"] == "service_error")
    return {
        "version": "v0.19.46",
        "n_cases": len(results),
        "condition_a": {
            "label": "A_raw",
            "description": "raw OMC error, no hint, single-turn",
            "pass_n": a_pass,
            "pass_rate": round(a_pass / a_total, 3) if a_total else 0,
            "service_errors": service_a,
        },
        "condition_b": {
            "label": "B_dm_hint",
            "description": "DM diagnostic context with per-variable hints, single-turn",
            "pass_n": b_pass,
            "pass_rate": round(b_pass / b_total, 3) if b_total else 0,
            "service_errors": service_b,
        },
        "delta": round((b_pass / b_total) - (a_pass / a_total), 3) if a_total else 0,
    }


def _run_check(model_text: str, model_name: str) -> tuple[bool, str]:
    with temporary_workspace("gf_hint46_") as ws:
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
    patched, err, provider = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=broken_text,
        failure_type=failure_type,
        expected_stage="check",
        error_excerpt=error_excerpt[:12000],
        repair_actions=[],
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--admitted-cases", type=Path, default=ADMITTED_TRIPLE)
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    cases = [json.loads(l) for l in args.admitted_cases.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(cases)} triple compound cases.")

    if args.sample and len(cases) > args.sample:
        import random
        random.seed(42)
        cases = random.sample(cases, args.sample)
        print(f"Sampled {args.sample} cases.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    patched_dir = OUT_DIR / "patched_models"
    patched_dir.mkdir(exist_ok=True)

    results: list[dict] = []

    for idx, case in enumerate(cases):
        cid = case["candidate_id"]
        out_path = OUT_DIR / f"{cid}.json"
        if args.skip_existing:
            existing = _load_existing_case_result(OUT_DIR, cid)
            if existing is not None:
                results.append(existing)
                print(f"[{idx + 1}/{len(cases)}] {cid}")
                print("  SKIP existing result")
                continue

        broken_path = Path(case["mutated_model_path"])
        if not broken_path.exists():
            print(f"  SKIP {cid}: mutated file not found")
            continue

        broken_text = broken_path.read_text(encoding="utf-8")
        model_name = case["model_name"]
        failure_type = case["failure_type"]
        raw_error = case["mutated_failure_excerpt"]
        workflow_goal = case["workflow_goal"]

        print(f"[{idx + 1}/{len(cases)}] {cid}")

        dm_ctx = build_dm_diagnostic_context(broken_text)

        result_a, patched_a = _run_condition(
            broken_text=broken_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=workflow_goal,
            error_excerpt=raw_error[:12000],
            condition_label="A_raw",
        )

        result_b, patched_b = _run_condition(
            broken_text=broken_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=workflow_goal,
            error_excerpt=dm_ctx[:2000],
            condition_label="B_dm_hint",
        )

        if patched_a is not None:
            (patched_dir / f"{cid}_A.mo").write_text(patched_a, encoding="utf-8")
        if patched_b is not None:
            (patched_dir / f"{cid}_B.mo").write_text(patched_b, encoding="utf-8")

        row = {
            "candidate_id": cid,
            "source_file": case.get("source_file", ""),
            "pp1_target": case.get("pp1_target", ""),
            "pv_target": case.get("pv_target", ""),
            "condition_a": result_a,
            "condition_b": result_b,
        }
        results.append(row)

        a_pass = "PASS" if result_a["fix_pass"] else "FAIL"
        b_pass = "PASS" if result_b["fix_pass"] else "FAIL"
        a_err = result_a.get("error_class", "")
        b_err = result_b.get("error_class", "")
        print(f"  A_raw={a_pass}" + (f" ({a_err})" if a_err else ""))
        print(f"  B_dm={b_pass}" + (f" ({b_err})" if b_err else ""))

        out_path.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")

    (OUT_DIR / "results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )

    summary = _build_summary(results)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
