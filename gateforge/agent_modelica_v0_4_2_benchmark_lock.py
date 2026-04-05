from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_2_common import (
    DEFAULT_BENCHMARK_LOCK_OUT_DIR,
    DEFAULT_V040_BENCHMARK_PATH,
    DEFAULT_V041_HANDOFF_PATH,
    DEFAULT_V041_SIGNAL_PACK_PATH,
    SCHEMA_PREFIX,
    benchmark_task_rows,
    family_counts,
    load_json,
    now_utc,
    policy_baseline,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_benchmark_lock"


def build_v042_benchmark_lock(
    *,
    benchmark_path: str = str(DEFAULT_V040_BENCHMARK_PATH),
    signal_pack_path: str = str(DEFAULT_V041_SIGNAL_PACK_PATH),
    v0_4_1_handoff_path: str = str(DEFAULT_V041_HANDOFF_PATH),
    out_dir: str = str(DEFAULT_BENCHMARK_LOCK_OUT_DIR),
) -> dict:
    benchmark = load_json(benchmark_path)
    signal_pack = load_json(signal_pack_path)
    handoff = load_json(v0_4_1_handoff_path)

    tasks = benchmark_task_rows(benchmark)
    task_count = len(tasks)
    family_task_breakdown = family_counts(tasks)
    signal_count = len(signal_pack.get("signal_rows") if isinstance(signal_pack.get("signal_rows"), list) else [])
    policy_scope = handoff.get("v0_4_2_policy_eval_scope") if isinstance(handoff.get("v0_4_2_policy_eval_scope"), dict) else {}

    baseline = policy_baseline()
    policy_mechanism = str(policy_scope.get("policy_mechanism") or baseline.get("policy_mechanism"))
    dispatch_priority = baseline.get("dispatch_priority")
    dispatch_priority_rule = policy_scope.get("dispatch_priority_rule")
    if not isinstance(dispatch_priority_rule, list) or not dispatch_priority_rule:
        dispatch_priority_rule = [
            "Prefer the narrowest bounded patch contract first.",
            "Default precedence: component_api_alignment -> local_interface_alignment -> medium_redeclare_alignment.",
            "Escalate only if the earlier family does not produce signature advance.",
        ]

    synthetic_benchmark_ready = bool(benchmark.get("benchmark_freeze_ready")) and task_count > 0
    policy_baseline_locked = bool(policy_mechanism) and bool(dispatch_priority) and signal_count >= task_count and task_count > 0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if synthetic_benchmark_ready and policy_baseline_locked else "FAIL",
        "benchmark_path": str(Path(benchmark_path).resolve()),
        "signal_pack_path": str(Path(signal_pack_path).resolve()),
        "v0_4_1_handoff_path": str(Path(v0_4_1_handoff_path).resolve()),
        "synthetic_benchmark_ready": synthetic_benchmark_ready,
        "benchmark_task_count": task_count,
        "family_task_breakdown": family_task_breakdown,
        "policy_baseline_locked": policy_baseline_locked,
        "policy_mechanism": policy_mechanism,
        "dispatch_priority": dispatch_priority,
        "dispatch_priority_rule": dispatch_priority_rule,
        "signal_record_count": signal_count,
        "tasks": tasks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "benchmark_pack.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.2 Benchmark Lock",
                "",
                f"- synthetic_benchmark_ready: `{payload.get('synthetic_benchmark_ready')}`",
                f"- benchmark_task_count: `{payload.get('benchmark_task_count')}`",
                f"- policy_baseline_locked: `{payload.get('policy_baseline_locked')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.2 benchmark lock.")
    parser.add_argument("--benchmark", default=str(DEFAULT_V040_BENCHMARK_PATH))
    parser.add_argument("--signal-pack", default=str(DEFAULT_V041_SIGNAL_PACK_PATH))
    parser.add_argument("--v0-4-1-handoff", default=str(DEFAULT_V041_HANDOFF_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_BENCHMARK_LOCK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v042_benchmark_lock(
        benchmark_path=str(args.benchmark),
        signal_pack_path=str(args.signal_pack),
        v0_4_1_handoff_path=str(args.v0_4_1_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "synthetic_benchmark_ready": payload.get("synthetic_benchmark_ready"), "policy_baseline_locked": payload.get("policy_baseline_locked")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
