from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from .agent_modelica_v0_4_0_conditioning_reactivation_audit import build_v040_conditioning_reactivation_audit
from .agent_modelica_v0_4_0_common import (
    DEFAULT_BENCHMARK_FREEZE_OUT_DIR,
    DEFAULT_CONDITIONING_AUDIT_OUT_DIR,
    DEFAULT_SYNTHETIC_BASELINE_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_synthetic_baseline"


def build_v040_synthetic_baseline(
    *,
    benchmark_freeze_path: str = str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "benchmark_pack.json"),
    conditioning_audit_path: str = str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_SYNTHETIC_BASELINE_OUT_DIR),
) -> dict:
    if not Path(benchmark_freeze_path).exists():
        build_v040_benchmark_freeze(out_dir=str(Path(benchmark_freeze_path).parent))
    if not Path(conditioning_audit_path).exists():
        build_v040_conditioning_reactivation_audit(
            benchmark_freeze_path=benchmark_freeze_path,
            out_dir=str(Path(conditioning_audit_path).parent),
        )

    benchmark = load_json(benchmark_freeze_path)
    audit = load_json(conditioning_audit_path)
    task_count = int(benchmark.get("benchmark_task_count") or 0)

    replay_compatible = bool(audit.get("replay_substrate_compatible"))
    planner_compatible = bool(audit.get("planner_conditioning_compatible"))
    if replay_compatible and planner_compatible:
        conditioning_mode = "replay_primary_with_planner_sidecar"
        single_mechanism_constraint = False
    elif replay_compatible:
        conditioning_mode = "replay_only"
        single_mechanism_constraint = True
    elif planner_compatible:
        conditioning_mode = "planner_only"
        single_mechanism_constraint = True
    else:
        conditioning_mode = "none"
        single_mechanism_constraint = False

    config_rows = [
        {
            "config_id": "unconditioned_baseline",
            "task_count": task_count,
            "conditioning_enabled": False,
            "conditioning_signal_task_count": 0,
            "notes": "Synthetic baseline control; no replay or planner experience context attached.",
        }
    ]
    if replay_compatible:
        config_rows.append(
            {
                "config_id": "replay_conditioned",
                "task_count": task_count,
                "conditioning_enabled": True,
                "conditioning_kind": "replay",
                "conditioning_signal_task_count": int(audit.get("replay_exact_match_task_count") or 0),
                "rule_ready_task_count": int(audit.get("replay_rule_ready_task_count") or 0),
            }
        )
    if planner_compatible:
        config_rows.append(
            {
                "config_id": "planner_conditioned_sidecar" if replay_compatible else "planner_conditioned",
                "task_count": task_count,
                "conditioning_enabled": True,
                "conditioning_kind": "planner_injection",
                "conditioning_signal_task_count": int(audit.get("planner_hint_task_count") or 0),
            }
        )

    synthetic_gain_measurement_ready = bool(audit.get("conditioning_reactivation_ready"))
    if not replay_compatible and not planner_compatible:
        primary_bottleneck = "conditioning_interfaces_incompatible"
    else:
        primary_bottleneck = str(audit.get("primary_bottleneck") or "none")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if bool(benchmark.get("benchmark_freeze_ready")) else "FAIL",
        "benchmark_freeze_path": str(Path(benchmark_freeze_path).resolve()),
        "conditioning_audit_path": str(Path(conditioning_audit_path).resolve()),
        "conditioning_mode": conditioning_mode,
        "single_mechanism_constraint": single_mechanism_constraint,
        "synthetic_gain_measurement_ready": synthetic_gain_measurement_ready,
        "synthetic_gain_supported": "inconclusive" if synthetic_gain_measurement_ready else "inconclusive",
        "primary_gain_axis": "stage2_conditioning_activation_rate_pct" if replay_compatible or planner_compatible else "",
        "primary_bottleneck": primary_bottleneck,
        "config_rows": config_rows,
        "baseline_task_count": task_count,
        "stage2_conditioning_activation_rate_pct": float(audit.get("stage2_conditioning_activation_rate_pct") or 0.0),
        "replay_exact_match_rate_pct": float(audit.get("replay_exact_match_rate_pct") or 0.0),
        "planner_hint_rate_pct": float(audit.get("planner_hint_rate_pct") or 0.0),
        "summary": (
            "Synthetic comparison configs are frozen, but stage_2-aligned conditioning signal is still missing."
            if not synthetic_gain_measurement_ready
            else "Synthetic conditioning configs are frozen and at least one stage_2-aligned measurement axis is available for comparison."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.0 Synthetic Baseline",
                "",
                f"- conditioning_mode: `{payload.get('conditioning_mode')}`",
                f"- synthetic_gain_measurement_ready: `{payload.get('synthetic_gain_measurement_ready')}`",
                f"- primary_bottleneck: `{payload.get('primary_bottleneck')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.0 synthetic learning baseline.")
    parser.add_argument("--benchmark-freeze", default=str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "benchmark_pack.json"))
    parser.add_argument("--conditioning-audit", default=str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_SYNTHETIC_BASELINE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v040_synthetic_baseline(
        benchmark_freeze_path=str(args.benchmark_freeze),
        conditioning_audit_path=str(args.conditioning_audit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "synthetic_gain_measurement_ready": payload.get("synthetic_gain_measurement_ready"), "conditioning_mode": payload.get("conditioning_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
