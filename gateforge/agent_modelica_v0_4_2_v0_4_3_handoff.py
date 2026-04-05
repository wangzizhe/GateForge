from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_2_common import (
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


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_4_3_handoff"


def build_v042_v0_4_3_handoff(
    *,
    synthetic_gain_path: str = str(DEFAULT_SYNTHETIC_GAIN_OUT_DIR / "summary.json"),
    dispatch_audit_path: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    real_backcheck_path: str = str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_V0_4_3_HANDOFF_OUT_DIR),
) -> dict:
    synthetic_gain = load_json(synthetic_gain_path)
    dispatch_audit = load_json(dispatch_audit_path)
    real_backcheck = load_json(real_backcheck_path)

    if not bool(dispatch_audit.get("policy_baseline_valid")):
        handoff_mode = "refine_dispatch_policy"
    elif bool(synthetic_gain.get("conditioning_gain_supported")) and str(real_backcheck.get("real_backcheck_status") or "") == "partial_positive":
        handoff_mode = "expand_real_backcheck"
    elif not bool(synthetic_gain.get("conditioning_gain_supported")):
        handoff_mode = "debug_synthetic_gain_failure"
    else:
        handoff_mode = "expand_real_backcheck"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "synthetic_gain_path": str(Path(synthetic_gain_path).resolve()),
        "dispatch_audit_path": str(Path(dispatch_audit_path).resolve()),
        "real_backcheck_path": str(Path(real_backcheck_path).resolve()),
        "v0_4_3_primary_eval_question": (
            "Can the initial synthetic gain signal survive a broader targeted real back-check while preserving a clean multi-family dispatch baseline?"
            if handoff_mode == "expand_real_backcheck"
            else (
                "Which dispatch policy change is required to make overlap-case attribution clean enough for authority evaluation?"
                if handoff_mode == "refine_dispatch_policy"
                else "Why did refreshed conditioning fail to produce supported synthetic gain on the frozen three-family stage_2 benchmark?"
            )
        ),
        "v0_4_3_handoff_mode": handoff_mode,
        "real_gain_authority_supported": False,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.2 -> v0.4.3 Handoff",
                "",
                f"- v0_4_3_handoff_mode: `{payload.get('v0_4_3_handoff_mode')}`",
                f"- real_gain_authority_supported: `{payload.get('real_gain_authority_supported')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.2 -> v0.4.3 handoff.")
    parser.add_argument("--synthetic-gain", default=str(DEFAULT_SYNTHETIC_GAIN_OUT_DIR / "summary.json"))
    parser.add_argument("--dispatch-audit", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--real-backcheck", default=str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_4_3_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v042_v0_4_3_handoff(
        synthetic_gain_path=str(args.synthetic_gain),
        dispatch_audit_path=str(args.dispatch_audit),
        real_backcheck_path=str(args.real_backcheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_4_3_handoff_mode": payload.get("v0_4_3_handoff_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
