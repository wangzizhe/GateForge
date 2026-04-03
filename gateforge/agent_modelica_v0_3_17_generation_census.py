from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_17_common import (
    REPO_ROOT,
    classify_library_resolution_status,
    extract_snapshot,
    generate_modelica_draft,
    load_json,
    now_utc,
    run_generated_model_live,
    write_json,
    write_text,
)


SCHEMA_VERSION = "agent_modelica_v0_3_17_generation_census"
DEFAULT_PROMPT_PACK = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_prompt_pack_current" / "prompt_pack.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_live_results_current"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current"


def _replacement_eligible(status: str) -> bool:
    return str(status or "").strip().lower() == "unresolved"


def _run_prompt_row(row: dict, *, results_dir: Path, generation_backend: str, timeout_sec: int) -> dict:
    task_id = str(row.get("task_id") or "").strip()
    generated = generate_modelica_draft(row, requested_backend=generation_backend)
    row_payload = {
        "task_id": task_id,
        "complexity_tier": row.get("complexity_tier"),
        "role": row.get("role"),
        "ordinal_within_tier": row.get("ordinal_within_tier"),
        "model_name": row.get("model_name"),
        "natural_language_spec": row.get("natural_language_spec"),
        "expected_domain_tags": row.get("expected_domain_tags") or [],
        "expected_component_count_band": row.get("expected_component_count_band"),
        "allowed_library_scope": row.get("allowed_library_scope"),
        "generation_provider": generated.get("provider_name"),
        "generation_model": generated.get("model"),
        "generation_success": bool(generated.get("generation_success")),
        "generation_rationale": generated.get("rationale"),
    }
    draft_dir = results_dir / "drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)
    write_text(draft_dir / f"{task_id}_response.txt", str(generated.get("response_text") or ""))
    write_text(draft_dir / f"{task_id}.mo", str(generated.get("modelica_code") or ""))
    row_payload["draft_model_path"] = str((draft_dir / f"{task_id}.mo").resolve())
    if not bool(generated.get("generation_success")):
        row_payload.update(
            {
                "status": "GENERATION_OUTPUT_INVALID",
                "library_resolution_status": "not_evaluated",
                "first_failure": {},
                "result_json_path": "",
            }
        )
        return row_payload
    live = run_generated_model_live(
        task_id=task_id,
        modelica_code=str(generated.get("modelica_code") or ""),
        result_dir=results_dir,
        evaluation_label="v0317_first_failure",
        max_rounds=1,
        declared_failure_type="simulate_error",
        expected_stage="simulate",
        timeout_sec=timeout_sec,
    )
    detail = live.get("detail") if isinstance(live.get("detail"), dict) else {}
    snapshot = extract_snapshot(detail, attempt_index=0)
    library_status = classify_library_resolution_status(detail)
    row_payload.update(
        {
            "status": "PASS" if detail else "EVAL_MISSING_RESULT",
            "library_resolution_status": library_status,
            "first_failure": snapshot,
            "result_json_path": live.get("result_json_path"),
            "executor_status": detail.get("executor_status"),
            "check_model_pass": detail.get("check_model_pass"),
            "simulate_pass": detail.get("simulate_pass"),
            "stdout_snippet": live.get("stdout_snippet"),
            "stderr_snippet": live.get("stderr_snippet"),
        }
    )
    return row_payload


def _finalize_tier(section: dict, *, results_dir: Path, generation_backend: str, timeout_sec: int) -> tuple[list[dict], list[dict], list[dict]]:
    active_rows = [row for row in (section.get("active_tasks") or []) if isinstance(row, dict)]
    reserve_rows = [row for row in (section.get("reserve_tasks") or []) if isinstance(row, dict)]
    final_rows: list[dict] = []
    replaced_rows: list[dict] = []
    used_reserves: list[dict] = []
    reserve_index = 0
    for active in active_rows:
        evaluated = _run_prompt_row(active, results_dir=results_dir, generation_backend=generation_backend, timeout_sec=timeout_sec)
        if _replacement_eligible(str(evaluated.get("library_resolution_status") or "")):
            replacement = None
            while reserve_index < len(reserve_rows):
                reserve_row = reserve_rows[reserve_index]
                reserve_index += 1
                reserve_eval = _run_prompt_row(reserve_row, results_dir=results_dir, generation_backend=generation_backend, timeout_sec=timeout_sec)
                used_reserves.append(reserve_eval)
                if not _replacement_eligible(str(reserve_eval.get("library_resolution_status") or "")):
                    replacement = dict(reserve_eval)
                    replacement["replaces_task_id"] = evaluated.get("task_id")
                    break
            if replacement is not None:
                replaced = dict(evaluated)
                replaced["replaced_by_task_id"] = replacement.get("task_id")
                replaced_rows.append(replaced)
                final_rows.append(replacement)
                continue
        final_rows.append(evaluated)
    return final_rows, replaced_rows, used_reserves


