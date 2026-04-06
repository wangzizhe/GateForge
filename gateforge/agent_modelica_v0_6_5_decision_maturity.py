from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_6_5_common import (
    DEFAULT_DECISION_MATURITY_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR,
    OPEN_WORLD_MARGIN_PARTIAL_MIN,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_6_5_open_world_recheck import build_v065_open_world_recheck


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_decision_maturity"


def build_v065_decision_maturity(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    open_world_recheck_path: str = str(DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DECISION_MATURITY_OUT_DIR),
) -> dict:
    if not Path(open_world_recheck_path).exists():
        build_v065_open_world_recheck(
            handoff_integrity_path=handoff_integrity_path,
            out_dir=str(Path(open_world_recheck_path).parent),
        )

    integrity = load_json(handoff_integrity_path) if Path(handoff_integrity_path).exists() else {"status": "FAIL"}
    recheck = load_json(open_world_recheck_path)

    if integrity.get("status") != "PASS":
        decision_input_maturity = "invalid"
        maturity_gap = "upstream_chain_integrity_invalid"
        why_not_ready_yet = "The near-miss handoff chain is no longer trustworthy."
        narrower = False
    elif recheck.get("representative_logic_delta") == "unbounded_change" or not recheck.get("legacy_taxonomy_still_sufficient", False):
        decision_input_maturity = "invalid"
        maturity_gap = "representative_logic_or_taxonomy_invalid"
        why_not_ready_yet = "The recheck no longer preserves representative logic or legacy taxonomy."
        narrower = False
    elif recheck.get("open_world_candidate_supported_after_recheck"):
        decision_input_maturity = "ready"
        maturity_gap = "none"
        why_not_ready_yet = ""
        narrower = True
    elif (
        float(recheck.get("open_world_margin_vs_floor_pct") or -999.0) >= OPEN_WORLD_MARGIN_PARTIAL_MIN
        or bool(recheck.get("complex_tier_pressure_is_primary_gap"))
        or str(recheck.get("dominant_remaining_authority_gap") or "none") != "none"
    ):
        decision_input_maturity = "partial"
        maturity_gap = "single_remaining_late_phase_gap"
        why_not_ready_yet = (
            "The remaining late-phase gap is now compressed to a single dominant authority limiter, "
            "even though the open-world threshold is still not fully crossed."
        )
        narrower = True
    else:
        decision_input_maturity = "invalid"
        maturity_gap = "open_world_recheck_not_auditable"
        why_not_ready_yet = "The recheck does not provide a sufficiently auditable late-phase basis."
        narrower = False

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if decision_input_maturity in {"ready", "partial"} else "FAIL",
        "decision_input_maturity": decision_input_maturity,
        "maturity_gap": maturity_gap,
        "why_not_ready_yet": why_not_ready_yet,
        "is_partial_narrower_than_v0_6_4": narrower if decision_input_maturity == "partial" else False,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.6.5 Decision Maturity",
                "",
                f"- decision_input_maturity: `{decision_input_maturity}`",
                f"- maturity_gap: `{maturity_gap}`",
                f"- is_partial_narrower_than_v0_6_4: `{payload['is_partial_narrower_than_v0_6_4']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.6.5 decision maturity.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--open-world-recheck", default=str(DEFAULT_OPEN_WORLD_RECHECK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DECISION_MATURITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v065_decision_maturity(
        handoff_integrity_path=str(args.handoff_integrity),
        open_world_recheck_path=str(args.open_world_recheck),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision_input_maturity": payload.get("decision_input_maturity")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
