from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_7_common import (
    DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR,
    DEFAULT_V051_CASE_CLASSIFICATION_PATH,
    DEFAULT_V056_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_boundary_synthesis"


def build_v057_boundary_synthesis(
    *,
    v051_case_classification_path: str = str(DEFAULT_V051_CASE_CLASSIFICATION_PATH),
    v056_closeout_path: str = str(DEFAULT_V056_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR),
) -> dict:
    classification = load_json(v051_case_classification_path)
    v056 = load_json(v056_closeout_path)
    bucket_table = classification.get("bucket_case_count_table") or {}

    explained_failure_count = int(bucket_table.get("covered_success") or 0) + int(bucket_table.get("covered_but_fragile") or 0) + int(bucket_table.get("bounded_uncovered_subtype_candidate") or 0)
    deferred_boundary_count = int(bucket_table.get("topology_or_open_world_spillover") or 0) + int(bucket_table.get("boundary_ambiguous") or 0)
    promoted_branch_changes_family_coverage = bool((v056.get("conclusion") or {}).get("recommended_promotion_level") == "family_extension_supported") and int(bucket_table.get("bounded_uncovered_subtype_candidate") or 0) > 0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "explained_failure_count": explained_failure_count,
        "deferred_boundary_count": deferred_boundary_count,
        "promoted_branch_changes_family_coverage": promoted_branch_changes_family_coverage,
        "boundary_bucket_case_count_table": bucket_table,
        "boundary_interpretation": {
            "explained_region": "Covered success, covered-but-fragile, and bounded uncovered pressure are now jointly interpretable under the widened map plus promoted branch evidence chain.",
            "deferred_region": "Only topology/open-world spillover or residual ambiguity remain deferred to a later phase.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.7 Boundary Synthesis",
                "",
                f"- explained_failure_count: `{payload.get('explained_failure_count')}`",
                f"- deferred_boundary_count: `{payload.get('deferred_boundary_count')}`",
                f"- promoted_branch_changes_family_coverage: `{payload.get('promoted_branch_changes_family_coverage')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.7 boundary synthesis.")
    parser.add_argument("--v0-5-1-case-classification", default=str(DEFAULT_V051_CASE_CLASSIFICATION_PATH))
    parser.add_argument("--v0-5-6-closeout", default=str(DEFAULT_V056_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v057_boundary_synthesis(
        v051_case_classification_path=str(args.v0_5_1_case_classification),
        v056_closeout_path=str(args.v0_5_6_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "promoted_branch_changes_family_coverage": payload.get("promoted_branch_changes_family_coverage")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