def _stage_distribution(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        snapshot = row.get(key) if isinstance(row.get(key), dict) else {}
        stage = str(snapshot.get("dominant_stage_subtype") or "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def build_generation_census(
    *,
    prompt_pack_path: str = str(DEFAULT_PROMPT_PACK),
    results_dir: str = str(DEFAULT_RESULTS_DIR),
    out_dir: str = str(DEFAULT_OUT_DIR),
    generation_backend: str = "",
    timeout_sec: int = 600,
) -> dict:
    prompt_pack = load_json(prompt_pack_path)
    tiers = prompt_pack.get("tiers") if isinstance(prompt_pack.get("tiers"), dict) else {}
    results_root = Path(results_dir)
    final_rows: list[dict] = []
    replaced_rows: list[dict] = []
    reserve_usage: list[dict] = []
    tier_summary: dict[str, dict] = {}
    repair_task_rows: list[dict] = []
    for tier_name in ("simple", "medium", "complex"):
        section = tiers.get(tier_name) if isinstance(tiers.get(tier_name), dict) else {}
        tier_final, tier_replaced, tier_reserves = _finalize_tier(
            section,
            results_dir=results_root / tier_name,
            generation_backend=generation_backend,
            timeout_sec=timeout_sec,
        )
        final_rows.extend(tier_final)
        replaced_rows.extend(tier_replaced)
        reserve_usage.extend(tier_reserves)
        tier_summary[tier_name] = {
            "final_count": len(tier_final),
            "replaced_count": len(tier_replaced),
            "reserve_used_count": len(tier_reserves),
            "generation_invalid_count": len([row for row in tier_final if str(row.get("status")) == "GENERATION_OUTPUT_INVALID"]),
            "library_unresolved_count": len([row for row in tier_final if str(row.get("library_resolution_status")) == "unresolved"]),
            "first_failure_stage_distribution": _stage_distribution(tier_final, "first_failure"),
        }
        for row in tier_final:
            if not bool(row.get("generation_success")):
                continue
            repair_task_rows.append(
                {
                    "task_id": row.get("task_id"),
                    "complexity_tier": row.get("complexity_tier"),
                    "source_model_text": Path(str(row.get("draft_model_path"))).read_text(encoding="utf-8"),
                    "mutated_model_text": Path(str(row.get("draft_model_path"))).read_text(encoding="utf-8"),
                    "first_failure": row.get("first_failure"),
                    "result_json_path": row.get("result_json_path"),
                }
            )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "prompt_pack_path": str(Path(prompt_pack_path).resolve()) if Path(prompt_pack_path).exists() else str(prompt_pack_path),
        "expected_main_task_count": 30,
        "final_task_count": len(final_rows),
        "repair_eligible_task_count": len(repair_task_rows),
        "replaced_task_count": len(replaced_rows),
        "reserve_used_count": len(reserve_usage),
        "tier_summary": tier_summary,
        "rows": final_rows,
        "replaced_rows": replaced_rows,
        "reserve_usage_rows": reserve_usage,
    }
    repair_taskset = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if repair_task_rows else "EMPTY",
        "task_count": len(repair_task_rows),
        "tasks": repair_task_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "repair_taskset.json", repair_taskset)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.17 Generation Census",
                "",
                f"- status: `{summary.get('status')}`",
                f"- final_task_count: `{summary.get('final_task_count')}`",
                f"- repair_eligible_task_count: `{summary.get('repair_eligible_task_count')}`",
                f"- reserve_used_count: `{summary.get('reserve_used_count')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.17 first-failure generation census.")
    parser.add_argument("--prompt-pack", default=str(DEFAULT_PROMPT_PACK))
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--generation-backend", default="")
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_generation_census(
        prompt_pack_path=str(args.prompt_pack),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        generation_backend=str(args.generation_backend),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "final_task_count": payload.get("final_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
