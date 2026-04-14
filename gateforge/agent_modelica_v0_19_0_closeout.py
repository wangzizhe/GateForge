from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, now_utc, write_json, write_text

SCHEMA_PREFIX = "agent_modelica_v0_19_0"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_19_0_closeout_current"

# Expected frozen values for the three foundation modules
_EXPECTED_TAXONOMY_FROZEN = True
_EXPECTED_TAXONOMY_CATEGORY_COUNT = 6
_EXPECTED_HARD_CAP_TURNS = 8
_EXPECTED_STALLED_CONSECUTIVE = 2
_EXPECTED_CYCLING_JACCARD_THRESHOLD = 0.85
_EXPECTED_SCHEMA_VERSION_TURN = "trajectory_turn_v0_19_0"
_EXPECTED_SCHEMA_VERSION_SUMMARY = "trajectory_summary_v0_19_0"


def _check_taxonomy() -> dict:
    from .mutation_taxonomy_v0_19_0 import MUTATION_TAXONOMY, TAXONOMY_FROZEN, TAXONOMY_IDS

    category_count = len(MUTATION_TAXONOMY)
    frozen = bool(TAXONOMY_FROZEN)
    all_ids_present = all(f"T{i}" in TAXONOMY_IDS for i in range(1, _EXPECTED_TAXONOMY_CATEGORY_COUNT + 1))
    taxonomy_frozen = (
        frozen
        and category_count == _EXPECTED_TAXONOMY_CATEGORY_COUNT
        and all_ids_present
    )
    return {
        "taxonomy_frozen": taxonomy_frozen,
        "taxonomy_frozen_flag": frozen,
        "taxonomy_category_count": category_count,
        "taxonomy_all_ids_present": all_ids_present,
    }


def _check_stop_signal() -> dict:
    from .stop_signal_v0_19_0 import (
        CYCLING_JACCARD_THRESHOLD,
        HARD_CAP_TURNS,
        STALLED_CONSECUTIVE,
    )

    hard_cap_ok = HARD_CAP_TURNS == _EXPECTED_HARD_CAP_TURNS
    stalled_ok = STALLED_CONSECUTIVE == _EXPECTED_STALLED_CONSECUTIVE
    cycling_ok = abs(CYCLING_JACCARD_THRESHOLD - _EXPECTED_CYCLING_JACCARD_THRESHOLD) < 1e-9
    stop_signal_frozen = hard_cap_ok and stalled_ok and cycling_ok
    return {
        "stop_signal_frozen": stop_signal_frozen,
        "hard_cap_turns": HARD_CAP_TURNS,
        "stalled_consecutive": STALLED_CONSECUTIVE,
        "cycling_jaccard_threshold": CYCLING_JACCARD_THRESHOLD,
        "hard_cap_ok": hard_cap_ok,
        "stalled_ok": stalled_ok,
        "cycling_ok": cycling_ok,
    }


def _check_trajectory_schema() -> dict:
    from .trajectory_schema_v0_19_0 import SCHEMA_VERSION_SUMMARY, SCHEMA_VERSION_TURN

    turn_ok = SCHEMA_VERSION_TURN == _EXPECTED_SCHEMA_VERSION_TURN
    summary_ok = SCHEMA_VERSION_SUMMARY == _EXPECTED_SCHEMA_VERSION_SUMMARY
    trajectory_schema_frozen = turn_ok and summary_ok
    return {
        "trajectory_schema_frozen": trajectory_schema_frozen,
        "schema_version_turn": SCHEMA_VERSION_TURN,
        "schema_version_summary": SCHEMA_VERSION_SUMMARY,
        "schema_version_turn_ok": turn_ok,
        "schema_version_summary_ok": summary_ok,
    }


def build_v190_closeout(*, out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR)) -> dict:
    taxonomy = _check_taxonomy()
    stop_signal = _check_stop_signal()
    trajectory_schema = _check_trajectory_schema()

    all_frozen = (
        taxonomy["taxonomy_frozen"]
        and stop_signal["stop_signal_frozen"]
        and trajectory_schema["trajectory_schema_frozen"]
    )

    # Distribution alignment experiment was not run in v0.19.0 code deliverable.
    # It is deferred to v0.19.1 as its first prerequisite.
    distribution_alignment_status = "deferred_to_v0_19_1"

    if all_frozen:
        version_decision = "v0_19_0_foundation_ready"
        status = "PASS"
    else:
        version_decision = "v0_19_0_foundation_incomplete"
        status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "conclusion": {
            "version_decision": version_decision,
            "taxonomy_frozen": taxonomy["taxonomy_frozen"],
            "stop_signal_frozen": stop_signal["stop_signal_frozen"],
            "trajectory_schema_frozen": trajectory_schema["trajectory_schema_frozen"],
            "distribution_alignment_status": distribution_alignment_status,
            "v0_19_1_handoff_mode": (
                "proceed_to_benchmark_construction"
                if all_frozen
                else "repair_v0_19_0_foundation_first"
            ),
        },
        "taxonomy_check": taxonomy,
        "stop_signal_check": stop_signal,
        "trajectory_schema_check": trajectory_schema,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join([
            "# v0.19.0 Closeout",
            "",
            f"- version_decision: `{version_decision}`",
            f"- taxonomy_frozen: `{taxonomy['taxonomy_frozen']}`",
            f"- stop_signal_frozen: `{stop_signal['stop_signal_frozen']}`",
            f"- trajectory_schema_frozen: `{trajectory_schema['trajectory_schema_frozen']}`",
            f"- distribution_alignment_status: `{distribution_alignment_status}`",
        ]),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.0 foundation closeout artifact.")
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v190_closeout(out_dir=str(args.out_dir))
    print(json.dumps({
        "status": payload["status"],
        "version_decision": payload["conclusion"]["version_decision"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
