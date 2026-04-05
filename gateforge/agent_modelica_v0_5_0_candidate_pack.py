from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_0_common import (
    DEFAULT_CANDIDATE_PACK_OUT_DIR,
    DEFAULT_V043_REAL_SLICE_FREEZE_PATH,
    DEFAULT_WIDENED_SPEC_OUT_DIR,
    MINIMUM_CASE_DELTA_VS_V04_TARGETED,
    MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT,
    MINIMUM_OVERLAP_CASE_REQUIREMENT,
    MINIMUM_QUALITATIVE_CASE_COUNT,
    MINIMUM_QUALITATIVE_CASE_SHARE_PCT,
    SCHEMA_PREFIX,
    classify_real_case,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_candidate_pack"


def build_v050_candidate_pack(
    *,
    widened_spec_path: str = str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"),
    v0_4_3_real_slice_freeze_path: str = str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH),
    out_dir: str = str(DEFAULT_CANDIDATE_PACK_OUT_DIR),
) -> dict:
    spec = load_json(widened_spec_path)
    real_slice = load_json(v0_4_3_real_slice_freeze_path)
    rows = real_slice.get("task_rows") if isinstance(real_slice.get("task_rows"), list) else []
    prior_targeted_count = int(spec.get("v0_4_targeted_real_slice_task_count") or 0)

    frozen_rows = []
    family_breakdown: dict[str, int] = {}
    slice_breakdown = {
        "already-covered": 0,
        "boundary-adjacent": 0,
        "undeclared-but-bounded-candidate": 0,
    }
    complexity_breakdown: dict[str, int] = {}
    qualitative_bucket_breakdown: dict[str, int] = {}
    qualitative_case_count = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "")
        family_id = str(row.get("family_id") or "")
        classification = classify_real_case(task_id, family_id)
        slice_class = classification.get("slice_class") or ""
        if not slice_class:
            continue
        qualitative_bucket = str(classification.get("qualitative_bucket") or "")
        complexity = str(row.get("complexity_tier") or "")
        enriched = dict(row)
        enriched["slice_class"] = slice_class
        enriched["qualitative_bucket"] = qualitative_bucket
        enriched["classification_reason"] = classification.get("reason")
        frozen_rows.append(enriched)

        family_breakdown[family_id] = int(family_breakdown.get(family_id) or 0) + 1
        slice_breakdown[slice_class] = int(slice_breakdown.get(slice_class) or 0) + 1
        complexity_breakdown[complexity] = int(complexity_breakdown.get(complexity) or 0) + 1
        if qualitative_bucket and qualitative_bucket != "none":
            qualitative_case_count += 1
            qualitative_bucket_breakdown[qualitative_bucket] = int(qualitative_bucket_breakdown.get(qualitative_bucket) or 0) + 1

    candidate_count = len(frozen_rows)
    case_delta = max(candidate_count - prior_targeted_count, 0)
    qualitative_case_share_pct = round((100.0 * qualitative_case_count / candidate_count), 1) if candidate_count else 0.0
    distinct_qualitative_bucket_count = len(qualitative_bucket_breakdown)
    overlap_case_count = candidate_count

    quantitative_ok = case_delta >= MINIMUM_CASE_DELTA_VS_V04_TARGETED
    qualitative_ok = (
        qualitative_case_count >= MINIMUM_QUALITATIVE_CASE_COUNT
        and qualitative_case_share_pct >= MINIMUM_QUALITATIVE_CASE_SHARE_PCT
        and distinct_qualitative_bucket_count >= MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT
    )
    overlap_ok = overlap_case_count >= MINIMUM_OVERLAP_CASE_REQUIREMENT
    widened_pack_ready = quantitative_ok and qualitative_ok and overlap_ok

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if widened_pack_ready else "FAIL",
        "widened_spec_path": str(Path(widened_spec_path).resolve()),
        "source_real_slice_freeze_path": str(Path(v0_4_3_real_slice_freeze_path).resolve()),
        "candidate_real_case_count": candidate_count,
        "candidate_family_breakdown": family_breakdown,
        "candidate_slice_class_breakdown": slice_breakdown,
        "candidate_boundary_like_breakdown": qualitative_bucket_breakdown,
        "candidate_complexity_breakdown": complexity_breakdown,
        "case_delta_vs_v0_4_targeted": case_delta,
        "qualitative_case_count": qualitative_case_count,
        "qualitative_case_share_pct": qualitative_case_share_pct,
        "distinct_qualitative_bucket_count": distinct_qualitative_bucket_count,
        "overlap_case_count": overlap_case_count,
        "candidate_slice_classification_rules_frozen": True,
        "widened_pack_ready": widened_pack_ready,
        "task_rows": frozen_rows,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_rows.json", {"task_rows": frozen_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.0 Candidate Pack",
                "",
                f"- candidate_real_case_count: `{candidate_count}`",
                f"- case_delta_vs_v0_4_targeted: `{case_delta}`",
                f"- qualitative_case_count: `{qualitative_case_count}`",
                f"- qualitative_case_share_pct: `{qualitative_case_share_pct}`",
                f"- widened_pack_ready: `{widened_pack_ready}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.0 widened real candidate pack.")
    parser.add_argument("--widened-spec", default=str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-3-real-slice-freeze", default=str(DEFAULT_V043_REAL_SLICE_FREEZE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CANDIDATE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v050_candidate_pack(
        widened_spec_path=str(args.widened_spec),
        v0_4_3_real_slice_freeze_path=str(args.v0_4_3_real_slice_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "candidate_real_case_count": payload.get("candidate_real_case_count"), "widened_pack_ready": payload.get("widened_pack_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
