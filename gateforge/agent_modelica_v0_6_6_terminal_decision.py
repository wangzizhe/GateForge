from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_6_common import (
    DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_TERMINAL_DECISION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_6_complex_gap_recheck import build_v066_complex_gap_recheck


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_terminal_decision"


def build_v066_terminal_decision(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    complex_gap_recheck_path: str = str(DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_TERMINAL_DECISION_OUT_DIR),
) -> dict:
    if not Path(complex_gap_recheck_path).exists():
        build_v066_complex_gap_recheck(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(complex_gap_recheck_path).parent),
        )

    integrity = load_json(handoff_integrity_path) if Path(handoff_integrity_path).exists() else {"status": "FAIL"}
    recheck = load_json(complex_gap_recheck_path)

    if integrity.get("status") != "PASS":
        decision_terminal_status = "invalid"
        terminal_gap = "upstream_chain_integrity_invalid"
        why_not_terminal_yet = "The late-phase single-gap chain is not trustworthy."
    elif recheck.get("representative_logic_delta") == "unbounded_change" or not recheck.get("legacy_taxonomy_still_sufficient", False):
        decision_terminal_status = "invalid"
        terminal_gap = "representative_logic_or_taxonomy_invalid"
        why_not_terminal_yet = "The last-gap recheck no longer preserves representative logic or legacy taxonomy."
    elif recheck.get("open_world_candidate_supported_after_gap_recheck"):
        decision_terminal_status = "ready"
        terminal_gap = "none"
        why_not_terminal_yet = ""
    elif recheck.get("phase_closeout_supported"):
        decision_terminal_status = "phase_closeout_supported"
        terminal_gap = "none"
        why_not_terminal_yet = ""
    else:
        decision_terminal_status = "partial"
        terminal_gap = "last_gap_still_not_resolved"
        why_not_terminal_yet = "One last late-phase gap still remains and has not yet been shown to be method-exhausted."

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if decision_terminal_status in {"ready", "phase_closeout_supported", "partial"} else "FAIL",
        "decision_terminal_status": decision_terminal_status,
        "terminal_gap": terminal_gap,
        "why_not_terminal_yet": why_not_terminal_yet,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.6 Terminal Decision",
                "",
                f"- decision_terminal_status: `{decision_terminal_status}`",
                f"- terminal_gap: `{terminal_gap}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.6 terminal decision.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--complex-gap-recheck", default=str(DEFAULT_COMPLEX_GAP_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_TERMINAL_DECISION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v066_terminal_decision(
        handoff_integrity_path=str(args.handoff_integrity),
        complex_gap_recheck_path=str(args.complex_gap_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision_terminal_status": payload.get("decision_terminal_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
