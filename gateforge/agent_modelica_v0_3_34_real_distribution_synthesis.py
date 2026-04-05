from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_34_common import (
    DEFAULT_FAMILY_LEDGER_OUT_DIR,
    DEFAULT_REAL_DIST_OUT_DIR,
    DEFAULT_V0317_CLOSEOUT_PATH,
    DEFAULT_V0317_DISTRIBUTION_ANALYSIS_PATH,
    SCHEMA_PREFIX,
    conclusion_of,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_34_family_ledger import build_v0334_family_ledger


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_real_distribution_synthesis"


def build_v0334_real_distribution_synthesis(
    *,
    family_ledger_path: str = str(DEFAULT_FAMILY_LEDGER_OUT_DIR / "summary.json"),
    v0317_closeout_path: str = str(DEFAULT_V0317_CLOSEOUT_PATH),
    v0317_distribution_analysis_path: str = str(DEFAULT_V0317_DISTRIBUTION_ANALYSIS_PATH),
    out_dir: str = str(DEFAULT_REAL_DIST_OUT_DIR),
) -> dict:
    if not Path(family_ledger_path).exists():
        build_v0334_family_ledger(out_dir=str(Path(family_ledger_path).parent))

    ledger = load_json(family_ledger_path)
    v0317_closeout = load_json(v0317_closeout_path)
    v0317_analysis = load_json(v0317_distribution_analysis_path)

    anchor_count = int(ledger.get("family_anchor_count") or 0)
    analysis_family_key_count = int(v0317_analysis.get("synthetic_family_key_count") or 0)
    current_stage2_slices = [
        "stage2_api_surface_symbol_alignment",
        "stage2_local_and_neighbor_interface_endpoint_alignment",
        "stage2_local_medium_redeclare_alignment",
    ]
    remaining_uncovered = [
        "real_generation_distribution_post_v0_3_33_back_check_missing",
        "topology_heavy_stage2_structure_repair",
        "open_world_stage2_candidate_discovery",
    ]
    if analysis_family_key_count < anchor_count:
        material_overlap_supported = "insufficient_evidence"
    else:
        decision = norm(v0317_analysis.get("version_decision"))
        if decision == "distribution_alignment_supported":
            material_overlap_supported = "true"
        elif decision == "distribution_alignment_not_supported":
            material_overlap_supported = "false"
        else:
            material_overlap_supported = "insufficient_evidence"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "family_ledger_path": str(Path(family_ledger_path).resolve()),
        "v0317_closeout_path": str(Path(v0317_closeout_path).resolve()),
        "v0317_distribution_analysis_path": str(Path(v0317_distribution_analysis_path).resolve()),
        "current_stage2_family_slices": current_stage2_slices,
        "material_overlap_supported": material_overlap_supported,
        "material_overlap_basis": {
            "v0317_version_decision": norm(conclusion_of(v0317_closeout).get("version_decision")),
            "v0317_distribution_decision": norm(v0317_analysis.get("version_decision")),
            "v0317_synthetic_family_key_count": analysis_family_key_count,
            "current_family_anchor_count": anchor_count,
        },
        "remaining_uncovered_stage2_slices": remaining_uncovered,
        "uncovered_slices_block_v0_4": False,
        "v0_4_required_real_back_check": material_overlap_supported != "true",
        "summary": (
            "The current three-family stage_2 curriculum is clearly closer to the real stage_2 frontier than the pre-v0.3.18 substrate, but the project still lacks a post-v0.3.33 real-distribution rerun strong enough to promote material-overlap authority."
            if material_overlap_supported == "insufficient_evidence"
            else (
                "The current curriculum has authority-level evidence for material overlap with the real stage_2 distribution."
                if material_overlap_supported == "true"
                else "The current curriculum still lacks material overlap with the real stage_2 distribution."
            )
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.34 Real-Distribution Synthesis",
                "",
                f"- material_overlap_supported: `{payload.get('material_overlap_supported')}`",
                f"- uncovered_slices_block_v0_4: `{payload.get('uncovered_slices_block_v0_4')}`",
                f"- v0_4_required_real_back_check: `{payload.get('v0_4_required_real_back_check')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.34 real-distribution synthesis.")
    parser.add_argument("--family-ledger", default=str(DEFAULT_FAMILY_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--v0317-closeout", default=str(DEFAULT_V0317_CLOSEOUT_PATH))
    parser.add_argument("--v0317-distribution-analysis", default=str(DEFAULT_V0317_DISTRIBUTION_ANALYSIS_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_DIST_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0334_real_distribution_synthesis(
        family_ledger_path=str(args.family_ledger),
        v0317_closeout_path=str(args.v0317_closeout),
        v0317_distribution_analysis_path=str(args.v0317_distribution_analysis),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "material_overlap_supported": payload.get("material_overlap_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
