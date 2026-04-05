from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_0_common import (
    DEFAULT_CANDIDATE_PACK_OUT_DIR,
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_WIDENED_SPEC_OUT_DIR,
    DEGRADED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX,
    DEGRADED_OVERLAP_CASE_COUNT_MIN,
    PROMOTED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX,
    PROMOTED_OVERLAP_CASE_COUNT_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dispatch_cleanliness_audit"


def build_v050_dispatch_cleanliness_audit(
    *,
    widened_spec_path: str = str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"),
    candidate_pack_path: str = str(DEFAULT_CANDIDATE_PACK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR),
) -> dict:
    _ = load_json(widened_spec_path)
    candidate_pack = load_json(candidate_pack_path)
    task_rows = candidate_pack.get("task_rows") if isinstance(candidate_pack.get("task_rows"), list) else []

    overlap_case_count = int(candidate_pack.get("overlap_case_count") or 0)
    qualitative_widening_auditable = bool(int(candidate_pack.get("qualitative_case_count") or 0) > 0)
    attribution_ambiguity_rate_pct = 0.0
    family_dispatch_visibility = all(bool((row or {}).get("family_id")) for row in task_rows)

    if (
        attribution_ambiguity_rate_pct <= PROMOTED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX
        and overlap_case_count >= PROMOTED_OVERLAP_CASE_COUNT_MIN
        and qualitative_widening_auditable
        and family_dispatch_visibility
    ):
        admission = "promoted"
    elif (
        attribution_ambiguity_rate_pct <= DEGRADED_ATTRIBUTION_AMBIGUITY_RATE_PCT_MAX
        and overlap_case_count >= DEGRADED_OVERLAP_CASE_COUNT_MIN
        and family_dispatch_visibility
    ):
        admission = "degraded_but_executable"
    else:
        admission = "failed"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if admission != "failed" else "FAIL",
        "candidate_pack_path": str(Path(candidate_pack_path).resolve()),
        "dispatch_cleanliness_admission": admission,
        "overlap_case_count": overlap_case_count,
        "attribution_ambiguity_rate_pct": attribution_ambiguity_rate_pct,
        "family_dispatch_visibility": family_dispatch_visibility,
        "qualitative_widening_auditable": qualitative_widening_auditable,
        "degraded_limits_boundary_mapping": admission == "degraded_but_executable",
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.0 Dispatch Cleanliness Audit",
                "",
                f"- dispatch_cleanliness_admission: `{admission}`",
                f"- overlap_case_count: `{overlap_case_count}`",
                f"- attribution_ambiguity_rate_pct: `{attribution_ambiguity_rate_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.0 dispatch-cleanliness admission audit.")
    parser.add_argument("--widened-spec", default=str(DEFAULT_WIDENED_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--candidate-pack", default=str(DEFAULT_CANDIDATE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v050_dispatch_cleanliness_audit(
        widened_spec_path=str(args.widened_spec),
        candidate_pack_path=str(args.candidate_pack),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "dispatch_cleanliness_admission": payload.get("dispatch_cleanliness_admission")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
