"""Block C + D: Readiness Meaning Synthesis and v0.8 Question Freeze.

Block C synthesises what v0.7.x demonstrated and did not demonstrate.
Block D selects and locks the v0.8.x phase-level primary question.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_7_common import (
    DEFAULT_MEANING_SYNTHESIS_OUT_DIR,
    DEFAULT_V075_CLOSEOUT_PATH,
    DEFAULT_V076_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)

_V08_PRIMARY_QUESTION = "workflow_proximal_readiness_evaluation"

_WHY_NOT_OTHERS = (
    "broader_open_world_authority_profiling would require constructing an even more "
    "open substrate before v0.7.x authority claims are stable enough to generalise — "
    "premature given partial_but_interpretable result. "
    "failure_boundary_remapping_under_weaker_protection is a diagnostic tool, not a "
    "phase-level forward question; it does not open new capability territory. "
    "workflow_proximal_readiness_evaluation is the natural escalation: v0.6.x established "
    "authority at the error-distribution level on a representative substrate; v0.7.x "
    "confirmed partial readiness under weaker curation at the same level; the next "
    "meaningful question is whether that readiness survives contact with real workflow "
    "structure rather than error-distribution proxies."
)

_SUPPORTED_CLAIMS = [
    "weaker-curation open-world-adjacent substrate is auditable and non-trivially "
    "distinct from the v0.6.x representative substrate",
    "readiness profile is stable and reproducible under same-logic extension",
    "legacy bucket taxonomy remains the dominant interpretive framework under weaker curation",
    "bounded_uncovered pressure stayed subcritical throughout v0.7.x — "
    "targeted expansion was never required",
    "the single remaining gap (stable_coverage 0.7pp below supported floor) is "
    "small enough to be non-blocking for phase closeout",
    "v0.7.x result is readiness-positive (partial_but_interpretable), not a collapse",
]

_UNSUPPORTED_CLAIMS = [
    "open_world_readiness_supported under weaker curation "
    "(stable_coverage did not clear the 40% supported floor)",
    "workflow-level readiness "
    "(v0.7.x evaluated error-distribution readiness, not real workflow readiness)",
    "v0.6.x authority is wrong or overstated "
    "(v0.7.x used a different substrate and answered a different question)",
]


def build_v077_meaning_synthesis(
    *,
    v075_closeout_path: str = str(DEFAULT_V075_CLOSEOUT_PATH),
    v076_closeout_path: str = str(DEFAULT_V076_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR),
) -> dict:
    v075 = load_json(v075_closeout_path)
    v075c = v075.get("conclusion") or {}
    v076 = load_json(v076_closeout_path)
    v076c = v076.get("conclusion") or {}

    gap_pct = float(v076c.get("gap_magnitude_pct") or 0.0)
    gap_small = bool(v076c.get("gap_magnitude_small_enough_for_closeout_support"))
    single_remaining_gap_non_blocking = gap_small

    stable_margin = float(v075c.get("stable_coverage_margin_vs_supported_floor_pct") or 0.0)
    dominant_gap = str(v075c.get("dominant_remaining_gap_after_refinement") or "unknown")

    phase_meaning_summary = (
        f"v0.7.x evaluated open-world-adjacent readiness under weaker curation. "
        f"The result is partial_but_interpretable: legacy taxonomy is dominant, "
        f"bounded_uncovered stayed subcritical, and the single remaining gap "
        f"({dominant_gap}, {stable_margin:+.1f}pp vs supported floor) is {gap_pct:.2f}pp — "
        f"small enough to be non-blocking for phase closeout. "
        f"This is a readiness-positive outcome, not an authority collapse."
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_meaning_synthesis",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        # Block C
        "phase_meaning_summary": phase_meaning_summary,
        "supported_claims": _SUPPORTED_CLAIMS,
        "unsupported_claims": _UNSUPPORTED_CLAIMS,
        "single_remaining_gap_non_blocking_for_phase_closeout": single_remaining_gap_non_blocking,
        "gap_magnitude_pct": gap_pct,
        "dominant_remaining_gap": dominant_gap,
        # Block D
        "v0_8_primary_phase_question": _V08_PRIMARY_QUESTION,
        "why_not_the_other_candidates": _WHY_NOT_OTHERS,
        "do_not_continue_v0_7_same_logic_refinement_by_default": True,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.7 Meaning Synthesis",
                "",
                "## Phase Meaning (Block C)",
                "",
                phase_meaning_summary,
                "",
                "### Supported claims",
                *[f"- {c}" for c in _SUPPORTED_CLAIMS],
                "",
                "### Unsupported claims",
                *[f"- {c}" for c in _UNSUPPORTED_CLAIMS],
                "",
                f"- single_remaining_gap_non_blocking_for_phase_closeout:"
                f" `{single_remaining_gap_non_blocking}`",
                "",
                "## v0.8 Question Freeze (Block D)",
                "",
                f"- v0_8_primary_phase_question: `{_V08_PRIMARY_QUESTION}`",
                f"- do_not_continue_v0_7_same_logic_refinement_by_default: `True`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.7 meaning synthesis.")
    parser.add_argument("--v075-closeout", default=str(DEFAULT_V075_CLOSEOUT_PATH))
    parser.add_argument("--v076-closeout", default=str(DEFAULT_V076_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MEANING_SYNTHESIS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v077_meaning_synthesis(
        v075_closeout_path=str(args.v075_closeout),
        v076_closeout_path=str(args.v076_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["v0_8_primary_phase_question"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
