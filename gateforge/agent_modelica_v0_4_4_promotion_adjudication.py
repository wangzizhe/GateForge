from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_4_authority_dispatch_audit import build_v044_authority_dispatch_audit
from .agent_modelica_v0_4_4_authority_slice_freeze import build_v044_authority_slice_freeze
from .agent_modelica_v0_4_4_common import (
    DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR,
    DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR,
    DEFAULT_V043_REAL_SLICE_FREEZE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_4_real_authority_recheck import build_v044_real_authority_recheck
from .agent_modelica_v0_4_4_common import DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_promotion_adjudication"


def build_v044_promotion_adjudication(
    *,
    v0_4_3_real_slice_freeze_path: str = str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH),
    authority_slice_freeze_path: str = str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"),
    real_authority_recheck_path: str = str(DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR / "summary.json"),
    authority_dispatch_audit_path: str = str(DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(authority_slice_freeze_path).exists():
        build_v044_authority_slice_freeze(out_dir=str(Path(authority_slice_freeze_path).parent))
    if not Path(real_authority_recheck_path).exists():
        build_v044_real_authority_recheck(out_dir=str(Path(real_authority_recheck_path).parent))
    if not Path(authority_dispatch_audit_path).exists():
        build_v044_authority_dispatch_audit(out_dir=str(Path(authority_dispatch_audit_path).parent))

    previous_slice = load_json(v0_4_3_real_slice_freeze_path)
    authority_slice = load_json(authority_slice_freeze_path)
    real_recheck = load_json(real_authority_recheck_path)
    dispatch = load_json(authority_dispatch_audit_path)

    current_complex_density = float(authority_slice.get("complex_density_pct") or 0.0)
    previous_complex_density = float(authority_slice.get("v0_4_3_complex_density_pct") or 0.0)
    current_overlap_density = float(authority_slice.get("overlap_density_pct") or 0.0)
    previous_overlap_density = float(authority_slice.get("v0_4_3_overlap_density_pct") or 0.0)
    previous_task_count = int(previous_slice.get("real_slice_task_count") or 0)
    current_task_count = int(authority_slice.get("real_authority_slice_task_count") or 0)

    floor_ok = float(real_recheck.get("real_gain_delta_pct") or 0.0) > 0 and bool(dispatch.get("policy_baseline_valid"))
    quant_support: dict[str, float | int] = {}
    if current_complex_density > previous_complex_density:
        promotion_basis = "higher_complexity_coverage"
        quant_support = {
            "complex_density_pct": current_complex_density,
            "v0_4_3_complex_density_pct": previous_complex_density,
            "complex_density_delta_pct": round(current_complex_density - previous_complex_density, 1),
        }
    elif current_overlap_density > previous_overlap_density:
        promotion_basis = "denser_overlap_authority"
        quant_support = {
            "overlap_density_pct": current_overlap_density,
            "v0_4_3_overlap_density_pct": previous_overlap_density,
            "overlap_density_delta_pct": round(current_overlap_density - previous_overlap_density, 1),
        }
    elif current_task_count > previous_task_count:
        promotion_basis = "wider_family_coverage"
        quant_support = {
            "real_authority_slice_task_count": current_task_count,
            "v0_4_3_real_slice_task_count": previous_task_count,
            "task_count_delta": current_task_count - previous_task_count,
        }
    elif float(dispatch.get("attribution_ambiguity_rate_pct") or 0.0) == 0.0:
        promotion_basis = "cleaner_dispatch_under_pressure"
        quant_support = {
            "attribution_ambiguity_rate_pct": float(dispatch.get("attribution_ambiguity_rate_pct") or 0.0),
            "overlap_case_count": int(dispatch.get("overlap_case_count") or 0),
        }
    else:
        promotion_basis = "none"

    real_authority_upgrade_supported = bool(
        floor_ok
        and float(real_recheck.get("real_signature_advance_delta_pct") or 0.0) > 0.0
        and promotion_basis != "none"
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if floor_ok else "FAIL",
        "v0_4_3_real_slice_freeze_path": str(Path(v0_4_3_real_slice_freeze_path).resolve()),
        "authority_slice_freeze_path": str(Path(authority_slice_freeze_path).resolve()),
        "real_authority_recheck_path": str(Path(real_authority_recheck_path).resolve()),
        "authority_dispatch_audit_path": str(Path(authority_dispatch_audit_path).resolve()),
        "promotion_basis": promotion_basis,
        "promotion_basis_quantitative_support": quant_support,
        "real_authority_upgrade_supported": real_authority_upgrade_supported,
        "promotion_floor_satisfied": floor_ok,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.4 Promotion Adjudication",
                "",
                f"- promotion_basis: `{payload.get('promotion_basis')}`",
                f"- real_authority_upgrade_supported: `{payload.get('real_authority_upgrade_supported')}`",
                f"- promotion_floor_satisfied: `{payload.get('promotion_floor_satisfied')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.4 promotion adjudication.")
    parser.add_argument("--v0-4-3-real-slice-freeze", default=str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH))
    parser.add_argument("--authority-slice-freeze", default=str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--real-authority-recheck", default=str(DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--authority-dispatch-audit", default=str(DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v044_promotion_adjudication(
        v0_4_3_real_slice_freeze_path=str(args.v0_4_3_real_slice_freeze),
        authority_slice_freeze_path=str(args.authority_slice_freeze),
        real_authority_recheck_path=str(args.real_authority_recheck),
        authority_dispatch_audit_path=str(args.authority_dispatch_audit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "promotion_basis": payload.get("promotion_basis"), "real_authority_upgrade_supported": payload.get("real_authority_upgrade_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
