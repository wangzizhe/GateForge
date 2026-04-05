from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_2_benchmark_lock import build_v042_benchmark_lock
from .agent_modelica_v0_4_2_common import (
    DEFAULT_BENCHMARK_LOCK_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_REAL_BACKCHECK_OUT_DIR,
    DEFAULT_SYNTHETIC_GAIN_OUT_DIR,
    DEFAULT_V0_4_3_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_2_dispatch_audit import build_v042_dispatch_audit
from .agent_modelica_v0_4_2_real_backcheck import build_v042_real_backcheck
from .agent_modelica_v0_4_2_synthetic_gain_measurement import build_v042_synthetic_gain_measurement
from .agent_modelica_v0_4_2_v0_4_3_handoff import build_v042_v0_4_3_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v042_closeout(
    *,
    benchmark_lock_path: str = str(DEFAULT_BENCHMARK_LOCK_OUT_DIR / "summary.json"),
    synthetic_gain_path: str = str(DEFAULT_SYNTHETIC_GAIN_OUT_DIR / "summary.json"),
    dispatch_audit_path: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    real_backcheck_path: str = str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"),
    v0_4_3_handoff_path: str = str(DEFAULT_V0_4_3_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(benchmark_lock_path).exists():
        build_v042_benchmark_lock(out_dir=str(Path(benchmark_lock_path).parent))
    if not Path(synthetic_gain_path).exists():
        build_v042_synthetic_gain_measurement(out_dir=str(Path(synthetic_gain_path).parent))
    if not Path(dispatch_audit_path).exists():
        build_v042_dispatch_audit(out_dir=str(Path(dispatch_audit_path).parent))
    if not Path(real_backcheck_path).exists():
        build_v042_real_backcheck(out_dir=str(Path(real_backcheck_path).parent))
    if not Path(v0_4_3_handoff_path).exists():
        build_v042_v0_4_3_handoff(out_dir=str(Path(v0_4_3_handoff_path).parent))

    benchmark_lock = load_json(benchmark_lock_path)
    synthetic_gain = load_json(synthetic_gain_path)
    dispatch_audit = load_json(dispatch_audit_path)
    real_backcheck = load_json(real_backcheck_path)
    handoff = load_json(v0_4_3_handoff_path)

    policy_baseline_valid = bool(dispatch_audit.get("policy_baseline_valid"))
    conditioning_gain_supported = bool(synthetic_gain.get("conditioning_gain_supported"))
    real_backcheck_status = str(real_backcheck.get("real_backcheck_status") or "")

    if not bool(benchmark_lock.get("synthetic_benchmark_ready")) or not bool(benchmark_lock.get("policy_baseline_locked")):
        version_decision = "v0_4_2_policy_baseline_invalid"
        primary_bottleneck = "benchmark_or_policy_lock_invalid"
    elif not policy_baseline_valid:
        version_decision = "v0_4_2_policy_baseline_invalid"
        primary_bottleneck = str(dispatch_audit.get("policy_failure_mode") or "dispatch_regression")
    elif not conditioning_gain_supported:
        version_decision = "v0_4_2_synthetic_gain_not_supported"
        primary_bottleneck = str(synthetic_gain.get("conditioning_gain_status") or "synthetic_gain_not_supported")
    elif real_backcheck_status == "partial_positive":
        version_decision = "v0_4_2_synthetic_gain_supported_real_backcheck_partial"
        primary_bottleneck = "real_backcheck_still_partial"
    elif real_backcheck_status == "no_support":
        version_decision = "v0_4_2_synthetic_gain_supported_real_backcheck_not_supported"
        primary_bottleneck = "real_backcheck_no_support"
    else:
        version_decision = "v0_4_2_policy_baseline_invalid"
        primary_bottleneck = "real_backcheck_invalid_slice"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_4_2_LEARNING_EFFECTIVENESS_FIRST_AUTHORITY",
        "conclusion": {
            "version_decision": version_decision,
            "conditioning_gain_supported": conditioning_gain_supported,
            "policy_baseline_valid": policy_baseline_valid,
            "real_backcheck_status": real_backcheck_status,
            "real_gain_authority_supported": False,
            "primary_bottleneck": primary_bottleneck,
            "v0_4_3_primary_eval_question": handoff.get("v0_4_3_primary_eval_question"),
            "v0_4_3_handoff_mode": handoff.get("v0_4_3_handoff_mode"),
            "v0_4_3_handoff_spec": str(Path(v0_4_3_handoff_path).resolve()),
        },
        "benchmark_lock": benchmark_lock,
        "synthetic_gain_measurement": synthetic_gain,
        "dispatch_audit": dispatch_audit,
        "real_backcheck": real_backcheck,
        "v0_4_3_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.2 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- conditioning_gain_supported: `{(payload.get('conclusion') or {}).get('conditioning_gain_supported')}`",
                f"- real_backcheck_status: `{(payload.get('conclusion') or {}).get('real_backcheck_status')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.2 closeout.")
    parser.add_argument("--benchmark-lock", default=str(DEFAULT_BENCHMARK_LOCK_OUT_DIR / "summary.json"))
    parser.add_argument("--synthetic-gain", default=str(DEFAULT_SYNTHETIC_GAIN_OUT_DIR / "summary.json"))
    parser.add_argument("--dispatch-audit", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--real-backcheck", default=str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-3-handoff", default=str(DEFAULT_V0_4_3_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v042_closeout(
        benchmark_lock_path=str(args.benchmark_lock),
        synthetic_gain_path=str(args.synthetic_gain),
        dispatch_audit_path=str(args.dispatch_audit),
        real_backcheck_path=str(args.real_backcheck),
        v0_4_3_handoff_path=str(args.v0_4_3_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
