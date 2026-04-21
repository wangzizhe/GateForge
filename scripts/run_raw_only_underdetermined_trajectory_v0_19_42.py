"""Run raw-only multi-turn trajectories on existing underdetermined families.

v0.19.42 discipline:
  - No DM context
  - No root-cause hint
  - No generic fix hint
  - No per-variable repair hint
  - No deterministic repair action suggestion

The LLM sees only:
  - current model text
  - raw OMC checkModel output
  - workflow goal

Families:
  - parameter_promotion
  - phantom_variable
  - compound_underdetermined

Usage:
  python3 scripts/run_raw_only_underdetermined_trajectory_v0_19_42.py
  python3 scripts/run_raw_only_underdetermined_trajectory_v0_19_42.py --sample-per-family 4
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
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

ADMITTED_STRUCTURAL = REPO_ROOT / "artifacts" / "structural_mutation_experiment_v0_19_34" / "admitted_cases.jsonl"
ADMITTED_COMPOUND = REPO_ROOT / "artifacts" / "compound_underdetermined_experiment_v0_19_38" / "admitted_cases.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "raw_only_underdetermined_trajectory_v0_19_42"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PLANNER_BACKEND = "gemini"
RNG = random.Random(42)


def _classify_llm_error(err: str) -> str:
    if not err:
        return ""
    text = err.lower()
    if any(
        token in text
        for token in (
            "503",
            "502",
            "service_unavailable",
            "rate_limited",
            "timeout",
            "url_error",
            "budget_exceeded",
        )
    ):
        return "service_error"
    if "json" in text or "missing_patched_model_text" in text or "no_output" in text:
        return "format_err"
    return "llm_fail"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_cases() -> list[dict]:
    structural = [
        row for row in _read_jsonl(ADMITTED_STRUCTURAL)
        if row.get("mutation_type") in {"parameter_promotion", "phantom_variable"}
    ]
    compound = _read_jsonl(ADMITTED_COMPOUND)
    cases = structural + compound
    for row in cases:
        row["_family"] = str(row.get("mutation_type") or row.get("mutation_family") or "")
    return cases


def _sample_cases(cases: list[dict], sample_per_family: int | None) -> list[dict]:
    if sample_per_family is None:
        return cases
    grouped: dict[str, list[dict]] = {}
    for case in cases:
        grouped.setdefault(case["_family"], []).append(case)
    sampled: list[dict] = []
    for family, rows in sorted(grouped.items()):
        picked = rows if len(rows) <= sample_per_family else RNG.sample(rows, sample_per_family)
        sampled.extend(picked)
        print(f"Sampled {len(picked)}/{len(rows)} cases for {family}")
    return sampled


def _filter_families(cases: list[dict], families: list[str] | None) -> list[dict]:
    if not families:
        return cases
    keep = {str(x).strip() for x in families if str(x).strip()}
    return [case for case in cases if case["_family"] in keep]


def _run_check(model_text: str, model_name: str) -> tuple[bool, str]:
    with temporary_workspace("gf_v01942_raw_") as ws:
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


def _strip_ws(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _llm_turn(
    *,
    model_text: str,
    model_name: str,
    failure_type: str,
    workflow_goal: str,
    error_excerpt: str,
    current_round: int,
) -> tuple[str | None, str, str]:
    patched, err, provider = llm_repair_model_text(
        planner_backend=PLANNER_BACKEND,
        original_text=model_text,
        failure_type=failure_type,
        expected_stage="check",
        error_excerpt=error_excerpt[:12000],
        repair_actions=[],
        model_name=model_name,
        workflow_goal=workflow_goal,
        current_round=current_round,
    )
    return patched, err, provider


def _classify_turn_shape(attempts: list[dict], final_pass: bool) -> str:
    if not attempts:
        return "format_or_service_fail"
    if any(str(a.get("llm_error_class") or "") in {"service_error", "format_err"} for a in attempts):
        return "format_or_service_fail"
    if not final_pass:
        changed_attempts = [a for a in attempts if a.get("round", 0) >= 1 and a.get("patched_text_present")]
        if not changed_attempts:
            return "format_or_service_fail"
        if all(not bool(a.get("model_changed")) for a in changed_attempts):
            return "stalled_no_progress"
        return "stalled_no_progress"
    changed_attempts = [a for a in attempts if a.get("round", 0) >= 1 and a.get("patched_text_present")]
    if not changed_attempts:
        return "format_or_service_fail"
    if len(changed_attempts) == 1:
        return "single_fix_closure"

    for idx, row in enumerate(changed_attempts[:-1]):
        next_row = changed_attempts[idx + 1]
        if row.get("model_changed") and not row.get("check_pass_after_patch") and next_row.get("check_pass_before_patch") is False:
            if row.get("omc_output_before_patch") != next_row.get("omc_output_before_patch"):
                return "partial_fix_then_continue"
            return "wrong_direction_then_recover"
    return "single_fix_closure"


def _run_case(case: dict, max_turns: int, patched_dir: Path) -> dict:
    candidate_id = case["candidate_id"]
    broken_text = Path(case["mutated_model_path"]).read_text(encoding="utf-8")
    model_name = str(case["model_name"])
    workflow_goal = str(case.get("workflow_goal") or "")
    family = str(case["_family"])

    current_text = broken_text
    attempts: list[dict] = []
    final_status = "FAIL"
    final_error_class = ""

    for round_idx in range(1, max_turns + 1):
        check_ok_before, omc_output_before = _run_check(current_text, model_name)
        attempt = {
            "round": round_idx,
            "check_pass_before_patch": check_ok_before,
            "omc_output_before_patch": omc_output_before,
            "observed_state_before_patch": "none" if check_ok_before else "model_check_error",
            "patched_text_present": False,
            "model_changed": False,
            "provider": "",
            "llm_error": "",
            "llm_error_class": "",
            "check_pass_after_patch": None,
            "omc_output_after_patch": "",
            "patched_model_path": "",
        }
        if check_ok_before:
            final_status = "PASS"
            attempts.append(attempt)
            break

        patched_text, llm_err, provider = _llm_turn(
            model_text=current_text,
            model_name=model_name,
            failure_type=str(case.get("failure_type") or "underdetermined_structural"),
            workflow_goal=workflow_goal,
            error_excerpt=omc_output_before,
            current_round=round_idx,
        )
        attempt["provider"] = provider
        attempt["llm_error"] = llm_err
        attempt["llm_error_class"] = _classify_llm_error(llm_err)

        if not isinstance(patched_text, str) or not patched_text.strip():
            final_error_class = attempt["llm_error_class"] or "llm_fail"
            attempts.append(attempt)
            break

        attempt["patched_text_present"] = True
        attempt["model_changed"] = _strip_ws(patched_text) != _strip_ws(current_text)
        patched_path = patched_dir / f"{candidate_id}_T{round_idx}.mo"
        patched_path.write_text(patched_text, encoding="utf-8")
        attempt["patched_model_path"] = str(patched_path)

        check_ok_after, omc_output_after = _run_check(patched_text, model_name)
        attempt["check_pass_after_patch"] = check_ok_after
        attempt["omc_output_after_patch"] = omc_output_after
        attempts.append(attempt)

        current_text = patched_text
        if check_ok_after:
            final_status = "PASS"
            break

    turn_shape = _classify_turn_shape(attempts, final_status == "PASS")
    observed_sequence = [str(a.get("observed_state_before_patch") or "") for a in attempts]
    return {
        "candidate_id": candidate_id,
        "family": family,
        "source_file": case.get("source_file", ""),
        "model_name": model_name,
        "final_status": final_status,
        "turn_count": len(attempts),
        "turn_shape": turn_shape,
        "final_error_class": final_error_class,
        "observed_sequence": observed_sequence,
        "attempts": attempts,
    }


def _build_summary(rows: list[dict]) -> dict:
    by_family: dict[str, dict] = {}
    for row in rows:
        fam = row["family"]
        bucket = by_family.setdefault(
            fam,
            {
                "n_cases": 0,
                "pass_n": 0,
                "clean_n": 0,
                "clean_pass_n": 0,
                "avg_turns_all": 0.0,
                "turn_shapes": {},
            },
        )
        bucket["n_cases"] += 1
        bucket["pass_n"] += 1 if row["final_status"] == "PASS" else 0
        if row["turn_shape"] != "format_or_service_fail":
            bucket["clean_n"] += 1
            bucket["clean_pass_n"] += 1 if row["final_status"] == "PASS" else 0
        bucket["avg_turns_all"] += row["turn_count"]
        ts = row["turn_shape"]
        bucket["turn_shapes"][ts] = bucket["turn_shapes"].get(ts, 0) + 1

    for fam, bucket in by_family.items():
        n_cases = bucket["n_cases"] or 1
        bucket["pass_rate"] = round(bucket["pass_n"] / n_cases, 3)
        bucket["clean_pass_rate"] = round(bucket["clean_pass_n"] / bucket["clean_n"], 3) if bucket["clean_n"] else None
        bucket["avg_turns_all"] = round(bucket["avg_turns_all"] / n_cases, 3)

    overall = {
        "n_cases": len(rows),
        "pass_n": sum(1 for r in rows if r["final_status"] == "PASS"),
        "clean_n": sum(1 for r in rows if r["turn_shape"] != "format_or_service_fail"),
        "clean_pass_n": sum(1 for r in rows if r["turn_shape"] != "format_or_service_fail" and r["final_status"] == "PASS"),
        "turn_shapes": {},
    }
    if rows:
        overall["pass_rate"] = round(overall["pass_n"] / len(rows), 3)
        overall["clean_pass_rate"] = round(overall["clean_pass_n"] / overall["clean_n"], 3) if overall["clean_n"] else None
        overall["avg_turns_all"] = round(sum(r["turn_count"] for r in rows) / len(rows), 3)
    else:
        overall["pass_rate"] = 0.0
        overall["clean_pass_rate"] = None
        overall["avg_turns_all"] = 0.0
    for row in rows:
        ts = row["turn_shape"]
        overall["turn_shapes"][ts] = overall["turn_shapes"].get(ts, 0) + 1

    return {
        "version": "v0.19.42",
        "mode": "raw_only",
        "families": by_family,
        "overall": overall,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-per-family", type=int, default=None)
    parser.add_argument("--max-turns", type=int, default=3)
    parser.add_argument("--families", nargs="*", default=None)
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    cases = _load_cases()
    cases = _filter_families(cases, args.families)
    cases = _sample_cases(cases, args.sample_per_family)
    print(f"Loaded {len(cases)} raw-only underdetermined cases.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT_DIR / "raw"
    raw_dir.mkdir(exist_ok=True)
    patched_dir = OUT_DIR / "patched_models"
    patched_dir.mkdir(exist_ok=True)

    results: list[dict] = []
    for idx, case in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] {case['candidate_id']} ({case['_family']})")
        raw_path = raw_dir / f"{case['candidate_id']}.json"
        if args.skip_existing and raw_path.exists():
            row = json.loads(raw_path.read_text(encoding="utf-8"))
            results.append(row)
            print(
                f"  -> reuse {row['final_status']} | turns={row['turn_count']} | shape={row['turn_shape']} | seq={row['observed_sequence']}"
            )
            continue
        row = _run_case(case, max_turns=args.max_turns, patched_dir=patched_dir)
        results.append(row)
        raw_path.write_text(
            json.dumps(row, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            f"  -> {row['final_status']} | turns={row['turn_count']} | shape={row['turn_shape']} | seq={row['observed_sequence']}"
        )

    summary = _build_summary(results)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )
    print("\n=== RAW-ONLY UNDERDETERMINED SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
