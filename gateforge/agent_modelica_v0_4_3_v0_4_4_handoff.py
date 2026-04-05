from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_3_common import (
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_REAL_BACKCHECK_OUT_DIR,
    DEFAULT_V0_4_4_HANDOFF_OUT_DIR,
    DEFAULT_V042_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_4_4_handoff"


def build_v043_v0_4_4_handoff(
    *,
    v0_4_2_closeout_path: str = str(DEFAULT_V042_CLOSEOUT_PATH),
    real_backcheck_path: str = str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"),
    dispatch_audit_path: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_V0_4_4_HANDOFF_OUT_DIR),
) -> dict:
    v042 = load_json(v0_4_2_closeout_path)
    real = load_json(real_backcheck_path)
    dispatch = load_json(dispatch_audit_path)

    if not bool(dispatch.get("policy_baseline_valid")):
        handoff_mode = "refine_dispatch_policy"
    elif str(real.get("real_backcheck_status") or "") == "supported":
        handoff_mode = "promote_real_authority_evaluation"
    else:
        handoff_mode = "expand_real_slice_again"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "v0_4_2_closeout_path": str(Path(v0_4_2_closeout_path).resolve()),
        "real_backcheck_path": str(Path(real_backcheck_path).resolve()),
        "dispatch_audit_path": str(Path(dispatch_audit_path).resolve()),
        "v0_4_4_handoff_mode": handoff_mode,
        "v0_4_4_primary_eval_question": (
            "Can widened real-distribution support now be promoted from partial transfer evidence to a stronger authority evaluation?"
            if handoff_mode == "promote_real_authority_evaluation"
            else (
                "Which wider targeted real slice is still missing before real transfer support becomes credible?"
                if handoff_mode == "expand_real_slice_again"
                else "Which dispatch-policy change is required to keep widened overlap-case attribution clean enough for authority?"
            )
        ),
        "conditioning_gain_anchor": (v042.get("conclusion") or {}).get("version_decision"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.3 -> v0.4.4 Handoff",
                "",
                f"- v0_4_4_handoff_mode: `{payload.get('v0_4_4_handoff_mode')}`",
                f"- conditioning_gain_anchor: `{payload.get('conditioning_gain_anchor')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.3 -> v0.4.4 handoff.")
    parser.add_argument("--v0-4-2-closeout", default=str(DEFAULT_V042_CLOSEOUT_PATH))
    parser.add_argument("--real-backcheck", default=str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--dispatch-audit", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_4_4_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v043_v0_4_4_handoff(
        v0_4_2_closeout_path=str(args.v0_4_2_closeout),
        real_backcheck_path=str(args.real_backcheck),
        dispatch_audit_path=str(args.dispatch_audit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_4_4_handoff_mode": payload.get("v0_4_4_handoff_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
