from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_20_common import (
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_patch_contract"


def build_v0320_patch_contract(*, out_dir: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR)) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "version_focus": "stage2_first_fix_execution",
        "allowed_patch_types": [
            "replace_class_path",
            "replace_parameter_name",
        ],
        "max_patch_count_per_round": 1,
        "selection_mode": "static_authoritative_candidates_only",
        "disallowed_candidate_sources": [
            "llm_generated_candidates",
            "dynamic_freeform_candidates",
        ],
        "disallowed_patch_modes": [
            "multi_component_rewrite",
            "topology_reconstruction",
            "freeform_regeneration",
        ],
        "claim_boundary": "This contract targets constrained first-fix execution on local API surfaces, not full structural redesign or API discovery from scratch.",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.20 Patch Contract",
                "",
                f"- status: `{payload.get('status')}`",
                f"- max_patch_count_per_round: `{payload.get('max_patch_count_per_round')}`",
                f"- selection_mode: `{payload.get('selection_mode')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.20 first-fix patch contract.")
    parser.add_argument("--out-dir", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0320_patch_contract(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "selection_mode": payload.get("selection_mode")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
