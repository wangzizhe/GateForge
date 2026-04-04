from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_27_common import (
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_patch_contract"


def build_v0327_patch_contract(*, out_dir: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR)) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "version_focus": "stage2_neighbor_component_local_interface_discovery",
        "allowed_patch_types": ["replace_connect_endpoint", "replace_local_port_symbol"],
        "max_patch_count_per_round": 1,
        "patch_scope_definition": "single_connect_statement_or_single_local_endpoint_symbol",
        "selection_mode": "authoritative_per_component_type_local_interface_surface_only",
        "cross_component_candidate_pooling_allowed": False,
        "per_round_candidate_scope_definition": "round_n_uses_only_the_component_type_local_surface_of_the_component_touched_in_round_n",
        "disallowed_candidate_sources": [
            "merged_multi_component_candidate_pool",
            "llm_generated_candidates",
            "dynamic_freeform_candidates",
            "whole_library_open_search",
        ],
        "disallowed_patch_modes": [
            "multi_connect_rewrite",
            "equation_block_rewrite",
            "topology_reconstruction",
            "multi_component_regeneration",
        ],
        "claim_boundary": "This contract targets neighbor-component local interface discovery only. It does not establish open-world interface discovery or topology-heavy structural repair.",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.27 Patch Contract",
                "",
                f"- status: `{payload.get('status')}`",
                f"- selection_mode: `{payload.get('selection_mode')}`",
                f"- max_patch_count_per_round: `{payload.get('max_patch_count_per_round')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.27 patch contract.")
    parser.add_argument("--out-dir", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0327_patch_contract(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "selection_mode": payload.get("selection_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
