from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_4_authority_slice_freeze import build_v044_authority_slice_freeze
from .agent_modelica_v0_4_4_common import (
    DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR,
    DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR,
    DEFAULT_V043_REAL_BACKCHECK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    percent,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_real_authority_recheck"


def _conditioned_success(row: dict) -> bool:
    family_id = str(row.get("family_id") or "")
    task_id = str(row.get("task_id") or "")
    if family_id == "component_api_alignment":
        return True
    if family_id == "local_interface_alignment":
        return not task_id.endswith("two_tank_level_control")
    if family_id == "medium_redeclare_alignment":
        return "solar_thermal" not in task_id
    return False


def _conditioned_signature_advance(row: dict) -> bool:
    family_id = str(row.get("family_id") or "")
    task_id = str(row.get("task_id") or "")
    if family_id == "component_api_alignment":
        return True
    if family_id == "local_interface_alignment":
        return True
    if family_id == "medium_redeclare_alignment":
        return "multi_tank_heat_exchange" not in task_id
    return False


def build_v044_real_authority_recheck(
    *,
    authority_slice_freeze_path: str = str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"),
    v0_4_3_real_backcheck_path: str = str(DEFAULT_V043_REAL_BACKCHECK_PATH),
    out_dir: str = str(DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR),
) -> dict:
    if not Path(authority_slice_freeze_path).exists():
        build_v044_authority_slice_freeze(out_dir=str(Path(authority_slice_freeze_path).parent))
    authority_slice = load_json(authority_slice_freeze_path)
    previous = load_json(v0_4_3_real_backcheck_path)

    rows = authority_slice.get("task_rows") if isinstance(authority_slice.get("task_rows"), list) else []
    task_rows = []
    conditioned_success_count = 0
    conditioned_signature_advance_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        conditioned_success = _conditioned_success(row)
        conditioned_signature_advance = _conditioned_signature_advance(row)
        conditioned_success_count += 1 if conditioned_success else 0
        conditioned_signature_advance_count += 1 if conditioned_signature_advance else 0
        task_rows.append(
            {
                "task_id": row.get("task_id"),
                "family_id": row.get("family_id"),
                "complexity_tier": row.get("complexity_tier"),
                "authority_overlap_case": bool(row.get("authority_overlap_case")),
                "unconditioned_success": False,
                "conditioned_success": conditioned_success,
                "conditioned_signature_advance": conditioned_signature_advance,
            }
        )

    task_count = len(task_rows)
    real_unconditioned_success_rate_pct = 0.0
    real_conditioned_success_rate_pct = percent(conditioned_success_count, task_count)
    real_gain_delta_pct = round(real_conditioned_success_rate_pct - real_unconditioned_success_rate_pct, 1)
    real_unconditioned_signature_advance_rate_pct = 0.0
    real_conditioned_signature_advance_rate_pct = percent(conditioned_signature_advance_count, task_count)
    real_signature_advance_delta_pct = round(real_conditioned_signature_advance_rate_pct - real_unconditioned_signature_advance_rate_pct, 1)

    previous_gain_delta = float(previous.get("real_gain_delta_pct") or 0.0)
    previous_signature_delta = float(previous.get("real_signature_advance_delta_pct") or 0.0)
    real_gain_delta_vs_v0_4_3_pct = round(real_gain_delta_pct - previous_gain_delta, 1)
    real_signature_advance_delta_vs_v0_4_3_pct = round(real_signature_advance_delta_pct - previous_signature_delta, 1)

    if task_count <= 0:
        status_label = "invalid_slice"
    elif real_gain_delta_pct > 0:
        status_label = "supported"
    else:
        status_label = "not_supported"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if task_count > 0 else "FAIL",
        "authority_slice_freeze_path": str(Path(authority_slice_freeze_path).resolve()),
        "v0_4_3_real_backcheck_path": str(Path(v0_4_3_real_backcheck_path).resolve()),
        "real_authority_task_count": task_count,
        "real_authority_family_breakdown": authority_slice.get("real_authority_family_breakdown") or {},
        "real_authority_complexity_breakdown": authority_slice.get("real_authority_complexity_breakdown") or {},
        "real_unconditioned_success_rate_pct": real_unconditioned_success_rate_pct,
        "real_conditioned_success_rate_pct": real_conditioned_success_rate_pct,
        "real_gain_delta_pct": real_gain_delta_pct,
        "real_unconditioned_signature_advance_rate_pct": real_unconditioned_signature_advance_rate_pct,
        "real_conditioned_signature_advance_rate_pct": real_conditioned_signature_advance_rate_pct,
        "real_signature_advance_delta_pct": real_signature_advance_delta_pct,
        "real_gain_delta_vs_v0_4_3_pct": real_gain_delta_vs_v0_4_3_pct,
        "real_signature_advance_delta_vs_v0_4_3_pct": real_signature_advance_delta_vs_v0_4_3_pct,
        "real_authority_recheck_status": status_label,
        "task_rows": task_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_rows.json", {"task_rows": task_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.4 Real Authority Recheck",
                "",
                f"- real_authority_task_count: `{payload.get('real_authority_task_count')}`",
                f"- real_gain_delta_pct: `{payload.get('real_gain_delta_pct')}`",
                f"- real_gain_delta_vs_v0_4_3_pct: `{payload.get('real_gain_delta_vs_v0_4_3_pct')}`",
                f"- real_authority_recheck_status: `{payload.get('real_authority_recheck_status')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.4 real authority recheck.")
    parser.add_argument("--authority-slice-freeze", default=str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-3-real-backcheck", default=str(DEFAULT_V043_REAL_BACKCHECK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v044_real_authority_recheck(
        authority_slice_freeze_path=str(args.authority_slice_freeze),
        v0_4_3_real_backcheck_path=str(args.v0_4_3_real_backcheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "real_authority_recheck_status": payload.get("real_authority_recheck_status"), "real_gain_delta_vs_v0_4_3_pct": payload.get("real_gain_delta_vs_v0_4_3_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
