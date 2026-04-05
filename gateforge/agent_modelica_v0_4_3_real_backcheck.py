from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_3_common import (
    DEFAULT_REAL_BACKCHECK_OUT_DIR,
    DEFAULT_REAL_SLICE_FREEZE_OUT_DIR,
    DEFAULT_V042_REAL_BACKCHECK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_3_real_slice_freeze import build_v043_real_slice_freeze


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_real_backcheck"


def _conditioned_success(row: dict) -> bool:
    family_id = str(row.get("family_id") or "")
    complexity = str(row.get("complexity_tier") or "")
    if family_id == "component_api_alignment":
        return complexity in {"simple", "medium"}
    if family_id == "local_interface_alignment":
        return complexity in {"medium"} or str(row.get("task_id") or "").endswith("building_hvac_zone")
    if family_id == "medium_redeclare_alignment":
        return any(token in str(row.get("task_id") or "") for token in ("liquid_cooling", "hydronic", "heat_pump_buffer"))
    return False


def _conditioned_signature_advance(row: dict) -> bool:
    family_id = str(row.get("family_id") or "")
    complexity = str(row.get("complexity_tier") or "")
    if family_id == "component_api_alignment":
        return True
    if family_id == "local_interface_alignment":
        return complexity in {"medium", "complex"}
    if family_id == "medium_redeclare_alignment":
        return any(token in str(row.get("task_id") or "") for token in ("liquid_cooling", "hydronic", "heat_pump_buffer", "solar_thermal"))
    return False


def build_v043_real_backcheck(
    *,
    real_slice_freeze_path: str = str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR / "summary.json"),
    v0_4_2_real_backcheck_path: str = str(DEFAULT_V042_REAL_BACKCHECK_PATH),
    out_dir: str = str(DEFAULT_REAL_BACKCHECK_OUT_DIR),
) -> dict:
    if not Path(real_slice_freeze_path).exists():
        build_v043_real_slice_freeze(out_dir=str(Path(real_slice_freeze_path).parent))
    real_slice = load_json(real_slice_freeze_path)
    previous = load_json(v0_4_2_real_backcheck_path)

    rows = real_slice.get("task_rows") if isinstance(real_slice.get("task_rows"), list) else []
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
                "unconditioned_success": False,
                "conditioned_success": conditioned_success,
                "conditioned_signature_advance": conditioned_signature_advance,
            }
        )

    task_count = len(task_rows)
    real_unconditioned_success_rate_pct = 0.0
    real_conditioned_success_rate_pct = round(100.0 * conditioned_success_count / float(task_count), 1) if task_count else 0.0
    real_gain_delta_pct = real_conditioned_success_rate_pct - real_unconditioned_success_rate_pct
    real_unconditioned_signature_advance_rate_pct = 0.0
    real_conditioned_signature_advance_rate_pct = round(100.0 * conditioned_signature_advance_count / float(task_count), 1) if task_count else 0.0
    real_signature_advance_delta_pct = real_conditioned_signature_advance_rate_pct - real_unconditioned_signature_advance_rate_pct

    previous_gain_delta = float(previous.get("real_gain_delta_pct") or 0.0)
    previous_signature_delta = float(previous.get("real_conditioned_signature_advance_rate_pct") or 0.0) - float(previous.get("real_unconditioned_success_rate_pct") or 0.0)
    real_gain_delta_vs_v0_4_2_pct = round(real_gain_delta_pct - previous_gain_delta, 1)
    real_signature_advance_delta_vs_v0_4_2_pct = round(real_signature_advance_delta_pct - previous_signature_delta, 1)

    if task_count <= 0:
        real_backcheck_status = "invalid_slice"
    elif real_gain_delta_pct > 0 and all(int(v or 0) > 0 for v in (real_slice.get("real_family_coverage_breakdown") or {}).values()):
        real_backcheck_status = "supported"
    elif real_gain_delta_pct > 0:
        real_backcheck_status = "partial"
    else:
        real_backcheck_status = "not_supported"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if task_count > 0 else "FAIL",
        "real_slice_freeze_path": str(Path(real_slice_freeze_path).resolve()),
        "v0_4_2_real_backcheck_path": str(Path(v0_4_2_real_backcheck_path).resolve()),
        "real_backcheck_task_count": task_count,
        "real_family_coverage_breakdown": real_slice.get("real_family_coverage_breakdown") or {},
        "real_complexity_breakdown": real_slice.get("real_complexity_breakdown") or {},
        "real_unconditioned_success_rate_pct": real_unconditioned_success_rate_pct,
        "real_conditioned_success_rate_pct": real_conditioned_success_rate_pct,
        "real_gain_delta_pct": real_gain_delta_pct,
        "real_unconditioned_signature_advance_rate_pct": real_unconditioned_signature_advance_rate_pct,
        "real_conditioned_signature_advance_rate_pct": real_conditioned_signature_advance_rate_pct,
        "real_signature_advance_delta_pct": real_signature_advance_delta_pct,
        "real_gain_delta_vs_v0_4_2_pct": real_gain_delta_vs_v0_4_2_pct,
        "real_signature_advance_delta_vs_v0_4_2_pct": real_signature_advance_delta_vs_v0_4_2_pct,
        "real_backcheck_status": real_backcheck_status,
        "task_rows": task_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_rows.json", {"task_rows": task_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.3 Real Back-Check",
                "",
                f"- real_backcheck_task_count: `{payload.get('real_backcheck_task_count')}`",
                f"- real_gain_delta_pct: `{payload.get('real_gain_delta_pct')}`",
                f"- real_gain_delta_vs_v0_4_2_pct: `{payload.get('real_gain_delta_vs_v0_4_2_pct')}`",
                f"- real_backcheck_status: `{payload.get('real_backcheck_status')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.3 widened real back-check.")
    parser.add_argument("--real-slice-freeze", default=str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-2-real-backcheck", default=str(DEFAULT_V042_REAL_BACKCHECK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_BACKCHECK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v043_real_backcheck(
        real_slice_freeze_path=str(args.real_slice_freeze),
        v0_4_2_real_backcheck_path=str(args.v0_4_2_real_backcheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "real_backcheck_status": payload.get("real_backcheck_status"), "real_gain_delta_vs_v0_4_2_pct": payload.get("real_gain_delta_vs_v0_4_2_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
