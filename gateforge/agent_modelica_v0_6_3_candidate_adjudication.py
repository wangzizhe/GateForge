from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_3_common import (
    DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR,
    DEFAULT_DECISION_INPUT_OUT_DIR,
    OPEN_WORLD_SPILLOVER_MAX,
    OPEN_WORLD_STABLE_COVERAGE_MIN,
    SCHEMA_PREFIX,
    TARGETED_EXPANSION_BOUNDED_UNCOVERED_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_3_phase_decision_input import build_v063_phase_decision_input


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_candidate_adjudication"


def build_v063_candidate_adjudication(
    *,
    phase_decision_input_path: str = str(DEFAULT_DECISION_INPUT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(phase_decision_input_path).exists():
        build_v063_phase_decision_input(out_dir=str(Path(phase_decision_input_path).parent))

    payload_in = load_json(phase_decision_input_path)
    stable_coverage_share_pct = float(payload_in.get("stable_coverage_share_pct") or 0.0)
    spillover_share_pct = float(payload_in.get("topology_or_open_world_spillover_share_pct") or 0.0)
    bounded_uncovered_share_pct = float(payload_in.get("bounded_uncovered_signal_share_pct") or 0.0)
    fluid_status = str(payload_in.get("fluid_network_extension_status_under_representative_pressure") or "")

    open_world_candidate_supported = (
        stable_coverage_share_pct >= OPEN_WORLD_STABLE_COVERAGE_MIN
        and spillover_share_pct <= OPEN_WORLD_SPILLOVER_MAX
        and fluid_status == "stable"
    )
    targeted_expansion_candidate_supported = (
        bounded_uncovered_share_pct >= TARGETED_EXPANSION_BOUNDED_UNCOVERED_MIN
    )

    if open_world_candidate_supported:
        dominant_next_phase_pressure_source = "open_world_readiness_gap_small_enough"
        why_open_world_candidate_not_yet_supported = ""
    else:
        dominant_next_phase_pressure_source = "stable_coverage_below_open_world_floor"
        why_open_world_candidate_not_yet_supported = (
            "Stable coverage is still below the open-world readiness floor and the "
            "promoted fluid-network extension remains fragile rather than fully stable."
        )

    if targeted_expansion_candidate_supported:
        why_targeted_expansion_not_yet_required = ""
    else:
        why_targeted_expansion_not_yet_required = (
            "Bounded uncovered share does not reach the threshold required to justify "
            "reopening targeted expansion as the next mainline."
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "open_world_candidate_supported": open_world_candidate_supported,
        "targeted_expansion_candidate_supported": targeted_expansion_candidate_supported,
        "why_open_world_candidate_not_yet_supported": why_open_world_candidate_not_yet_supported,
        "why_targeted_expansion_not_yet_required": why_targeted_expansion_not_yet_required,
        "dominant_next_phase_pressure_source": dominant_next_phase_pressure_source,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", result)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.3 Candidate Adjudication",
                "",
                f"- open_world_candidate_supported: `{open_world_candidate_supported}`",
                f"- targeted_expansion_candidate_supported: `{targeted_expansion_candidate_supported}`",
                f"- dominant_next_phase_pressure_source: `{dominant_next_phase_pressure_source}`",
            ]
        ),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.3 candidate adjudication.")
    parser.add_argument("--phase-decision-input", default=str(DEFAULT_DECISION_INPUT_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CANDIDATE_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v063_candidate_adjudication(
        phase_decision_input_path=str(args.phase_decision_input),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "open_world_candidate_supported": payload.get("open_world_candidate_supported")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
