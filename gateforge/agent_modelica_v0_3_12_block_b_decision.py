from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_12_block_b_decision"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_12_block_b_decision"
MIN_CANDIDATE_READY_CASES = 8
MIN_LABELED_FOR_CONCLUSION = 5


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_v0_3_12_block_b_decision(
    *,
    lane_summary_path: str,
    classifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    classifier = _load_json(classifier_summary_path)
    lane_status = str(lane.get("lane_status") or "")
    lane_admitted_count = int(lane.get("admitted_count") or 0)
    metrics = classifier.get("metrics") if isinstance(classifier.get("metrics"), dict) else {}
    successful_label_counts = metrics.get("successful_label_counts") if isinstance(metrics.get("successful_label_counts"), dict) else {}
    successful_case_count = int(metrics.get("successful_case_count") or 0)
    successful_labeled_count = int(metrics.get("successful_labeled_count") or 0)
    unknown_success_pct = float(metrics.get("unknown_success_pct") or 0.0)
    true_continuity_count = int(metrics.get("true_continuity_count") or 0)
    true_continuity_pct = float(metrics.get("true_continuity_pct") or 0.0)
    one_shot_count = int(successful_label_counts.get("one_shot") or 0)
    multi_step_non_continuity_count = int(successful_label_counts.get("multi_step_non_continuity") or 0)

    decision = "inconclusive_needs_more_cases"
    reason = "admitted_count_below_minimum"
    if lane_status != "CANDIDATE_READY" or lane_admitted_count < MIN_CANDIDATE_READY_CASES:
        decision = "inconclusive_needs_more_cases"
        reason = "admitted_count_below_minimum"
    elif unknown_success_pct > 30.0:
        decision = "inconclusive_signal_too_sparse"
        reason = "unknown_success_pct_above_threshold"
    elif successful_labeled_count < MIN_LABELED_FOR_CONCLUSION:
        decision = "inconclusive_insufficient_labeled_cases"
        reason = "successful_labeled_count_below_minimum"
    elif true_continuity_pct < 20.0:
        decision = "one_shot_hypothesis_confirmed"
        reason = "true_continuity_pct_below_confirmation_threshold"
    elif true_continuity_pct >= 40.0:
        decision = "one_shot_hypothesis_rejected"
        reason = "true_continuity_pct_above_rejection_threshold"
    else:
        decision = "inconclusive_ambiguous_signal"
        reason = "true_continuity_pct_in_ambiguous_band"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if lane_admitted_count > 0 else "EMPTY",
        "decision": decision,
        "reason": reason,
        "lane_summary_path": str(Path(lane_summary_path).resolve()) if Path(lane_summary_path).exists() else str(lane_summary_path),
        "classifier_summary_path": str(Path(classifier_summary_path).resolve()) if Path(classifier_summary_path).exists() else str(classifier_summary_path),
        "metrics": {
            "lane_status": lane_status,
            "admitted_count": lane_admitted_count,
            "successful_case_count": successful_case_count,
            "successful_labeled_count": successful_labeled_count,
            "unknown_success_pct": unknown_success_pct,
            "true_continuity_count": true_continuity_count,
            "true_continuity_pct": true_continuity_pct,
            "one_shot_count": one_shot_count,
            "multi_step_non_continuity_count": multi_step_non_continuity_count,
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.12 Block B Decision",
                "",
                f"- decision: `{decision}`",
                f"- reason: `{reason}`",
                f"- admitted_count: `{lane_admitted_count}`",
                f"- successful_labeled_count: `{successful_labeled_count}`",
                f"- unknown_success_pct: `{unknown_success_pct}`",
                f"- true_continuity_pct: `{true_continuity_pct}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.12 Block B decision summary.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_12_block_b_decision(
        lane_summary_path=str(args.lane_summary),
        classifier_summary_path=str(args.classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
