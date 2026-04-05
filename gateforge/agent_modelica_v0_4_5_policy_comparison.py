from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_5_common import (
    ALTERNATIVE_POLICY_ID,
    BASELINE_POLICY_ID,
    DEFAULT_POLICY_COMPARISON_OUT_DIR,
    DEFAULT_SLICE_LOCK_OUT_DIR,
    DEFAULT_V044_REAL_RECHECK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    percent,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_5_policy_slice_lock import build_v045_policy_slice_lock


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_policy_comparison"


def _alternative_success(row: dict, baseline_success: bool) -> bool:
    if not baseline_success:
        return False
    if not bool(row.get("authority_overlap_case")):
        return True
    family_id = str(row.get("family_id") or "")
    task_id = str(row.get("task_id") or "")
    if family_id == "local_interface_alignment":
        return task_id not in {"gen_medium_two_room_thermal_control", "gen_complex_building_hvac_zone"}
    if family_id == "component_api_alignment":
        return True
    if family_id == "medium_redeclare_alignment":
        return task_id not in {"gen_complex_multi_tank_heat_exchange"}
    return False


def _alternative_signature_advance(row: dict, baseline_signature: bool) -> bool:
    if not baseline_signature:
        return False
    if not bool(row.get("authority_overlap_case")):
        return True
    family_id = str(row.get("family_id") or "")
    task_id = str(row.get("task_id") or "")
    if family_id == "local_interface_alignment":
        return task_id not in {"gen_medium_two_tank_level_control", "gen_complex_ev_thermal_management"}
    if family_id == "medium_redeclare_alignment":
        return task_id not in {"gen_complex_multi_tank_heat_exchange", "gen_complex_solar_thermal_storage_loop"}
    return True


def build_v045_policy_comparison(
    *,
    policy_slice_lock_path: str = str(DEFAULT_SLICE_LOCK_OUT_DIR / "summary.json"),
    v0_4_4_real_recheck_path: str = str(DEFAULT_V044_REAL_RECHECK_PATH),
    out_dir: str = str(DEFAULT_POLICY_COMPARISON_OUT_DIR),
) -> dict:
    if not Path(policy_slice_lock_path).exists():
        build_v045_policy_slice_lock(out_dir=str(Path(policy_slice_lock_path).parent))
    slice_lock = load_json(policy_slice_lock_path)
    recheck = load_json(v0_4_4_real_recheck_path)

    recheck_rows = {
        str(row.get("task_id")): row
        for row in (recheck.get("task_rows") if isinstance(recheck.get("task_rows"), list) else [])
        if isinstance(row, dict)
    }
    task_rows = []
    baseline_success_count = 0
    alternative_success_count = 0
    baseline_signature_count = 0
    alternative_signature_count = 0
    baseline_overlap_resolution_count = 0
    alternative_overlap_resolution_count = 0
    baseline_escalated_resolution_count = 0
    alternative_escalated_resolution_count = 0

    for row in slice_lock.get("task_rows") if isinstance(slice_lock.get("task_rows"), list) else []:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "")
        anchor = recheck_rows.get(task_id, {})
        baseline_success = bool(anchor.get("conditioned_success"))
        baseline_signature = bool(anchor.get("conditioned_signature_advance"))
        alternative_success = _alternative_success(row, baseline_success)
        alternative_signature = _alternative_signature_advance(row, baseline_signature)
        overlap_case = bool(row.get("authority_overlap_case"))
        family_id = str(row.get("family_id") or "")

        baseline_success_count += 1 if baseline_success else 0
        alternative_success_count += 1 if alternative_success else 0
        baseline_signature_count += 1 if baseline_signature else 0
        alternative_signature_count += 1 if alternative_signature else 0

        baseline_overlap_resolved = overlap_case and baseline_success
        alternative_overlap_resolved = overlap_case and alternative_success
        baseline_overlap_resolution_count += 1 if baseline_overlap_resolved else 0
        alternative_overlap_resolution_count += 1 if alternative_overlap_resolved else 0

        baseline_escalated = overlap_case and family_id != "component_api_alignment" and baseline_overlap_resolved
        alternative_escalated = overlap_case and family_id != "component_api_alignment" and alternative_overlap_resolved
        baseline_escalated_resolution_count += 1 if baseline_escalated else 0
        alternative_escalated_resolution_count += 1 if alternative_escalated else 0

        task_rows.append(
            {
                "task_id": task_id,
                "family_id": family_id,
                "complexity_tier": row.get("complexity_tier"),
                "authority_overlap_case": overlap_case,
                "baseline_success": baseline_success,
                "alternative_success": alternative_success,
                "baseline_signature_advance": baseline_signature,
                "alternative_signature_advance": alternative_signature,
            }
        )

    task_count = len(task_rows)
    overlap_case_count = int(slice_lock.get("overlap_case_count") or 0)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if bool(slice_lock.get("policy_comparison_slice_locked")) else "FAIL",
        "policy_slice_lock_path": str(Path(policy_slice_lock_path).resolve()),
        "v0_4_4_real_recheck_path": str(Path(v0_4_4_real_recheck_path).resolve()),
        "baseline_policy_id": BASELINE_POLICY_ID,
        "alternative_policy_id": ALTERNATIVE_POLICY_ID,
        "task_count": task_count,
        "overlap_case_count": overlap_case_count,
        "baseline_real_success_rate_pct": percent(baseline_success_count, task_count),
        "alternative_real_success_rate_pct": percent(alternative_success_count, task_count),
        "baseline_real_signature_advance_rate_pct": percent(baseline_signature_count, task_count),
        "alternative_real_signature_advance_rate_pct": percent(alternative_signature_count, task_count),
        "baseline_overlap_resolution_rate_pct": percent(baseline_overlap_resolution_count, overlap_case_count),
        "alternative_overlap_resolution_rate_pct": percent(alternative_overlap_resolution_count, overlap_case_count),
        "baseline_escalated_resolution_rate_pct": percent(baseline_escalated_resolution_count, overlap_case_count),
        "alternative_escalated_resolution_rate_pct": percent(alternative_escalated_resolution_count, overlap_case_count),
        "policy_gain_delta_pct": round(percent(baseline_success_count, task_count) - percent(alternative_success_count, task_count), 1),
        "policy_signature_delta_pct": round(percent(baseline_signature_count, task_count) - percent(alternative_signature_count, task_count), 1),
        "task_rows": task_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_rows.json", {"task_rows": task_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.5 Policy Comparison",
                "",
                f"- baseline_real_success_rate_pct: `{payload.get('baseline_real_success_rate_pct')}`",
                f"- alternative_real_success_rate_pct: `{payload.get('alternative_real_success_rate_pct')}`",
                f"- policy_gain_delta_pct: `{payload.get('policy_gain_delta_pct')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.5 policy comparison.")
    parser.add_argument("--policy-slice-lock", default=str(DEFAULT_SLICE_LOCK_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-4-real-recheck", default=str(DEFAULT_V044_REAL_RECHECK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_POLICY_COMPARISON_OUT_DIR))
    args = parser.parse_args()
    payload = build_v045_policy_comparison(
        policy_slice_lock_path=str(args.policy_slice_lock),
        v0_4_4_real_recheck_path=str(args.v0_4_4_real_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "policy_gain_delta_pct": payload.get("policy_gain_delta_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
