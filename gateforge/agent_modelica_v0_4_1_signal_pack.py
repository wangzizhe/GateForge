from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from .agent_modelica_v0_4_1_common import (
    DEFAULT_SIGNAL_PACK_OUT_DIR,
    DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR,
    DEFAULT_V040_BENCHMARK_PATH,
    MIN_EXACT_SIGNALS_PER_FAMILY,
    SCHEMA_PREFIX,
    benchmark_tasks,
    family_counts,
    family_ready,
    load_json,
    now_utc,
    signal_action_key,
    signal_action_type,
    signal_rule_id,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_1_signal_source_audit import build_v041_signal_source_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_signal_pack"


def _signal_row(task: dict, sequence_idx: int) -> dict:
    family_id = str(task.get("family_id") or "")
    patch_type = str(task.get("patch_type") or "unknown_patch")
    benchmark_task_id = str(task.get("benchmark_task_id") or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "signal_id": f"{benchmark_task_id}|signal_{sequence_idx}",
        "family_id": family_id,
        "benchmark_task_id": benchmark_task_id,
        "source_task_id": str(task.get("source_task_id") or ""),
        "failure_type": str(task.get("declared_failure_type") or ""),
        "error_subtype": str(task.get("error_subtype") or ""),
        "dominant_stage_subtype": str(task.get("dominant_stage_subtype") or ""),
        "residual_signal_cluster": str(task.get("residual_signal_cluster") or ""),
        "rule_id": signal_rule_id(family_id, patch_type),
        "action_key": signal_action_key(family_id, patch_type),
        "action_type": signal_action_type(family_id, patch_type),
        "step_outcome": "advancing",
        "replay_eligible": True,
        "rule_tier": "family_curriculum_signal_rule",
        "task_role": str(task.get("task_role") or ""),
        "allowed_patch_types": list(task.get("allowed_patch_types") or []),
        "patch_type": patch_type,
        "family_target_bucket": str(task.get("family_target_bucket") or ""),
        "signal_origin": "refreshed_stage2_curriculum_extraction",
    }


def build_v041_signal_pack(
    *,
    signal_source_audit_path: str = str(DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR / "summary.json"),
    benchmark_path: str = str(DEFAULT_V040_BENCHMARK_PATH),
    out_dir: str = str(DEFAULT_SIGNAL_PACK_OUT_DIR),
) -> dict:
    if not Path(signal_source_audit_path).exists():
        build_v041_signal_source_audit(
            benchmark_path=benchmark_path,
            out_dir=str(Path(signal_source_audit_path).parent),
        )
    if not Path(benchmark_path).exists():
        build_v040_benchmark_freeze(out_dir=str(Path(benchmark_path).parent))

    audit = load_json(signal_source_audit_path)
    benchmark = load_json(benchmark_path)
    tasks = benchmark_tasks(benchmark)
    signal_rows = [_signal_row(task, idx) for idx, task in enumerate(tasks, start=1)]
    counts_by_family = family_counts(signal_rows)
    signal_pack_ready = bool(audit.get("signal_source_ready")) and family_ready(counts_by_family)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if signal_pack_ready else "FAIL",
        "signal_source_audit_path": str(Path(signal_source_audit_path).resolve()),
        "benchmark_path": str(Path(benchmark_path).resolve()),
        "signal_record_count": len(signal_rows),
        "family_signal_breakdown": counts_by_family,
        "exact_stage2_key_count": 1 if signal_rows else 0,
        "exact_stage2_signal_count_by_family": counts_by_family,
        "min_exact_signals_per_family_required": MIN_EXACT_SIGNALS_PER_FAMILY,
        "signal_pack_ready": signal_pack_ready,
        "signal_rows": signal_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "signal_pack.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.1 Signal Pack",
                "",
                f"- signal_record_count: `{payload.get('signal_record_count')}`",
                f"- signal_pack_ready: `{payload.get('signal_pack_ready')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.1 stage-2 signal pack.")
    parser.add_argument("--signal-source-audit", default=str(DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--benchmark", default=str(DEFAULT_V040_BENCHMARK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_SIGNAL_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v041_signal_pack(
        signal_source_audit_path=str(args.signal_source_audit),
        benchmark_path=str(args.benchmark),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "signal_pack_ready": payload.get("signal_pack_ready"), "signal_record_count": payload.get("signal_record_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
