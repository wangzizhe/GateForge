from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_3_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR,
    DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR,
    DEFAULT_V081_REPLAY_PACK_PATH,
    DEFAULT_V082_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_3_handoff_integrity import build_v083_handoff_integrity
from .agent_modelica_v0_8_3_threshold_validation_replay_pack import (
    build_v083_threshold_validation_replay_pack,
)
from .agent_modelica_v0_8_3_threshold_validation_summary import (
    build_v083_threshold_validation_summary,
)


def build_v083_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    validation_replay_pack_path: str = str(
        DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR / "summary.json"
    ),
    validation_summary_path: str = str(DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR / "summary.json"),
    v081_replay_pack_path: str = str(DEFAULT_V081_REPLAY_PACK_PATH),
    v082_closeout_path: str = str(DEFAULT_V082_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    build_v083_handoff_integrity(
        v082_closeout_path=v082_closeout_path,
        out_dir=str(Path(handoff_integrity_path).parent),
    )
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_8_3_HANDOFF_VALIDATION_INPUTS_INVALID",
            "conclusion": {
                "version_decision": "v0_8_3_handoff_validation_inputs_invalid",
                "v0_8_4_handoff_mode": "rebuild_threshold_validation_chain_first",
                "why_the_pack_is_or_is_not_ready_for_late_adjudication": "Upstream threshold-freeze chain did not pass integrity.",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.8.3 Closeout\n\n- version_decision: `v0_8_3_handoff_validation_inputs_invalid`\n")
        return payload

    build_v083_threshold_validation_replay_pack(
        v081_replay_pack_path=v081_replay_pack_path,
        v082_closeout_path=v082_closeout_path,
        out_dir=str(Path(validation_replay_pack_path).parent),
    )
    build_v083_threshold_validation_summary(
        validation_replay_pack_path=validation_replay_pack_path,
        out_dir=str(Path(validation_summary_path).parent),
    )
    replay = load_json(validation_replay_pack_path)
    summary = load_json(validation_summary_path)

    consistency = float(replay.get("adjudication_route_consistency_rate_pct") or 0.0)
    flip_count = int(replay.get("adjudication_route_flip_count") or 0)
    all_unique = all(int(run.get("route_count_per_run") or 0) == 1 for run in replay.get("validation_runs") or [])
    baseline_partial = summary.get("current_baseline_route_observed") == "workflow_readiness_partial_but_interpretable"
    overlap = bool(summary.get("pack_overlap_detected"))
    underspecified = bool(summary.get("pack_under_specified_detected"))

    if all(
        [
            int(replay.get("validation_run_count") or 0) >= 3,
            consistency == 100.0,
            flip_count == 0,
            all_unique,
            baseline_partial,
            not overlap,
            not underspecified,
        ]
    ):
        state = "validated"
        decision = "v0_8_3_threshold_pack_validated"
        handoff = "run_late_workflow_readiness_adjudication"
        why = "The frozen pack yields one unique and stable route on every run, and the current baseline still lands cleanly on partial without overlap or under-specification."
    elif all(
        [
            int(replay.get("validation_run_count") or 0) >= 2,
            consistency >= 80.0,
            flip_count <= 1,
            all(int(run.get("route_count_per_run") or 0) <= 1 for run in replay.get("validation_runs") or []),
            all(int(run.get("route_count_per_run") or 0) >= 1 for run in replay.get("validation_runs") or []),
            baseline_partial,
            not overlap,
            not underspecified,
        ]
    ):
        state = "partial"
        decision = "v0_8_3_threshold_pack_partial"
        handoff = "repair_threshold_validation_instability_first"
        why = "The frozen pack remains directionally usable, but route stability falls short of the promoted validation bar."
    else:
        state = "invalid"
        decision = "v0_8_3_threshold_pack_invalid"
        handoff = "rebuild_threshold_validation_chain_first"
        why = "The frozen pack does not yet produce a unique and trustworthy same-logic route on the current baseline."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if state in {"validated", "partial"} else "FAIL",
        "closeout_status": {
            "validated": "V0_8_3_THRESHOLD_PACK_VALIDATED",
            "partial": "V0_8_3_THRESHOLD_PACK_PARTIAL",
            "invalid": "V0_8_3_THRESHOLD_PACK_INVALID",
        }[state],
        "conclusion": {
            "version_decision": decision,
            "current_baseline_route_observed": summary.get("current_baseline_route_observed"),
            "why_the_pack_is_or_is_not_ready_for_late_adjudication": why,
            "v0_8_4_handoff_mode": handoff,
        },
        "handoff_integrity": integrity,
        "threshold_validation_replay_pack": replay,
        "threshold_validation_summary": summary,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.3 Closeout",
                "",
                f"- version_decision: `{decision}`",
                f"- current_baseline_route_observed: `{summary.get('current_baseline_route_observed')}`",
                f"- adjudication_route_consistency_rate_pct: `{replay.get('adjudication_route_consistency_rate_pct')}`",
                f"- v0_8_4_handoff_mode: `{handoff}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.3 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument(
        "--validation-replay-pack",
        default=str(DEFAULT_THRESHOLD_VALIDATION_REPLAY_PACK_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--validation-summary",
        default=str(DEFAULT_THRESHOLD_VALIDATION_SUMMARY_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--v081-replay-pack", default=str(DEFAULT_V081_REPLAY_PACK_PATH))
    parser.add_argument("--v082-closeout", default=str(DEFAULT_V082_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v083_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        validation_replay_pack_path=str(args.validation_replay_pack),
        validation_summary_path=str(args.validation_summary),
        v081_replay_pack_path=str(args.v081_replay_pack),
        v082_closeout_path=str(args.v082_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
