from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_4_authority_dispatch_audit import build_v044_authority_dispatch_audit
from .agent_modelica_v0_4_4_authority_slice_freeze import build_v044_authority_slice_freeze
from .agent_modelica_v0_4_4_common import (
    DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR,
    DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR,
    DEFAULT_V0_4_5_HANDOFF_OUT_DIR,
    DEFAULT_V042_CLOSEOUT_PATH,
    DEFAULT_V043_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_4_promotion_adjudication import build_v044_promotion_adjudication
from .agent_modelica_v0_4_4_real_authority_recheck import build_v044_real_authority_recheck
from .agent_modelica_v0_4_4_v0_4_5_handoff import build_v044_v0_4_5_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v044_closeout(
    *,
    v0_4_2_closeout_path: str = str(DEFAULT_V042_CLOSEOUT_PATH),
    v0_4_3_closeout_path: str = str(DEFAULT_V043_CLOSEOUT_PATH),
    authority_slice_freeze_path: str = str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"),
    real_authority_recheck_path: str = str(DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR / "summary.json"),
    authority_dispatch_audit_path: str = str(DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    promotion_adjudication_path: str = str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR / "summary.json"),
    v0_4_5_handoff_path: str = str(DEFAULT_V0_4_5_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(authority_slice_freeze_path).exists():
        build_v044_authority_slice_freeze(out_dir=str(Path(authority_slice_freeze_path).parent))
    if not Path(real_authority_recheck_path).exists():
        build_v044_real_authority_recheck(out_dir=str(Path(real_authority_recheck_path).parent))
    if not Path(authority_dispatch_audit_path).exists():
        build_v044_authority_dispatch_audit(out_dir=str(Path(authority_dispatch_audit_path).parent))
    if not Path(promotion_adjudication_path).exists():
        build_v044_promotion_adjudication(out_dir=str(Path(promotion_adjudication_path).parent))
    if not Path(v0_4_5_handoff_path).exists():
        build_v044_v0_4_5_handoff(out_dir=str(Path(v0_4_5_handoff_path).parent))

    v042 = load_json(v0_4_2_closeout_path)
    v043 = load_json(v0_4_3_closeout_path)
    authority_slice = load_json(authority_slice_freeze_path)
    real_recheck = load_json(real_authority_recheck_path)
    dispatch = load_json(authority_dispatch_audit_path)
    promotion = load_json(promotion_adjudication_path)
    handoff = load_json(v0_4_5_handoff_path)

    policy_baseline_valid = bool(dispatch.get("policy_baseline_valid"))
    real_status = str(real_recheck.get("real_authority_recheck_status") or "")
    promoted = bool(promotion.get("real_authority_upgrade_supported"))

    if not policy_baseline_valid:
        version_decision = "v0_4_4_policy_validity_regressed"
        primary_bottleneck = str(dispatch.get("policy_failure_mode") or "authority_dispatch_regression")
    elif real_status == "not_supported":
        version_decision = "v0_4_4_real_authority_regressed"
        primary_bottleneck = "real_authority_recheck_not_supported"
    elif promoted:
        version_decision = "v0_4_4_real_authority_promoted"
        primary_bottleneck = "none"
    else:
        version_decision = "v0_4_4_real_authority_supported_but_not_promoted"
        primary_bottleneck = "authority_basis_still_insufficient"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_4_4_REAL_AUTHORITY_EVALUATION",
        "conclusion": {
            "version_decision": version_decision,
            "conditioning_gain_supported": bool((v042.get("conclusion") or {}).get("conditioning_gain_supported")),
            "policy_baseline_valid": policy_baseline_valid,
            "real_backcheck_status": real_status,
            "real_authority_upgrade_supported": promoted,
            "promotion_basis": promotion.get("promotion_basis"),
            "primary_bottleneck": primary_bottleneck,
            "v0_4_5_handoff_mode": handoff.get("v0_4_5_handoff_mode"),
            "v0_4_5_handoff_spec": str(Path(v0_4_5_handoff_path).resolve()),
        },
        "v0_4_2_closeout": v042,
        "v0_4_3_closeout": v043,
        "authority_slice_freeze": authority_slice,
        "real_authority_recheck": real_recheck,
        "authority_dispatch_audit": dispatch,
        "promotion_adjudication": promotion,
        "v0_4_5_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.4 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- real_backcheck_status: `{(payload.get('conclusion') or {}).get('real_backcheck_status')}`",
                f"- promotion_basis: `{(payload.get('conclusion') or {}).get('promotion_basis')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.4 closeout.")
    parser.add_argument("--v0-4-2-closeout", default=str(DEFAULT_V042_CLOSEOUT_PATH))
    parser.add_argument("--v0-4-3-closeout", default=str(DEFAULT_V043_CLOSEOUT_PATH))
    parser.add_argument("--authority-slice-freeze", default=str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--real-authority-recheck", default=str(DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--authority-dispatch-audit", default=str(DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--promotion-adjudication", default=str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-5-handoff", default=str(DEFAULT_V0_4_5_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v044_closeout(
        v0_4_2_closeout_path=str(args.v0_4_2_closeout),
        v0_4_3_closeout_path=str(args.v0_4_3_closeout),
        authority_slice_freeze_path=str(args.authority_slice_freeze),
        real_authority_recheck_path=str(args.real_authority_recheck),
        authority_dispatch_audit_path=str(args.authority_dispatch_audit),
        promotion_adjudication_path=str(args.promotion_adjudication),
        v0_4_5_handoff_path=str(args.v0_4_5_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
