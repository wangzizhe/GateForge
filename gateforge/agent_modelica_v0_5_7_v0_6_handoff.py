from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_7_common import (
    DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR,
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V0_6_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_7_boundary_synthesis import build_v057_boundary_synthesis
from .agent_modelica_v0_5_7_stop_condition_audit import build_v057_stop_condition_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_6_handoff"


def build_v057_v0_6_handoff(
    *,
    stop_audit_path: str = str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"),
    boundary_synthesis_path: str = str(DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_V0_6_HANDOFF_OUT_DIR),
) -> dict:
    if not Path(stop_audit_path).exists():
        build_v057_stop_condition_audit(out_dir=str(Path(stop_audit_path).parent))
    if not Path(boundary_synthesis_path).exists():
        build_v057_boundary_synthesis(out_dir=str(Path(boundary_synthesis_path).parent))

    stop_audit = load_json(stop_audit_path)
    boundary = load_json(boundary_synthesis_path)

    if bool(stop_audit.get("overall_stop_condition_met")) and bool(boundary.get("promoted_branch_changes_family_coverage")):
        primary_question = "broader_real_distribution_authority"
        handoff_mode = "start_v0_6_broader_real_distribution_authority"
        why_not_the_other_candidates = {
            "open_world_repair_readiness_evaluation": "The current evidence still comes from bounded and auditable real slices, so it is too early to make open-world readiness the next phase mainline.",
            "targeted_family_expansion_for_uncovered_stage2_slices": "The current recurring bounded uncovered slice has already been handled up to promoted branch authority, so continuing the same expansion is no longer the cleanest phase-level question.",
        }
    else:
        primary_question = "targeted_family_expansion_for_uncovered_stage2_slices"
        handoff_mode = "continue_v0_5_targeted_family_expansion"
        why_not_the_other_candidates = {
            "broader_real_distribution_authority": "The current phase has not yet synthesized enough clean authority evidence to broaden the primary question further.",
            "open_world_repair_readiness_evaluation": "Open-world readiness remains too far from the currently stabilized bounded evidence chain.",
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "v0_6_primary_phase_question": primary_question,
        "v0_6_0_handoff_mode": handoff_mode,
        "why_not_the_other_candidates": why_not_the_other_candidates,
        "do_not_default_back_to_v0_5_branch_expansion": primary_question != "targeted_family_expansion_for_uncovered_stage2_slices",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.7 v0.6 Handoff",
                "",
                f"- v0_6_primary_phase_question: `{payload.get('v0_6_primary_phase_question')}`",
                f"- v0_6_0_handoff_mode: `{payload.get('v0_6_0_handoff_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.7 v0.6 handoff.")
    parser.add_argument("--stop-audit", default=str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--boundary-synthesis", default=str(DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_6_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v057_v0_6_handoff(
        stop_audit_path=str(args.stop_audit),
        boundary_synthesis_path=str(args.boundary_synthesis),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_6_primary_phase_question": payload.get("v0_6_primary_phase_question")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
