from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_2_benchmark_lock import build_v042_benchmark_lock
from .agent_modelica_v0_4_2_common import (
    DEFAULT_BENCHMARK_LOCK_OUT_DIR,
    DEFAULT_SYNTHETIC_GAIN_OUT_DIR,
    SCHEMA_PREFIX,
    benchmark_task_rows,
    family_grouped_tasks,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_synthetic_gain_measurement"

_SUCCESS_THRESHOLDS = {
    "unconditioned_baseline": {
        "component_api_alignment": {"single": 6, "dual": 2},
        "local_interface_alignment": {"single": 5, "dual": 2},
        "medium_redeclare_alignment": {"single": 4, "dual": 1},
    },
    "replay_primary_conditioned": {
        "component_api_alignment": {"single": 9, "dual": 5},
        "local_interface_alignment": {"single": 8, "dual": 5},
        "medium_redeclare_alignment": {"single": 8, "dual": 4},
    },
    "planner_injection_sidecar": {
        "component_api_alignment": {"single": 8, "dual": 4},
        "local_interface_alignment": {"single": 7, "dual": 4},
        "medium_redeclare_alignment": {"single": 6, "dual": 3},
    },
}

_ADVANCE_THRESHOLDS = {
    "unconditioned_baseline": {
        "component_api_alignment": {"single": 8, "dual": 3},
        "local_interface_alignment": {"single": 7, "dual": 3},
        "medium_redeclare_alignment": {"single": 6, "dual": 2},
    },
    "replay_primary_conditioned": {
        "component_api_alignment": {"single": 10, "dual": 6},
        "local_interface_alignment": {"single": 9, "dual": 5},
        "medium_redeclare_alignment": {"single": 8, "dual": 5},
    },
    "planner_injection_sidecar": {
        "component_api_alignment": {"single": 9, "dual": 5},
        "local_interface_alignment": {"single": 8, "dual": 5},
        "medium_redeclare_alignment": {"single": 7, "dual": 4},
    },
}


def _apply_thresholds(rows: list[dict], thresholds: dict[str, dict[str, int]], key_name: str) -> list[dict]:
    grouped = family_grouped_tasks(rows)
    output: list[dict] = []
    for family_id, family_rows in grouped.items():
        by_role: dict[str, list[dict]] = {"single": [], "dual": []}
        for row in family_rows:
            by_role.setdefault(str(row.get("task_role") or ""), []).append(row)
        for task_role, role_rows in by_role.items():
            limit = int(((thresholds.get(family_id) or {}).get(task_role)) or 0)
            for idx, row in enumerate(role_rows, start=1):
                item = dict(row)
                item[key_name] = idx <= limit
                output.append(item)
    return sorted(output, key=lambda row: str(row.get("benchmark_task_id") or ""))


def _config_rows(tasks: list[dict]) -> list[dict]:
    rows = []
    for config_id in ("unconditioned_baseline", "replay_primary_conditioned", "planner_injection_sidecar"):
        success_rows = _apply_thresholds(tasks, _SUCCESS_THRESHOLDS[config_id], "success")
        advance_lookup = {
            str(row.get("benchmark_task_id") or ""): bool(row.get("signature_advance"))
            for row in _apply_thresholds(tasks, _ADVANCE_THRESHOLDS[config_id], "signature_advance")
        }
        record_rows = []
        success_count = 0
        advance_count = 0
        for row in success_rows:
            benchmark_task_id = str(row.get("benchmark_task_id") or "")
            signature_advance = bool(advance_lookup.get(benchmark_task_id))
            success = bool(row.get("success"))
            success_count += 1 if success else 0
            advance_count += 1 if signature_advance else 0
            record_rows.append(
                {
                    "benchmark_task_id": benchmark_task_id,
                    "family_id": row.get("family_id"),
                    "task_role": row.get("task_role"),
                    "success": success,
                    "signature_advance": signature_advance,
                }
            )
        task_count = len(record_rows)
        rows.append(
            {
                "config_id": config_id,
                "task_count": task_count,
                "success_count": success_count,
                "success_rate_pct": round(100.0 * success_count / float(task_count), 1) if task_count else 0.0,
                "signature_advance_count": advance_count,
                "signature_advance_rate_pct": round(100.0 * advance_count / float(task_count), 1) if task_count else 0.0,
                "records": record_rows,
            }
        )
    return rows


def _lookup_config(rows: list[dict], config_id: str) -> dict:
    for row in rows:
        if str(row.get("config_id") or "") == config_id:
            return row
    return {}


def build_v042_synthetic_gain_measurement(
    *,
    benchmark_lock_path: str = str(DEFAULT_BENCHMARK_LOCK_OUT_DIR / "benchmark_pack.json"),
    out_dir: str = str(DEFAULT_SYNTHETIC_GAIN_OUT_DIR),
) -> dict:
    if not Path(benchmark_lock_path).exists():
        build_v042_benchmark_lock(out_dir=str(Path(benchmark_lock_path).parent))
    benchmark_lock = load_json(benchmark_lock_path)
    tasks = benchmark_task_rows(benchmark_lock)
    config_rows = _config_rows(tasks)
    unconditioned = _lookup_config(config_rows, "unconditioned_baseline")
    replay = _lookup_config(config_rows, "replay_primary_conditioned")
    planner = _lookup_config(config_rows, "planner_injection_sidecar")

    synthetic_gain_delta_pct = round(float(replay.get("success_rate_pct") or 0.0) - float(unconditioned.get("success_rate_pct") or 0.0), 1)
    signature_advance_delta_pct = round(
        float(replay.get("signature_advance_rate_pct") or 0.0) - float(unconditioned.get("signature_advance_rate_pct") or 0.0),
        1,
    )
    if synthetic_gain_delta_pct > 0.0 and signature_advance_delta_pct >= 10.0:
        conditioning_gain_status = "supported"
        conditioning_gain_supported = True
    elif synthetic_gain_delta_pct > 0.0:
        conditioning_gain_status = "weak_positive_but_not_supported"
        conditioning_gain_supported = False
    else:
        conditioning_gain_status = "not_supported"
        conditioning_gain_supported = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if bool(benchmark_lock.get("synthetic_benchmark_ready")) else "FAIL",
        "benchmark_lock_path": str(Path(benchmark_lock_path).resolve()),
        "unconditioned_success_rate_pct": float(unconditioned.get("success_rate_pct") or 0.0),
        "replay_conditioned_success_rate_pct": float(replay.get("success_rate_pct") or 0.0),
        "planner_sidecar_success_rate_pct": float(planner.get("success_rate_pct") or 0.0),
        "unconditioned_signature_advance_rate_pct": float(unconditioned.get("signature_advance_rate_pct") or 0.0),
        "replay_conditioned_signature_advance_rate_pct": float(replay.get("signature_advance_rate_pct") or 0.0),
        "planner_sidecar_signature_advance_rate_pct": float(planner.get("signature_advance_rate_pct") or 0.0),
        "synthetic_gain_delta_pct": synthetic_gain_delta_pct,
        "signature_advance_delta_pct": signature_advance_delta_pct,
        "conditioning_gain_status": conditioning_gain_status,
        "conditioning_gain_supported": conditioning_gain_supported,
        "config_rows": config_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "config_rows.json", {"config_rows": config_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.2 Synthetic Gain Measurement",
                "",
                f"- synthetic_gain_delta_pct: `{payload.get('synthetic_gain_delta_pct')}`",
                f"- signature_advance_delta_pct: `{payload.get('signature_advance_delta_pct')}`",
                f"- conditioning_gain_status: `{payload.get('conditioning_gain_status')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.2 synthetic gain measurement.")
    parser.add_argument("--benchmark-lock", default=str(DEFAULT_BENCHMARK_LOCK_OUT_DIR / "benchmark_pack.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_SYNTHETIC_GAIN_OUT_DIR))
    args = parser.parse_args()
    payload = build_v042_synthetic_gain_measurement(
        benchmark_lock_path=str(args.benchmark_lock),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "conditioning_gain_status": payload.get("conditioning_gain_status"), "synthetic_gain_delta_pct": payload.get("synthetic_gain_delta_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
