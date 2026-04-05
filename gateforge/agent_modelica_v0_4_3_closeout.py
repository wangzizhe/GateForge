from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_3_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_REAL_BACKCHECK_OUT_DIR,
    DEFAULT_REAL_SLICE_FREEZE_OUT_DIR,
    DEFAULT_V0_4_4_HANDOFF_OUT_DIR,
    DEFAULT_V042_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_3_dispatch_audit import build_v043_dispatch_audit
from .agent_modelica_v0_4_3_real_backcheck import build_v043_real_backcheck
from .agent_modelica_v0_4_3_real_slice_freeze import build_v043_real_slice_freeze
from .agent_modelica_v0_4_3_v0_4_4_handoff import build_v043_v0_4_4_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def _support_basis(real_slice: dict, real_backcheck: dict, dispatch: dict) -> str:
    if float(real_backcheck.get("real_gain_delta_vs_v0_4_2_pct") or 0.0) > 0 and all(int(v or 0) > 0 for v in (real_slice.get("real_family_coverage_breakdown") or {}).values()):
        return "wider_family_coverage"
    if float(real_backcheck.get("real_signature_advance_delta_vs_v0_4_2_pct") or 0.0) > 0 and int((real_slice.get("real_complexity_breakdown") or {}).get("complex", 0)) > 0:
        return "higher_complexity_coverage"
    if int(real_slice.get("real_slice_task_count") or 0) > 6 and bool(dispatch.get("policy_baseline_valid")):
        return "cleaner_overlap_dispatch"
    return "none"


def build_v043_closeout(
    *,
    v0_4_2_closeout_path: str = str(DEFAULT_V042_CLOSEOUT_PATH),
    real_slice_freeze_path: str = str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR / "summary.json"),
    real_backcheck_path: str = str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"),
    dispatch_audit_path: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    v0_4_4_handoff_path: str = str(DEFAULT_V0_4_4_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(real_slice_freeze_path).exists():
        build_v043_real_slice_freeze(out_dir=str(Path(real_slice_freeze_path).parent))
    if not Path(real_backcheck_path).exists():
        build_v043_real_backcheck(out_dir=str(Path(real_backcheck_path).parent))
    if not Path(dispatch_audit_path).exists():
        build_v043_dispatch_audit(out_dir=str(Path(dispatch_audit_path).parent))
    if not Path(v0_4_4_handoff_path).exists():
        build_v043_v0_4_4_handoff(out_dir=str(Path(v0_4_4_handoff_path).parent))

    v042 = load_json(v0_4_2_closeout_path)
    real_slice = load_json(real_slice_freeze_path)
    real_backcheck = load_json(real_backcheck_path)
    dispatch = load_json(dispatch_audit_path)
    handoff = load_json(v0_4_4_handoff_path)

    policy_baseline_valid = bool(dispatch.get("policy_baseline_valid"))
    real_status = str(real_backcheck.get("real_backcheck_status") or "")
    support_basis = _support_basis(real_slice, real_backcheck, dispatch)

    if not bool(real_slice.get("widened_real_slice_ready")):
        version_decision = "v0_4_3_dispatch_validity_regressed"
        primary_bottleneck = "widened_real_slice_not_ready"
        real_gain_authority_supported = False
    elif not policy_baseline_valid:
        version_decision = "v0_4_3_dispatch_validity_regressed"
        primary_bottleneck = str(dispatch.get("policy_failure_mode") or "dispatch_regression")
        real_gain_authority_supported = False
    elif real_status == "supported":
        version_decision = "v0_4_3_real_backcheck_supported"
        primary_bottleneck = "none"
        real_gain_authority_supported = True
    elif real_status == "partial":
        version_decision = "v0_4_3_real_backcheck_partial"
        primary_bottleneck = "real_transfer_still_partial"
        real_gain_authority_supported = False
    else:
        version_decision = "v0_4_3_real_backcheck_not_supported"
        primary_bottleneck = "widened_real_gain_not_supported"
        real_gain_authority_supported = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_4_3_REAL_BACKCHECK_WIDENING",
        "conclusion": {
            "version_decision": version_decision,
            "conditioning_gain_supported": bool((v042.get("conclusion") or {}).get("conditioning_gain_supported")),
            "policy_baseline_valid": policy_baseline_valid,
            "real_backcheck_status": real_status,
            "real_gain_authority_supported": real_gain_authority_supported,
            "support_basis": support_basis,
            "primary_bottleneck": primary_bottleneck,
            "v0_4_4_handoff_mode": handoff.get("v0_4_4_handoff_mode"),
            "v0_4_4_handoff_spec": str(Path(v0_4_4_handoff_path).resolve()),
        },
        "v0_4_2_closeout": v042,
        "real_slice_freeze": real_slice,
        "real_backcheck": real_backcheck,
        "dispatch_audit": dispatch,
        "v0_4_4_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.3 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- real_backcheck_status: `{(payload.get('conclusion') or {}).get('real_backcheck_status')}`",
                f"- support_basis: `{(payload.get('conclusion') or {}).get('support_basis')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.3 closeout.")
    parser.add_argument("--v0-4-2-closeout", default=str(DEFAULT_V042_CLOSEOUT_PATH))
    parser.add_argument("--real-slice-freeze", default=str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--real-backcheck", default=str(DEFAULT_REAL_BACKCHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--dispatch-audit", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-4-handoff", default=str(DEFAULT_V0_4_4_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v043_closeout(
        v0_4_2_closeout_path=str(args.v0_4_2_closeout),
        real_slice_freeze_path=str(args.real_slice_freeze),
        real_backcheck_path=str(args.real_backcheck),
        dispatch_audit_path=str(args.dispatch_audit),
        v0_4_4_handoff_path=str(args.v0_4_4_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
