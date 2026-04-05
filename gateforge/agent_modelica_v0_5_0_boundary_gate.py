from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_0_common import (
    DEFAULT_BOUNDARY_GATE_OUT_DIR,
    DEFAULT_CANDIDATE_PACK_OUT_DIR,
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_WIDENED_SPEC_OUT_DIR,
    MINIMUM_CASE_DELTA_VS_V04_TARGETED,
    MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT,
    MINIMUM_QUALITATIVE_CASE_COUNT,
    MINIMUM_QUALITATIVE_CASE_SHARE_PCT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_boundary_gate"


def build_v050_boundary_gate(
    *,
    widened_spec_path: str = str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"),
    candidate_pack_path: str = str(DEFAULT_CANDIDATE_PACK_OUT_DIR / "summary.json"),
    dispatch_cleanliness_audit_path: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_BOUNDARY_GATE_OUT_DIR),
) -> dict:
    spec = load_json(widened_spec_path)
    pack = load_json(candidate_pack_path)
    dispatch = load_json(dispatch_cleanliness_audit_path)

    case_delta = int(pack.get("case_delta_vs_v0_4_targeted") or 0)
    qualitative_case_count = int(pack.get("qualitative_case_count") or 0)
    qualitative_case_share_pct = float(pack.get("qualitative_case_share_pct") or 0.0)
    distinct_buckets = int(pack.get("distinct_qualitative_bucket_count") or 0)
    wider_than_targeted = case_delta >= int(spec.get("minimum_case_delta_vs_v0_4_targeted") or MINIMUM_CASE_DELTA_VS_V04_TARGETED)
    qualitative_confirmed = (
        qualitative_case_count >= MINIMUM_QUALITATIVE_CASE_COUNT
        and qualitative_case_share_pct >= MINIMUM_QUALITATIVE_CASE_SHARE_PCT
        and distinct_buckets >= MINIMUM_DISTINCT_QUALITATIVE_BUCKET_COUNT
    )
    admission = str(dispatch.get("dispatch_cleanliness_admission") or "")
    interpretable_seed = bool(qualitative_confirmed and pack.get("candidate_boundary_like_breakdown"))
    boundary_mapping_ready = wider_than_targeted and qualitative_confirmed and interpretable_seed and admission == "promoted"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if admission != "failed" else "FAIL",
        "widened_spec_path": str(Path(widened_spec_path).resolve()),
        "candidate_pack_path": str(Path(candidate_pack_path).resolve()),
        "dispatch_cleanliness_audit_path": str(Path(dispatch_cleanliness_audit_path).resolve()),
        "boundary_mapping_ready": boundary_mapping_ready,
        "wider_than_v0_4_targeted_slice": wider_than_targeted,
        "qualitative_widening_confirmed": qualitative_confirmed,
        "interpretable_failure_bucket_seed_available": interpretable_seed,
        "dispatch_cleanliness_admission": admission,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.0 Boundary Gate",
                "",
                f"- wider_than_v0_4_targeted_slice: `{wider_than_targeted}`",
                f"- qualitative_widening_confirmed: `{qualitative_confirmed}`",
                f"- boundary_mapping_ready: `{boundary_mapping_ready}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.0 boundary-mapping readiness gate.")
    parser.add_argument("--widened-spec", default=str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--candidate-pack", default=str(DEFAULT_CANDIDATE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--dispatch-cleanliness-audit", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_BOUNDARY_GATE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v050_boundary_gate(
        widened_spec_path=str(args.widened_spec),
        candidate_pack_path=str(args.candidate_pack),
        dispatch_cleanliness_audit_path=str(args.dispatch_cleanliness_audit),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "boundary_mapping_ready": payload.get("boundary_mapping_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
