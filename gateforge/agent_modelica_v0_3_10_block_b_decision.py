from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_10_block_b_decision"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_10_block_b_decision"


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


def build_v0_3_10_block_b_decision(
    *,
    lane_summary_path: str,
    refreshed_summary_path: str,
    classifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    refreshed = _load_json(refreshed_summary_path)
    classifier = _load_json(classifier_summary_path)

    lane_status = str(lane.get("lane_status") or "")
    refreshed_metrics = refreshed.get("metrics") if isinstance(refreshed.get("metrics"), dict) else {}
    classifier_metrics = classifier.get("metrics") if isinstance(classifier.get("metrics"), dict) else {}
    counts = classifier_metrics.get("primary_bucket_counts") if isinstance(classifier_metrics.get("primary_bucket_counts"), dict) else {}
    total = int(classifier_metrics.get("total_rows") or 0)
    sorted_counts = sorted(((bucket, int(count)) for bucket, count in counts.items()), key=lambda item: item[1], reverse=True)
    top_bucket, top_count = sorted_counts[0] if sorted_counts else ("", 0)
    second_count = sorted_counts[1][1] if len(sorted_counts) > 1 else 0
    top_coverage_pct = round(100.0 * top_count / total, 1) if total else 0.0
    residual_count = total - top_count
    residual_pct = round(100.0 * residual_count / total, 1) if total else 0.0

    continuity_count = int(refreshed_metrics.get("success_after_same_branch_continuation_count") or 0)
    continuity_pct = float(refreshed_metrics.get("same_branch_continuity_success_pct") or 0.0)
    switch_pct = float(refreshed_metrics.get("success_with_explicit_branch_switch_evidence_pct") or 0.0)

    decision = "blocked"
    reason = "insufficient_continuity_signal"
    replacement_hypothesis = ""
    if (
        lane_status == "CANDIDATE_READY"
        and top_bucket == "true_same_branch_multi_step_success"
        and continuity_count >= 5
        and continuity_pct >= 60.0
        and switch_pct <= 20.0
        and top_count >= second_count + 2
    ):
        decision = "continuity_promotion_supported"
        reason = "same_branch_continuity_dominates_mainline"
    elif total > 0 and top_bucket != "true_same_branch_multi_step_success" and top_coverage_pct >= 80.0 and residual_pct <= 20.0:
        decision = "narrower_replacement_hypothesis_supported"
        reason = "same_branch_continuity_not_dominant_and_one_narrower_mechanism_explains_the_lane"
        replacement_hypothesis = top_bucket

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total > 0 else "EMPTY",
        "decision": decision,
        "reason": reason,
        "lane_summary_path": str(Path(lane_summary_path).resolve()) if Path(lane_summary_path).exists() else str(lane_summary_path),
        "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "classifier_summary_path": str(Path(classifier_summary_path).resolve()) if Path(classifier_summary_path).exists() else str(classifier_summary_path),
        "metrics": {
            "lane_status": lane_status,
            "total_rows": total,
            "top_bucket": top_bucket,
            "top_bucket_count": top_count,
            "top_bucket_coverage_pct": top_coverage_pct,
            "residual_count": residual_count,
            "residual_pct": residual_pct,
            "continuity_success_count": continuity_count,
            "continuity_success_pct": continuity_pct,
            "switch_evidence_pct": switch_pct,
        },
        "replacement_hypothesis": replacement_hypothesis,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.10 Block B Decision",
                "",
                f"- decision: `{decision}`",
                f"- reason: `{reason}`",
                f"- top_bucket: `{top_bucket}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the single Block B decision for v0.3.10.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_10_block_b_decision(
        lane_summary_path=str(args.lane_summary),
        refreshed_summary_path=str(args.refreshed_summary),
        classifier_summary_path=str(args.classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
