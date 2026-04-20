"""Multi-turn self-healing experiment for phantom_variable (v0.19.37).

Hypothesis: phantom_variable "half-fix" cases (LLM fixes equation reference
but forgets to delete the phantom declaration) self-correct on turn 2, because
the residual error message directly names the orphaned phantom variable.

Method:
  - Reuse v0.19.36 turn-1 results (condition A, raw OMC).
  - For turn-1 FAIL cases with a saved patched model: run OMC on the patched
    model to get the turn-2 error, then run LLM turn 2.
  - Report 1-turn rate and cumulative 2-turn rate.

Usage:
  python3 scripts/run_phantom_multiturn_experiment_v0_19_37.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# 5 turn-2 candidates × 1 condition = ~5 calls
os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "30")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
from gateforge.agent_modelica_omc_workspace_v1 import (
    prepare_workspace_model_layout,
    run_check_and_simulate,
    temporary_workspace,
)

V36_RESULTS = (
    REPO_ROOT / "artifacts" / "dm_context_experiment_v0_19_36" / "experiment_results.jsonl"
)
V36_PATCHED_DIR = (
    REPO_ROOT / "artifacts" / "dm_context_experiment_v0_19_36" / "patched_models"
)
ADMITTED_PATH = (
    REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34" / "admitted_cases.jsonl"
)
OUT_DIR = REPO_ROOT / "artifacts" / "phantom_multiturn_experiment_v0_19_37"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"


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
    with temporary_workspace("gf_exp37_") as ws:
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


def _run_llm_turn(
    *,
    model_text: str,
    model_name: str,
    failure_type: str,
    workflow_goal: str,
    error_excerpt: str,
    current_round: int,
) -> tuple[dict, str | None]:
    patched, err, _ = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=model_text,
        failure_type=failure_type,
        expected_stage="check",
        error_excerpt=error_excerpt,
        repair_actions=["Restore or add the missing defining equation or declaration."],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
    )
    if err or patched is None:
        err_str = err or "no_output"
        return {
            "fix_pass": False,
            "llm_error": err_str,
            "error_class": _classify_llm_error(err_str),
            "omc_output_snippet": "",
        }, None

    check_pass, omc_out = _run_check(patched, model_name)
    return {
        "fix_pass": check_pass,
        "llm_error": "",
        "error_class": "",
        "omc_output_snippet": omc_out[:500],
    }, patched


# ── main ──────────────────────────────────────────────────────────────────────

def run_experiment() -> None:
    v36_rows = [
        json.loads(l)
        for l in V36_RESULTS.read_text().splitlines() if l.strip()
    ]
    admitted = {
        c["candidate_id"]: c
        for l in ADMITTED_PATH.read_text().splitlines() if l.strip()
        for c in [json.loads(l)]
        if c.get("mutation_type") == "phantom_variable"
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    patched_dir = OUT_DIR / "patched_models"
    patched_dir.mkdir(exist_ok=True)

    results: list[dict] = []

    for row in v36_rows:
        cid = row["candidate_id"]
        ca = row["condition_a"]
        case = admitted.get(cid, {})
        model_name = case.get("model_name", "")
        failure_type = case.get("failure_type", "underdetermined_structural")
        workflow_goal = case.get("workflow_goal", "")

        turn1_pass = ca["fix_pass"]
        turn1_error_class = ca.get("error_class", "")

        patched_t1_path = V36_PATCHED_DIR / f"{cid}_A.mo"
        has_patched_t1 = patched_t1_path.exists()

        print(f"{cid}")
        print(f"  Turn1: {'PASS' if turn1_pass else 'FAIL'} (error_class={turn1_error_class!r})")

        if turn1_pass:
            # Already fixed in turn 1 — no need for turn 2
            results.append({
                "candidate_id": cid,
                "turn1_pass": True,
                "turn2_attempted": False,
                "turn2_pass": None,
                "cumulative_pass": True,
                "turn1_error_class": "",
                "turn2_error_class": None,
            })
            print("  → 1-turn fix, skip turn 2")
            continue

        if not has_patched_t1 or turn1_error_class in ("llm_fail", "service_error"):
            # No patched model to continue from
            results.append({
                "candidate_id": cid,
                "turn1_pass": False,
                "turn2_attempted": False,
                "turn2_pass": None,
                "cumulative_pass": False,
                "turn1_error_class": turn1_error_class,
                "turn2_error_class": None,
            })
            print(f"  → No patched model ({turn1_error_class or 'no output'}), skip turn 2")
            continue

        # Turn 1 failed but produced a patched model — run OMC to get turn-2 error
        patched_t1_text = patched_t1_path.read_text(encoding="utf-8")
        _, t2_error_raw = _run_check(patched_t1_text, model_name)
        print(f"  Turn2 error excerpt: {t2_error_raw[:120].strip()!r}")

        result_t2, patched_t2 = _run_llm_turn(
            model_text=patched_t1_text,
            model_name=model_name,
            failure_type=failure_type,
            workflow_goal=workflow_goal,
            error_excerpt=t2_error_raw[:1500],
            current_round=2,
        )

        if patched_t2 is not None:
            (patched_dir / f"{cid}_T2.mo").write_text(patched_t2, encoding="utf-8")

        turn2_pass = result_t2["fix_pass"]
        print(f"  Turn2: {'PASS' if turn2_pass else 'FAIL'}")

        results.append({
            "candidate_id": cid,
            "turn1_pass": False,
            "turn2_attempted": True,
            "turn2_pass": turn2_pass,
            "cumulative_pass": turn2_pass,
            "turn1_error_class": "",
            "turn2_error_class": result_t2.get("error_class", ""),
        })

    # Summary
    n = len(results)
    t1_pass_n = sum(1 for r in results if r["turn1_pass"])
    cumulative_pass_n = sum(1 for r in results if r["cumulative_pass"])
    t2_attempted = [r for r in results if r["turn2_attempted"]]
    t2_pass_n = sum(1 for r in t2_attempted if r["turn2_pass"])

    summary = {
        "total_cases": n,
        "mutation_type": "phantom_variable",
        "turn1_fix_rate": round(t1_pass_n / n, 3),
        "turn2_attempted_n": len(t2_attempted),
        "turn2_pass_among_attempted": round(t2_pass_n / len(t2_attempted), 3) if t2_attempted else None,
        "cumulative_2turn_fix_rate": round(cumulative_pass_n / n, 3),
        "delta_vs_1turn": round((cumulative_pass_n - t1_pass_n) / n, 3),
    }

    (OUT_DIR / "experiment_results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n=== EXPERIMENT SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run_experiment()
