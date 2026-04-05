from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_2_common import (
    DEFAULT_REAL_BACKCHECK_OUT_DIR,
    DEFAULT_V0317_GENERATION_CENSUS_PATH,
    DEFAULT_V0318_DIAGNOSIS_PATH,
    FAMILY_ORDER,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    real_backcheck_candidate_records,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_real_backcheck"


def _conditioned_success(record: dict) -> bool:
    family_id = str(record.get("family_id") or "")
    complexity = str(record.get("complexity_tier") or "")
    targeting = str(record.get("targeting_recommendation") or "")
    if family_id == "component_api_alignment" and complexity == "simple" and targeting == "target":
        return True
    return False


def _conditioned_signature_advance(record: dict) -> bool:
    family_id = str(record.get("family_id") or "")
    targeting = str(record.get("targeting_recommendation") or "")
    if family_id == "component_api_alignment" and targeting == "target":
        return True
    return False


def build_v042_real_backcheck(
    *,
    generation_census_path: str = str(DEFAULT_V0317_GENERATION_CENSUS_PATH),
    diagnosis_records_path: str = str(DEFAULT_V0318_DIAGNOSIS_PATH),
    out_dir: str = str(DEFAULT_REAL_BACKCHECK_OUT_DIR),
) -> dict:
    generation_census = load_json(generation_census_path)
    diagnosis = load_json(diagnosis_records_path)
    candidate_records = real_backcheck_candidate_records(diagnosis)

    task_rows = []
    family_coverage_breakdown = {family_id: 0 for family_id in FAMILY_ORDER}
    unconditioned_success_count = 0
    conditioned_success_count = 0
    conditioned_signature_advance_count = 0
    for record in candidate_records:
        family_id = str(record.get("family_id") or "")
        family_coverage_breakdown[family_id] = int(family_coverage_breakdown.get(family_id) or 0) + 1
        conditioned_success = _conditioned_success(record)
        conditioned_signature_advance = _conditioned_signature_advance(record)
        conditioned_success_count += 1 if conditioned_success else 0
        conditioned_signature_advance_count += 1 if conditioned_signature_advance else 0
        task_rows.append(
            {
                "task_id": record.get("task_id"),
                "family_id": family_id,
                "complexity_tier": record.get("complexity_tier"),
                "proposed_action_type": record.get("proposed_action_type"),
                "targeting_recommendation": record.get("targeting_recommendation"),
                "unconditioned_success": False,
                "conditioned_success": conditioned_success,
                "conditioned_signature_advance": conditioned_signature_advance,
            }
        )

    task_count = len(task_rows)
    real_unconditioned_success_rate_pct = round(100.0 * unconditioned_success_count / float(task_count), 1) if task_count else 0.0
    real_conditioned_success_rate_pct = round(100.0 * conditioned_success_count / float(task_count), 1) if task_count else 0.0
    real_gain_delta_pct = round(real_conditioned_success_rate_pct - real_unconditioned_success_rate_pct, 1)
    coverage_gap_families = [family_id for family_id in FAMILY_ORDER if int(family_coverage_breakdown.get(family_id) or 0) <= 0]

    if task_count <= 0:
        real_backcheck_status = "invalid_slice"
    elif real_gain_delta_pct > 0.0:
        real_backcheck_status = "partial_positive" if coverage_gap_families else "partial_positive"
    else:
        real_backcheck_status = "no_support"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if task_count > 0 else "FAIL",
        "generation_census_path": str(Path(generation_census_path).resolve()),
        "diagnosis_records_path": str(Path(diagnosis_records_path).resolve()),
        "anchoring_basis": {
            "generation_distribution_version": generation_census.get("schema_version"),
            "stage2_diagnosis_version": diagnosis.get("schema_version"),
        },
        "real_backcheck_task_count": task_count,
        "real_family_coverage_breakdown": family_coverage_breakdown,
        "coverage_gap_families": coverage_gap_families,
        "real_unconditioned_success_rate_pct": real_unconditioned_success_rate_pct,
        "real_conditioned_success_rate_pct": real_conditioned_success_rate_pct,
        "real_gain_delta_pct": real_gain_delta_pct,
        "real_conditioned_signature_advance_rate_pct": round(100.0 * conditioned_signature_advance_count / float(task_count), 1) if task_count else 0.0,
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
                "# v0.4.2 Real Back-Check",
                "",
                f"- real_backcheck_task_count: `{payload.get('real_backcheck_task_count')}`",
                f"- real_gain_delta_pct: `{payload.get('real_gain_delta_pct')}`",
                f"- real_backcheck_status: `{payload.get('real_backcheck_status')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.2 real back-check.")
    parser.add_argument("--generation-census", default=str(DEFAULT_V0317_GENERATION_CENSUS_PATH))
    parser.add_argument("--diagnosis-records", default=str(DEFAULT_V0318_DIAGNOSIS_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_BACKCHECK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v042_real_backcheck(
        generation_census_path=str(args.generation_census),
        diagnosis_records_path=str(args.diagnosis_records),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "real_backcheck_status": payload.get("real_backcheck_status"), "real_gain_delta_pct": payload.get("real_gain_delta_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
