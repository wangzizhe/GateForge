from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_19_common import (
    DEFAULT_FAMILY_SPEC_OUT_DIR,
    SCHEMA_PREFIX,
    build_source_specs,
    now_utc,
    norm,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_family_spec"


def build_v0319_family_spec(*, out_dir: str = str(DEFAULT_FAMILY_SPEC_OUT_DIR)) -> dict:
    source_specs = build_source_specs()
    complexity_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    for spec in source_specs:
        tier = norm(spec.get("complexity_tier")) or "unknown"
        complexity_counts[tier] = complexity_counts.get(tier, 0) + 1
        for variant in spec.get("variants") or []:
            key = norm(variant.get("placement_kind")) or "unknown"
            variant_counts[key] = variant_counts.get(key, 0) + 1
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if source_specs else "EMPTY",
        "version_focus": "stage_2_component_api_alignment",
        "training_scope": "api_recovery_not_api_discovery",
        "complexity_tier_scope": ["simple", "medium"],
        "excluded_complexity_tiers": ["complex"],
        "primary_placement_kind": "same_component_dual_mismatch",
        "fallback_placement_kind": "neighbor_component_dual_mismatch",
        "required_first_failure": "stage_2_structural_balance_reference|undefined_symbol",
        "required_second_residual_subtype": "undefined_symbol",
        "disallowed_second_residual_subtypes": ["compile_failure_unknown"],
        "source_count": len(source_specs),
        "complexity_counts": complexity_counts,
        "variant_counts": variant_counts,
        "allowed_source_patterns": [
            "MSL-backed simple or medium models with a single focal component whose class path and public parameters are documented",
            "same-component dual mismatches where the first failure hides the second until one repair is applied",
        ],
        "excluded_source_patterns": [
            "fluid medium redeclare consistency across multiple components",
            "topology reconstruction and missing structural references",
            "complex multi-domain models requiring global intent reconstruction",
        ],
        "sources": source_specs,
        "caveat": {
            "claim_boundary": "This family trains recovery from locally corrupted correct API surfaces, not discovery of the correct API from scratch.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "source_manifest.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.19 Family Spec",
                "",
                f"- status: `{payload.get('status')}`",
                f"- source_count: `{payload.get('source_count')}`",
                f"- primary_placement_kind: `{payload.get('primary_placement_kind')}`",
                f"- training_scope: `{payload.get('training_scope')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.19 family spec.")
    parser.add_argument("--out-dir", default=str(DEFAULT_FAMILY_SPEC_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0319_family_spec(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "source_count": payload.get("source_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
