from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_experience_replay_v1 import build_rule_priority_context
from .agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from .agent_modelica_v0_4_1_common import (
    DEFAULT_EXPERIENCE_STORE_PATH,
    DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR,
    DEFAULT_V040_BENCHMARK_PATH,
    SCHEMA_PREFIX,
    benchmark_tasks,
    family_counts,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_signal_source_audit"


def build_v041_signal_source_audit(
    *,
    benchmark_path: str = str(DEFAULT_V040_BENCHMARK_PATH),
    legacy_experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE_PATH),
    out_dir: str = str(DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR),
) -> dict:
    if not Path(benchmark_path).exists():
        build_v040_benchmark_freeze(out_dir=str(Path(benchmark_path).parent))

    benchmark = load_json(benchmark_path)
    legacy = load_json(legacy_experience_store_path)
    tasks = benchmark_tasks(benchmark)
    task_family_counts = family_counts(tasks)

    legacy_exact_match_by_family: dict[str, int] = {}
    refreshed_candidate_capacity_by_family: dict[str, int] = {}
    family_signal_source_breakdown: dict[str, dict] = {}
    for family_id in sorted(task_family_counts.keys()):
        family_tasks = [row for row in tasks if str(row.get("family_id") or "") == family_id]
        exact_hits = 0
        for task in family_tasks:
            replay_ctx = build_rule_priority_context(
                legacy,
                failure_type=str(task.get("declared_failure_type") or ""),
                error_subtype=str(task.get("error_subtype") or ""),
                dominant_stage_subtype=str(task.get("dominant_stage_subtype") or ""),
                residual_signal_cluster=str(task.get("residual_signal_cluster") or ""),
            )
            coverage = replay_ctx.get("coverage") if isinstance(replay_ctx.get("coverage"), dict) else {}
            if str(coverage.get("signal_coverage_status") or "") == "exact_step_match_available":
                exact_hits += 1
        legacy_exact_match_by_family[family_id] = exact_hits
        refreshed_candidate_capacity_by_family[family_id] = len(family_tasks)
        family_signal_source_breakdown[family_id] = {
            "benchmark_task_count": len(family_tasks),
            "legacy_exact_match_task_count": exact_hits,
            "legacy_exact_match_available": exact_hits > 0,
            "refreshed_extraction_candidate_count": len(family_tasks),
            "has_minimal_signal_fields": all(
                bool(task.get("patch_type") or task.get("allowed_patch_types"))
                and bool(task.get("family_id"))
                and bool(task.get("family_target_bucket"))
                for task in family_tasks
            ),
        }

    any_legacy_stage2_signal = any(int(value or 0) > 0 for value in legacy_exact_match_by_family.values())
    signal_source_mode = "existing_step_artifacts" if any_legacy_stage2_signal else "refreshed_extraction_required"
    signal_source_ready = all(bool((family_signal_source_breakdown.get(family_id) or {}).get("has_minimal_signal_fields")) for family_id in family_signal_source_breakdown)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if signal_source_ready else "FAIL",
        "benchmark_path": str(Path(benchmark_path).resolve()),
        "legacy_experience_store_path": str(Path(legacy_experience_store_path).resolve()),
        "signal_source_mode": signal_source_mode,
        "family_signal_source_breakdown": family_signal_source_breakdown,
        "legacy_exact_match_by_family": legacy_exact_match_by_family,
        "refreshed_candidate_capacity_by_family": refreshed_candidate_capacity_by_family,
        "signal_source_ready": signal_source_ready,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.1 Signal Source Audit",
                "",
                f"- signal_source_mode: `{payload.get('signal_source_mode')}`",
                f"- signal_source_ready: `{payload.get('signal_source_ready')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.1 stage-2 signal source audit.")
    parser.add_argument("--benchmark", default=str(DEFAULT_V040_BENCHMARK_PATH))
    parser.add_argument("--legacy-experience-store", default=str(DEFAULT_EXPERIENCE_STORE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v041_signal_source_audit(
        benchmark_path=str(args.benchmark),
        legacy_experience_store_path=str(args.legacy_experience_store),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "signal_source_mode": payload.get("signal_source_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
