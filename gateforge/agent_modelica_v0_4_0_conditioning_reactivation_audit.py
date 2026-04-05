from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_experience_replay_v1 import build_rule_priority_context, summarize_signal_coverage
from .agent_modelica_planner_experience_context_v1 import build_planner_experience_context
from .agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from .agent_modelica_v0_4_0_common import (
    DEFAULT_BENCHMARK_FREEZE_OUT_DIR,
    DEFAULT_CONDITIONING_AUDIT_OUT_DIR,
    DEFAULT_EXPERIENCE_STORE_PATH,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_conditioning_reactivation_audit"


def _task_replay_metrics(task: dict, experience_payload: dict) -> dict:
    replay_ctx = build_rule_priority_context(
        experience_payload,
        failure_type=str(task.get("declared_failure_type") or "model_check_error"),
        error_subtype=str(task.get("error_subtype") or ""),
        dominant_stage_subtype=str(task.get("dominant_stage_subtype") or ""),
        residual_signal_cluster=str(task.get("residual_signal_cluster") or ""),
    )
    planner_ctx = build_planner_experience_context(
        experience_payload,
        failure_type=str(task.get("declared_failure_type") or "model_check_error"),
        error_subtype=str(task.get("error_subtype") or ""),
        dominant_stage_subtype=str(task.get("dominant_stage_subtype") or ""),
        residual_signal_cluster=str(task.get("residual_signal_cluster") or ""),
    )
    replay_coverage = replay_ctx.get("coverage") if isinstance(replay_ctx.get("coverage"), dict) else {}
    replay_exact = norm(replay_coverage.get("signal_coverage_status")) == "exact_step_match_available" and int(replay_coverage.get("exact_match_step_count") or 0) > 0
    replay_rule_ready = bool(replay_ctx.get("recommended_rule_order"))
    planner_hint_ready = int(planner_ctx.get("positive_hint_count") or 0) > 0 or int(planner_ctx.get("caution_hint_count") or 0) > 0
    return {
        "benchmark_task_id": str(task.get("benchmark_task_id") or ""),
        "family_id": str(task.get("family_id") or ""),
        "task_role": str(task.get("task_role") or ""),
        "replay_exact_match": replay_exact,
        "replay_rule_ready": replay_rule_ready,
        "planner_hint_ready": planner_hint_ready,
        "replay_exact_match_step_count": int(replay_coverage.get("exact_match_step_count") or 0),
        "positive_hint_count": int(planner_ctx.get("positive_hint_count") or 0),
        "caution_hint_count": int(planner_ctx.get("caution_hint_count") or 0),
    }


def build_v040_conditioning_reactivation_audit(
    *,
    benchmark_freeze_path: str = str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "benchmark_pack.json"),
    experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE_PATH),
    out_dir: str = str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR),
) -> dict:
    if not Path(benchmark_freeze_path).exists():
        build_v040_benchmark_freeze(out_dir=str(Path(benchmark_freeze_path).parent))
    benchmark = load_json(benchmark_freeze_path)
    experience_payload = load_json(experience_store_path)
    tasks = benchmark.get("tasks") if isinstance(benchmark.get("tasks"), list) else []
    tasks = [row for row in tasks if isinstance(row, dict)]

    replay_substrate_compatible = bool(tasks) and all(
        norm(row.get("declared_failure_type"))
        and norm(row.get("error_subtype"))
        and norm(row.get("dominant_stage_subtype"))
        and norm(row.get("residual_signal_cluster"))
        for row in tasks
    )
    planner_conditioning_compatible = bool(tasks) and all(
        norm(row.get("family_id")) and bool(row.get("allowed_patch_types") or row.get("patch_type"))
        for row in tasks
    )
    three_family_benchmark_pack_compatible = bool(benchmark.get("benchmark_freeze_ready")) and int(benchmark.get("benchmark_family_count") or 0) == 3

    legacy_signal_coverage = summarize_signal_coverage(experience_payload)
    task_metrics = [_task_replay_metrics(task, experience_payload) for task in tasks]
    replay_exact_match_task_count = sum(1 for row in task_metrics if bool(row.get("replay_exact_match")))
    replay_rule_ready_task_count = sum(1 for row in task_metrics if bool(row.get("replay_rule_ready")))
    planner_hint_task_count = sum(1 for row in task_metrics if bool(row.get("planner_hint_ready")))
    stage2_conditioning_activation_task_count = sum(
        1 for row in task_metrics if bool(row.get("replay_exact_match")) or bool(row.get("planner_hint_ready"))
    )
    task_count = len(task_metrics)

    family_breakdown: dict[str, dict] = {}
    for row in task_metrics:
        family_id = str(row.get("family_id") or "")
        slot = family_breakdown.setdefault(
            family_id,
            {
                "task_count": 0,
                "replay_exact_match_task_count": 0,
                "replay_rule_ready_task_count": 0,
                "planner_hint_task_count": 0,
            },
        )
        slot["task_count"] = int(slot.get("task_count") or 0) + 1
        if row.get("replay_exact_match"):
            slot["replay_exact_match_task_count"] = int(slot.get("replay_exact_match_task_count") or 0) + 1
        if row.get("replay_rule_ready"):
            slot["replay_rule_ready_task_count"] = int(slot.get("replay_rule_ready_task_count") or 0) + 1
        if row.get("planner_hint_ready"):
            slot["planner_hint_task_count"] = int(slot.get("planner_hint_task_count") or 0) + 1

    if replay_substrate_compatible and planner_conditioning_compatible and three_family_benchmark_pack_compatible:
        conditioning_mode_recommendation = "replay_primary_with_planner_sidecar"
    elif replay_substrate_compatible:
        conditioning_mode_recommendation = "replay_only"
    elif planner_conditioning_compatible:
        conditioning_mode_recommendation = "planner_only"
    else:
        conditioning_mode_recommendation = "none"

    conditioning_reactivation_ready = (
        three_family_benchmark_pack_compatible
        and (replay_substrate_compatible or planner_conditioning_compatible)
        and stage2_conditioning_activation_task_count > 0
    )
    if not three_family_benchmark_pack_compatible:
        primary_bottleneck = "three_family_benchmark_pack_incompatible"
    elif not replay_substrate_compatible and not planner_conditioning_compatible:
        primary_bottleneck = "conditioning_interfaces_incompatible"
    elif stage2_conditioning_activation_task_count <= 0:
        primary_bottleneck = "stage2_aligned_conditioning_signal_missing"
    else:
        primary_bottleneck = "none"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if three_family_benchmark_pack_compatible else "FAIL",
        "benchmark_freeze_path": str(Path(benchmark_freeze_path).resolve()),
        "experience_store_path": str(Path(experience_store_path).resolve()),
        "replay_substrate_compatible": replay_substrate_compatible,
        "planner_conditioning_compatible": planner_conditioning_compatible,
        "three_family_benchmark_pack_compatible": three_family_benchmark_pack_compatible,
        "conditioning_mode_recommendation": conditioning_mode_recommendation,
        "conditioning_reactivation_ready": conditioning_reactivation_ready,
        "task_count": task_count,
        "legacy_signal_coverage": legacy_signal_coverage,
        "replay_exact_match_task_count": replay_exact_match_task_count,
        "replay_rule_ready_task_count": replay_rule_ready_task_count,
        "planner_hint_task_count": planner_hint_task_count,
        "stage2_conditioning_activation_task_count": stage2_conditioning_activation_task_count,
        "replay_exact_match_rate_pct": round(100.0 * replay_exact_match_task_count / float(task_count), 1) if task_count else 0.0,
        "planner_hint_rate_pct": round(100.0 * planner_hint_task_count / float(task_count), 1) if task_count else 0.0,
        "stage2_conditioning_activation_rate_pct": round(100.0 * stage2_conditioning_activation_task_count / float(task_count), 1) if task_count else 0.0,
        "primary_bottleneck": primary_bottleneck,
        "family_breakdown": family_breakdown,
        "task_metrics": task_metrics,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_metrics.json", {"task_metrics": task_metrics})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.0 Conditioning Reactivation Audit",
                "",
                f"- replay_substrate_compatible: `{payload.get('replay_substrate_compatible')}`",
                f"- planner_conditioning_compatible: `{payload.get('planner_conditioning_compatible')}`",
                f"- conditioning_reactivation_ready: `{payload.get('conditioning_reactivation_ready')}`",
                f"- primary_bottleneck: `{payload.get('primary_bottleneck')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.4.0 conditioning reactivation audit.")
    parser.add_argument("--benchmark-freeze", default=str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "benchmark_pack.json"))
    parser.add_argument("--experience-store", default=str(DEFAULT_EXPERIENCE_STORE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v040_conditioning_reactivation_audit(
        benchmark_freeze_path=str(args.benchmark_freeze),
        experience_store_path=str(args.experience_store),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "conditioning_reactivation_ready": payload.get("conditioning_reactivation_ready"), "primary_bottleneck": payload.get("primary_bottleneck")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
