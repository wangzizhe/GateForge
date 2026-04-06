from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_1_common import (
    BOUNDARY_BUCKET_ORDER,
    DEFAULT_TAXONOMY_OUT_DIR,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_boundary_taxonomy"


def build_v051_boundary_taxonomy(
    *,
    out_dir: str = str(DEFAULT_TAXONOMY_OUT_DIR),
) -> dict:
    bucket_definition_table = {
        "covered_success": "Inside a declared family envelope and still behaving as a stable covered success region.",
        "covered_but_fragile": "Inside a declared family envelope but showing edge-of-envelope fragility under widened real pressure.",
        "dispatch_or_policy_limited": "Case is dirty or attribution/policy-limited, so it cannot be interpreted as curriculum-coverage failure.",
        "bounded_uncovered_subtype_candidate": "Case is outside the currently declared envelope but still remains bounded, local, and interpretable.",
        "topology_or_open_world_spillover": "Case has moved beyond the bounded local repair regime into topology-heavy or open-world pressure.",
        "boundary_ambiguous": "Case is still not cleanly assignable and should be treated as residual classification noise.",
    }
    bucket_priority_rules_frozen = [
        "dirty_dispatch_first_to_dispatch_or_policy_limited",
        "clean_inside_declared_envelope_then_split_success_vs_fragile",
        "clean_outside_declared_but_bounded_to_bounded_uncovered_subtype_candidate",
        "clean_beyond_bounded_local_regime_to_topology_or_open_world_spillover",
        "residual_unresolved_clean_cases_to_boundary_ambiguous",
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "boundary_bucket_taxonomy_ready": True,
        "bucket_order": BOUNDARY_BUCKET_ORDER,
        "bucket_definition_table": bucket_definition_table,
        "bucket_priority_rules_frozen": bucket_priority_rules_frozen,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.1 Boundary Taxonomy",
                "",
                f"- boundary_bucket_taxonomy_ready: `{payload.get('boundary_bucket_taxonomy_ready')}`",
                f"- bucket_count: `{len(BOUNDARY_BUCKET_ORDER)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.1 boundary bucket taxonomy.")
    parser.add_argument("--out-dir", default=str(DEFAULT_TAXONOMY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v051_boundary_taxonomy(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "boundary_bucket_taxonomy_ready": payload.get("boundary_bucket_taxonomy_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
