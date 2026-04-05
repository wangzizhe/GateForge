from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_0_benchmark_freeze import build_v040_benchmark_freeze
from .agent_modelica_v0_4_0_conditioning_reactivation_audit import build_v040_conditioning_reactivation_audit
from .agent_modelica_v0_4_0_synthetic_baseline import build_v040_synthetic_baseline
from .agent_modelica_v0_4_0_v0_4_1_handoff import build_v040_v0_4_1_handoff
from .agent_modelica_v0_4_0_common import (
    DEFAULT_BENCHMARK_FREEZE_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_CONDITIONING_AUDIT_OUT_DIR,
    DEFAULT_SYNTHETIC_BASELINE_OUT_DIR,
    DEFAULT_V0_4_1_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v040_closeout(
    *,
    benchmark_freeze_path: str = str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "summary.json"),
    conditioning_audit_path: str = str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR / "summary.json"),
    synthetic_baseline_path: str = str(DEFAULT_SYNTHETIC_BASELINE_OUT_DIR / "summary.json"),
    v0_4_1_handoff_path: str = str(DEFAULT_V0_4_1_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(benchmark_freeze_path).exists():
        build_v040_benchmark_freeze(out_dir=str(Path(benchmark_freeze_path).parent))
    if not Path(conditioning_audit_path).exists():
        build_v040_conditioning_reactivation_audit(
            benchmark_freeze_path=str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "benchmark_pack.json"),
            out_dir=str(Path(conditioning_audit_path).parent),
        )
    if not Path(synthetic_baseline_path).exists():
        build_v040_synthetic_baseline(
            benchmark_freeze_path=str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "benchmark_pack.json"),
            conditioning_audit_path=conditioning_audit_path,
            out_dir=str(Path(synthetic_baseline_path).parent),
        )
    if not Path(v0_4_1_handoff_path).exists():
        build_v040_v0_4_1_handoff(
            conditioning_audit_path=conditioning_audit_path,
            synthetic_baseline_path=synthetic_baseline_path,
            out_dir=str(Path(v0_4_1_handoff_path).parent),
        )

    benchmark = load_json(benchmark_freeze_path)
    audit = load_json(conditioning_audit_path)
    baseline = load_json(synthetic_baseline_path)
    handoff = load_json(v0_4_1_handoff_path)

    benchmark_ready = bool(benchmark.get("benchmark_freeze_ready"))
    conditioning_ready = bool(audit.get("conditioning_reactivation_ready"))
    synthetic_baseline_ready = bool(baseline.get("synthetic_gain_measurement_ready"))

    if not benchmark_ready or (not bool(audit.get("replay_substrate_compatible")) and not bool(audit.get("planner_conditioning_compatible"))):
        version_decision = "v0_4_0_conditioning_substrate_not_ready"
    elif not conditioning_ready or not synthetic_baseline_ready:
        version_decision = "v0_4_0_conditioning_substrate_partial"
    else:
        version_decision = "v0_4_0_synthetic_learning_baseline_ready"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_4_0_LEARNING_RESTART_READY",
        "conclusion": {
            "version_decision": version_decision,
            "conditioning_reactivation_ready": conditioning_ready,
            "synthetic_learning_baseline_ready": synthetic_baseline_ready,
            "conditioning_mode": baseline.get("conditioning_mode"),
            "single_mechanism_constraint": bool(baseline.get("single_mechanism_constraint")),
            "real_gain_authority_deferred": True,
            "primary_bottleneck": baseline.get("primary_bottleneck") or audit.get("primary_bottleneck") or "none",
            "v0_4_1_handoff_spec": str(Path(v0_4_1_handoff_path).resolve()),
            "summary": (
                "v0.4.0 restarts learning-effectiveness work with a three-family synthetic baseline."
                if version_decision == "v0_4_0_synthetic_learning_baseline_ready"
                else (
                    "v0.4.0 reactivates the conditioning substrate structurally, but stage_2-aligned conditioning signal is still incomplete."
                    if version_decision == "v0_4_0_conditioning_substrate_partial"
                    else "v0.4.0 cannot yet establish a trustworthy synthetic learning baseline because the conditioning substrate does not attach cleanly to the three-family benchmark."
                )
            ),
        },
        "benchmark_freeze": benchmark,
        "conditioning_reactivation_audit": audit,
        "synthetic_baseline": baseline,
        "v0_4_1_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.0 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- conditioning_reactivation_ready: `{(payload.get('conclusion') or {}).get('conditioning_reactivation_ready')}`",
                f"- synthetic_learning_baseline_ready: `{(payload.get('conclusion') or {}).get('synthetic_learning_baseline_ready')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.0 closeout.")
    parser.add_argument("--benchmark-freeze", default=str(DEFAULT_BENCHMARK_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--conditioning-audit", default=str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--synthetic-baseline", default=str(DEFAULT_SYNTHETIC_BASELINE_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-1-handoff", default=str(DEFAULT_V0_4_1_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v040_closeout(
        benchmark_freeze_path=str(args.benchmark_freeze),
        conditioning_audit_path=str(args.conditioning_audit),
        synthetic_baseline_path=str(args.synthetic_baseline),
        v0_4_1_handoff_path=str(args.v0_4_1_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
