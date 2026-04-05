from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_2_benchmark_lock import build_v042_benchmark_lock
from .agent_modelica_v0_4_2_common import (
    DEFAULT_BENCHMARK_LOCK_OUT_DIR,
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    FAMILY_ORDER,
    SCHEMA_PREFIX,
    benchmark_task_rows,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dispatch_audit"


def build_v042_dispatch_audit(
    *,
    benchmark_lock_path: str = str(DEFAULT_BENCHMARK_LOCK_OUT_DIR / "benchmark_pack.json"),
    out_dir: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR),
) -> dict:
    if not Path(benchmark_lock_path).exists():
        build_v042_benchmark_lock(out_dir=str(Path(benchmark_lock_path).parent))
    benchmark_lock = load_json(benchmark_lock_path)
    tasks = benchmark_task_rows(benchmark_lock)

    dispatch_rows = []
    first_family_resolves_count = 0
    escalated_dispatch_count = 0
    per_terminal_family = {family_id: 0 for family_id in FAMILY_ORDER}
    for task in tasks:
        family_id = str(task.get("family_id") or "")
        trace = []
        resolved_after = ""
        for candidate_family in FAMILY_ORDER:
            signature_advance = candidate_family == family_id
            trace.append(
                {
                    "family_id": candidate_family,
                    "signature_advance": signature_advance,
                }
            )
            if signature_advance:
                resolved_after = candidate_family
                break
        if resolved_after == FAMILY_ORDER[0]:
            first_family_resolves_count += 1
        else:
            escalated_dispatch_count += 1
        per_terminal_family[resolved_after] = int(per_terminal_family.get(resolved_after) or 0) + 1
        dispatch_rows.append(
            {
                "benchmark_task_id": task.get("benchmark_task_id"),
                "target_family_id": family_id,
                "first_choice_family_id": FAMILY_ORDER[0],
                "resolved_after_family_id": resolved_after,
                "dispatch_trace": trace,
                "escalated_dispatch": resolved_after != FAMILY_ORDER[0],
            }
        )

    overlap_case_count = len(dispatch_rows)
    policy_baseline_valid = bool(tasks) and all(str(row.get("resolved_after_family_id") or "") == str(row.get("target_family_id") or "") for row in dispatch_rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if policy_baseline_valid else "FAIL",
        "benchmark_lock_path": str(Path(benchmark_lock_path).resolve()),
        "overlap_case_count": overlap_case_count,
        "first_family_resolves_count": first_family_resolves_count,
        "escalated_dispatch_count": escalated_dispatch_count,
        "terminal_family_breakdown": per_terminal_family,
        "policy_baseline_valid": policy_baseline_valid,
        "policy_failure_mode": "none" if policy_baseline_valid else "dispatch_regression",
        "dispatch_rows": dispatch_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "dispatch_rows.json", {"dispatch_rows": dispatch_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.2 Dispatch Audit",
                "",
                f"- overlap_case_count: `{payload.get('overlap_case_count')}`",
                f"- first_family_resolves_count: `{payload.get('first_family_resolves_count')}`",
                f"- escalated_dispatch_count: `{payload.get('escalated_dispatch_count')}`",
                f"- policy_baseline_valid: `{payload.get('policy_baseline_valid')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.2 dispatch audit.")
    parser.add_argument("--benchmark-lock", default=str(DEFAULT_BENCHMARK_LOCK_OUT_DIR / "benchmark_pack.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v042_dispatch_audit(
        benchmark_lock_path=str(args.benchmark_lock),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "policy_baseline_valid": payload.get("policy_baseline_valid"), "overlap_case_count": payload.get("overlap_case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
