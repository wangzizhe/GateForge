from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_18_stage2_common import (
    DEFAULT_GENERATION_CENSUS_PATH,
    DEFAULT_ONE_STEP_REPAIR_PATH,
    DEFAULT_PROMPT_PACK_PATH,
    DEFAULT_REPAIR_TASKSET_PATH,
    DEFAULT_SAMPLE_MANIFEST_OUT_DIR,
    FROZEN_SAMPLE_STRATEGY,
    FROZEN_STAGE2_SAMPLE_TASK_IDS,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    task_id_map,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_stage2_sample_manifest"
TIER_ORDER = {
    "simple": 0,
    "medium": 1,
    "complex": 2,
}


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _row_excerpt(log_excerpt: str, max_chars: int = 1200) -> str:
    text = norm(log_excerpt)
    return text[:max_chars]


def build_stage2_sample_manifest(
    *,
    prompt_pack_path: str = str(DEFAULT_PROMPT_PACK_PATH),
    generation_census_path: str = str(DEFAULT_GENERATION_CENSUS_PATH),
    repair_taskset_path: str = str(DEFAULT_REPAIR_TASKSET_PATH),
    one_step_repair_path: str = str(DEFAULT_ONE_STEP_REPAIR_PATH),
    out_dir: str = str(DEFAULT_SAMPLE_MANIFEST_OUT_DIR),
) -> dict:
    prompt_pack = load_json(prompt_pack_path)
    generation_census = load_json(generation_census_path)
    repair_taskset = load_json(repair_taskset_path)
    one_step_repair = load_json(one_step_repair_path)

    prompt_rows = task_id_map(_task_rows(prompt_pack))
    census_rows = task_id_map(generation_census.get("rows") if isinstance(generation_census.get("rows"), list) else [])
    repair_task_rows = task_id_map(_task_rows(repair_taskset))
    one_step_rows = task_id_map(one_step_repair.get("rows") if isinstance(one_step_repair.get("rows"), list) else [])

    samples: list[dict] = []
    missing_task_ids: list[str] = []
    for task_id in FROZEN_STAGE2_SAMPLE_TASK_IDS:
        prompt_row = prompt_rows.get(task_id) or {}
        census_row = census_rows.get(task_id) or {}
        repair_task_row = repair_task_rows.get(task_id) or {}
        one_step_row = one_step_rows.get(task_id) or {}
        if not prompt_row or not census_row or not repair_task_row or not one_step_row:
            missing_task_ids.append(task_id)
            continue
        result_detail = load_json(one_step_row.get("result_json_path") or "")
        attempts = result_detail.get("attempts") if isinstance(result_detail.get("attempts"), list) else []
        first_attempt = next((row for row in attempts if isinstance(row, dict)), {})
        samples.append(
            {
                "task_id": task_id,
                "complexity_tier": norm(prompt_row.get("complexity_tier")),
                "ordinal_within_tier": int(prompt_row.get("ordinal_within_tier") or 0),
                "model_name": norm(prompt_row.get("model_name")),
                "natural_language_spec": norm(prompt_row.get("natural_language_spec")),
                "expected_domain_tags": list(prompt_row.get("expected_domain_tags") or []),
                "expected_component_count_band": norm(prompt_row.get("expected_component_count_band")),
                "allowed_library_scope": norm(prompt_row.get("allowed_library_scope")),
                "first_failure": dict(repair_task_row.get("first_failure") or {}),
                "second_residual": dict(one_step_row.get("second_residual") or {}),
                "repair_action_type": norm(one_step_row.get("repair_action_type")),
                "second_residual_actionability": norm(one_step_row.get("second_residual_actionability")),
                "source_model_text": norm(repair_task_row.get("source_model_text")),
                "one_step_result_json_path": norm(one_step_row.get("result_json_path")),
                "one_step_log_excerpt": _row_excerpt(norm(first_attempt.get("log_excerpt"))),
            }
        )

    samples.sort(
        key=lambda row: (
            TIER_ORDER.get(norm(row.get("complexity_tier")), 99),
            int(row.get("ordinal_within_tier") or 0),
        )
    )
    tier_counts: dict[str, int] = {}
    for row in samples:
        tier = norm(row.get("complexity_tier")) or "unknown"
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if not missing_task_ids and len(samples) == len(FROZEN_STAGE2_SAMPLE_TASK_IDS) else "FAIL",
        "source_paths": {
            "prompt_pack_path": str(Path(prompt_pack_path).resolve()) if Path(prompt_pack_path).exists() else str(prompt_pack_path),
            "generation_census_path": str(Path(generation_census_path).resolve()) if Path(generation_census_path).exists() else str(generation_census_path),
            "repair_taskset_path": str(Path(repair_taskset_path).resolve()) if Path(repair_taskset_path).exists() else str(repair_taskset_path),
            "one_step_repair_path": str(Path(one_step_repair_path).resolve()) if Path(one_step_repair_path).exists() else str(one_step_repair_path),
        },
        "frozen_selection_strategy": FROZEN_SAMPLE_STRATEGY,
        "sample_count": len(samples),
        "tier_counts": tier_counts,
        "sample_task_ids": [row["task_id"] for row in samples],
        "missing_task_ids": missing_task_ids,
        "samples": samples,
    }
    out_root = Path(out_dir)
    write_json(out_root / "manifest.json", payload)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.18 Stage_2 Sample Manifest",
                "",
                f"- status: `{payload.get('status')}`",
                f"- sample_count: `{payload.get('sample_count')}`",
                f"- sample_task_ids: `{', '.join(payload.get('sample_task_ids') or [])}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the v0.3.18 stage_2 sample manifest.")
    parser.add_argument("--prompt-pack", default=str(DEFAULT_PROMPT_PACK_PATH))
    parser.add_argument("--generation-census", default=str(DEFAULT_GENERATION_CENSUS_PATH))
    parser.add_argument("--repair-taskset", default=str(DEFAULT_REPAIR_TASKSET_PATH))
    parser.add_argument("--one-step-repair", default=str(DEFAULT_ONE_STEP_REPAIR_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_SAMPLE_MANIFEST_OUT_DIR))
    args = parser.parse_args()
    payload = build_stage2_sample_manifest(
        prompt_pack_path=str(args.prompt_pack),
        generation_census_path=str(args.generation_census),
        repair_taskset_path=str(args.repair_taskset),
        one_step_repair_path=str(args.one_step_repair),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "sample_count": payload.get("sample_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
