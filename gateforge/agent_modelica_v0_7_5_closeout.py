from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_5_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_GAP_REFINEMENT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR,
    DEFAULT_V073_CLOSEOUT_PATH,
    DEFAULT_V074_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_7_5_gap_refinement import build_v075_gap_refinement
from .agent_modelica_v0_7_5_handoff_integrity import build_v075_handoff_integrity
from .agent_modelica_v0_7_5_refinement_adjudication import build_v075_refinement_adjudication

_STATUS_MAP = {
    "supported": "V0_7_5_OPEN_WORLD_READINESS_SUPPORTED",
    "partial_but_interpretable": "V0_7_5_OPEN_WORLD_READINESS_PARTIAL_BUT_INTERPRETABLE",
    "invalid": "V0_7_5_HANDOFF_SUBSTRATE_INVALID",
}

_HANDOFF_MAP = {
    "supported": "prepare_late_phase_promotion_or_closeout_inputs",
    "partial_but_interpretable": "prepare_late_phase_partial_closeout_inputs",
    "invalid": "repair_open_world_readiness_refinement_substrate_first",
}

_VERSION_MAP = {
    "supported": "v0_7_5_open_world_readiness_supported",
    "partial_but_interpretable": "v0_7_5_open_world_readiness_partial_but_interpretable",
    "invalid": "v0_7_5_handoff_substrate_invalid",
}


def build_v075_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    gap_refinement_path: str = str(DEFAULT_GAP_REFINEMENT_OUT_DIR / "summary.json"),
    refinement_adjudication_path: str = str(
        DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR / "summary.json"
    ),
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    v073_closeout_path: str = str(DEFAULT_V073_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    # Step 1: handoff integrity.
    if not Path(handoff_integrity_path).exists():
        build_v075_handoff_integrity(
            v074_closeout_path=v074_closeout_path,
            out_dir=str(Path(handoff_integrity_path).parent),
        )
    integrity = load_json(handoff_integrity_path)

    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_5_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_5_handoff_substrate_invalid",
                "readiness_refinement_status": "invalid",
                "stable_coverage_margin_vs_supported_floor_pct": None,
                "spillover_margin_vs_supported_floor_pct": None,
                "legacy_mapping_margin_vs_supported_floor_pct": None,
                "bounded_uncovered_still_subcritical": None,
                "dominant_remaining_gap_after_refinement": None,
                "remaining_gap_count_after_refinement": None,
                "v0_7_6_handoff_mode": "repair_open_world_readiness_refinement_substrate_first",
            },
            "handoff_integrity": integrity,
        }
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.7.5 Closeout\n\n- status: `FAIL` (integrity)\n")
        return payload

    # Step 2: gap refinement.
    if not Path(gap_refinement_path).exists():
        build_v075_gap_refinement(
            v074_closeout_path=v074_closeout_path,
            v073_closeout_path=v073_closeout_path,
            out_dir=str(Path(gap_refinement_path).parent),
        )
    gap_refinement = load_json(gap_refinement_path)

    # Step 3: refinement adjudication.
    if not Path(refinement_adjudication_path).exists():
        build_v075_refinement_adjudication(
            gap_refinement_path=gap_refinement_path,
            out_dir=str(Path(refinement_adjudication_path).parent),
        )
    adjudication = load_json(refinement_adjudication_path)

    status = str(adjudication.get("readiness_refinement_status") or "invalid")
    version_decision = _VERSION_MAP.get(status, "v0_7_5_handoff_substrate_invalid")
    handoff_mode = _HANDOFF_MAP.get(status, "repair_open_world_readiness_refinement_substrate_first")
    closeout_status = _STATUS_MAP.get(status, "V0_7_5_HANDOFF_SUBSTRATE_INVALID")

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status != "invalid" else "FAIL",
        "closeout_status": closeout_status,
        "conclusion": {
            "version_decision": version_decision,
            "readiness_refinement_status": status,
            "stable_coverage_margin_vs_supported_floor_pct": adjudication.get(
                "stable_coverage_margin_vs_supported_floor_pct"
            ),
            "spillover_margin_vs_supported_floor_pct": adjudication.get(
                "spillover_margin_vs_supported_floor_pct"
            ),
            "legacy_mapping_margin_vs_supported_floor_pct": adjudication.get(
                "legacy_mapping_margin_vs_supported_floor_pct"
            ),
            "bounded_uncovered_still_subcritical": adjudication.get(
                "bounded_uncovered_still_subcritical"
            ),
            "dominant_remaining_gap_after_refinement": adjudication.get(
                "dominant_remaining_gap_after_refinement"
            ),
            "remaining_gap_count_after_refinement": adjudication.get(
                "remaining_gap_count_after_refinement"
            ),
            "v0_7_6_handoff_mode": handoff_mode,
        },
        "handoff_integrity": integrity,
        "gap_refinement": gap_refinement,
        "refinement_adjudication": adjudication,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.5 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- readiness_refinement_status: `{status}`",
                f"- stable_coverage_margin: `{adjudication.get('stable_coverage_margin_vs_supported_floor_pct'):+.2f}pp`",
                f"- spillover_margin: `{adjudication.get('spillover_margin_vs_supported_floor_pct'):+.2f}pp`",
                f"- legacy_mapping_margin: `{adjudication.get('legacy_mapping_margin_vs_supported_floor_pct'):+.2f}pp`",
                f"- remaining_gap_count: `{adjudication.get('remaining_gap_count_after_refinement')}`",
                f"- dominant_remaining_gap: `{adjudication.get('dominant_remaining_gap_after_refinement')}`",
                f"- v0_7_6_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.5 closeout.")
    parser.add_argument(
        "--handoff-integrity",
        default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--gap-refinement",
        default=str(DEFAULT_GAP_REFINEMENT_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--refinement-adjudication",
        default=str(DEFAULT_REFINEMENT_ADJUDICATION_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--v073-closeout", default=str(DEFAULT_V073_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v075_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        gap_refinement_path=str(args.gap_refinement),
        refinement_adjudication_path=str(args.refinement_adjudication),
        v074_closeout_path=str(args.v074_closeout),
        v073_closeout_path=str(args.v073_closeout),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "version_decision": (payload.get("conclusion") or {}).get("version_decision"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
