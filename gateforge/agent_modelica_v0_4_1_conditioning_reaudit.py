from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from .agent_modelica_v0_4_1_common import (
    DEFAULT_REAUDIT_OUT_DIR,
    DEFAULT_SIGNAL_PACK_OUT_DIR,
    DEFAULT_V040_AUDIT_PATH,
    DEFAULT_V040_BENCHMARK_PATH,
    SCHEMA_PREFIX,
    benchmark_tasks,
    family_counts,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_1_signal_pack import build_v041_signal_pack


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_conditioning_reaudit"


def build_v041_conditioning_reaudit(
    *,
    signal_pack_path: str = str(DEFAULT_SIGNAL_PACK_OUT_DIR / "signal_pack.json"),
    benchmark_path: str = str(DEFAULT_V040_BENCHMARK_PATH),
    legacy_audit_path: str = str(DEFAULT_V040_AUDIT_PATH),
    out_dir: str = str(DEFAULT_REAUDIT_OUT_DIR),
) -> dict:
    if not Path(signal_pack_path).exists():
        build_v041_signal_pack(out_dir=str(Path(signal_pack_path).parent))
    if not Path(benchmark_path).exists():
        build_v040_benchmark_freeze(out_dir=str(Path(benchmark_path).parent))

    signal_pack = load_json(signal_pack_path)
    benchmark = load_json(benchmark_path)
    legacy = load_json(legacy_audit_path)
    tasks = benchmark_tasks(benchmark)
    signal_rows = signal_pack.get("signal_rows") if isinstance(signal_pack.get("signal_rows"), list) else []
    signal_rows = [row for row in signal_rows if isinstance(row, dict)]

    by_family: dict[str, list[dict]] = {}
    for row in signal_rows:
        by_family.setdefault(str(row.get("family_id") or ""), []).append(row)

    family_task_counts = family_counts(tasks)
    refreshed_family_activation: dict[str, dict] = {}
    replay_exact_match_task_count = 0
    planner_hint_task_count = 0
    refreshed_activation_task_count = 0
    for family_id, task_count in family_task_counts.items():
        signal_count = len(by_family.get(family_id) or [])
        replay_family_tasks = min(task_count, signal_count)
        planner_family_tasks = min(task_count, signal_count)
        replay_exact_match_task_count += replay_family_tasks
        planner_hint_task_count += planner_family_tasks
        refreshed_activation_task_count += min(task_count, signal_count)
        refreshed_family_activation[family_id] = {
            "task_count": task_count,
            "exact_signal_count": signal_count,
            "replay_exact_match_task_count": replay_family_tasks,
            "planner_hint_task_count": planner_family_tasks,
        }

    task_count = len(tasks)
    refreshed_stage2_activation_rate_pct = round(100.0 * refreshed_activation_task_count / float(task_count), 1) if task_count else 0.0
    replay_exact_match_rate_pct = round(100.0 * replay_exact_match_task_count / float(task_count), 1) if task_count else 0.0
    planner_hint_rate_pct = round(100.0 * planner_hint_task_count / float(task_count), 1) if task_count else 0.0
    conditioning_reactivation_ready = bool(signal_pack.get("signal_pack_ready")) and refreshed_stage2_activation_rate_pct > 0.0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if bool(signal_pack.get("signal_pack_ready")) else "FAIL",
        "signal_pack_path": str(Path(signal_pack_path).resolve()),
        "benchmark_path": str(Path(benchmark_path).resolve()),
        "legacy_audit_path": str(Path(legacy_audit_path).resolve()),
        "legacy_stage2_activation_rate_pct": float(legacy.get("stage2_conditioning_activation_rate_pct") or 0.0),
        "refreshed_stage2_activation_rate_pct": refreshed_stage2_activation_rate_pct,
        "replay_exact_match_task_count": replay_exact_match_task_count,
        "planner_hint_task_count": planner_hint_task_count,
        "replay_exact_match_rate_pct": replay_exact_match_rate_pct,
        "planner_hint_rate_pct": planner_hint_rate_pct,
        "conditioning_reactivation_ready": conditioning_reactivation_ready,
        "family_activation_breakdown": refreshed_family_activation,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.1 Conditioning Re-Audit",
                "",
                f"- legacy_stage2_activation_rate_pct: `{payload.get('legacy_stage2_activation_rate_pct')}`",
                f"- refreshed_stage2_activation_rate_pct: `{payload.get('refreshed_stage2_activation_rate_pct')}`",
                f"- conditioning_reactivation_ready: `{payload.get('conditioning_reactivation_ready')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.4.1 conditioning re-audit on the refreshed stage-2 signal pack.")
    parser.add_argument("--signal-pack", default=str(DEFAULT_SIGNAL_PACK_OUT_DIR / "signal_pack.json"))
    parser.add_argument("--benchmark", default=str(DEFAULT_V040_BENCHMARK_PATH))
    parser.add_argument("--legacy-audit", default=str(DEFAULT_V040_AUDIT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v041_conditioning_reaudit(
        signal_pack_path=str(args.signal_pack),
        benchmark_path=str(args.benchmark),
        legacy_audit_path=str(args.legacy_audit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "conditioning_reactivation_ready": payload.get("conditioning_reactivation_ready"), "refreshed_stage2_activation_rate_pct": payload.get("refreshed_stage2_activation_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
