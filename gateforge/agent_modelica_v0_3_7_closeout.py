from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_7_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_7_closeout"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def build_v0_3_7_closeout(
    *,
    lane_summary_path: str,
    refreshed_summary_path: str,
    classifier_summary_path: str,
    dev_priorities_summary_path: str,
    verifier_summary_path: str,
    previous_closeout_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    refreshed = _load_json(refreshed_summary_path)
    classifier = _load_json(classifier_summary_path)
    dev = _load_json(dev_priorities_summary_path)
    verifier = _load_json(verifier_summary_path)
    previous = _load_json(previous_closeout_summary_path)

    lane_status = _norm(lane.get("lane_status"))
    admitted_count = int(lane.get("admitted_count") or 0)
    refreshed_metrics = refreshed.get("metrics") if isinstance(refreshed.get("metrics"), dict) else {}
    classifier_metrics = classifier.get("metrics") if isinstance(classifier.get("metrics"), dict) else {}
    counts = classifier_metrics.get("failure_bucket_counts") if isinstance(classifier_metrics.get("failure_bucket_counts"), dict) else {}
    dev_status = _norm(dev.get("status"))
    verifier_status = _norm(verifier.get("status"))
    previous_classification = _norm(previous.get("classification"))

    planner_invoked_pct = float(refreshed_metrics.get("planner_invoked_pct") or 0.0)
    deterministic_only_pct = float(refreshed_metrics.get("deterministic_only_pct") or 0.0)
    success_after_branch_switch = int(counts.get("success_after_branch_switch") or 0)
    success_without_branch_switch_evidence = int(counts.get("success_without_branch_switch_evidence") or 0)
    wrong_branch_after_restore = int(counts.get("wrong_branch_after_restore") or 0)
    stalled_search_after_progress = int(counts.get("stalled_search_after_progress") or 0)

    if (
        lane_status == "CANDIDATE_READY"
        and admitted_count >= 8
        and verifier_status == "PASS"
        and planner_invoked_pct == 100.0
        and deterministic_only_pct == 0.0
        and success_after_branch_switch == 0
        and wrong_branch_after_restore == 0
        and success_without_branch_switch_evidence > 0
    ):
        classification = "branch_switch_frontier_narrowed_behavioral_signal_missing"
        status = "PASS"
    elif (
        lane_status == "CANDIDATE_READY"
        and verifier_status == "PASS"
        and (success_after_branch_switch > 0 or wrong_branch_after_restore > 0 or stalled_search_after_progress > 0)
        and dev_status == "PASS"
    ):
        classification = "branch_switch_frontier_behavioral_signal_detected"
        status = "PASS"
    else:
        classification = "branch_switch_frontier_v0_3_7_incomplete"
        status = "FAIL"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "classification": classification,
        "inputs": {
            "lane_summary_path": str(Path(lane_summary_path).resolve()) if Path(lane_summary_path).exists() else str(lane_summary_path),
            "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
            "classifier_summary_path": str(Path(classifier_summary_path).resolve()) if Path(classifier_summary_path).exists() else str(classifier_summary_path),
            "dev_priorities_summary_path": str(Path(dev_priorities_summary_path).resolve()) if Path(dev_priorities_summary_path).exists() else str(dev_priorities_summary_path),
            "verifier_summary_path": str(Path(verifier_summary_path).resolve()) if Path(verifier_summary_path).exists() else str(verifier_summary_path),
            "previous_closeout_summary_path": str(Path(previous_closeout_summary_path).resolve()) if Path(previous_closeout_summary_path).exists() else str(previous_closeout_summary_path),
        },
        "metrics": {
            "previous_classification": previous_classification,
            "lane_status": lane_status,
            "admitted_count": admitted_count,
            "planner_invoked_pct": planner_invoked_pct,
            "deterministic_only_pct": deterministic_only_pct,
            "success_after_branch_switch_count": success_after_branch_switch,
            "success_without_branch_switch_evidence_count": success_without_branch_switch_evidence,
            "wrong_branch_after_restore_count": wrong_branch_after_restore,
            "stalled_search_after_progress_count": stalled_search_after_progress,
            "dev_status": dev_status,
            "verifier_status": verifier_status,
        },
        "notes": [
            "v0.3.7 stayed narrow: it built and validated a branch-switch-after-stall candidate-ready lane rather than widening back into generic replan work.",
            "The main live result is strong planner involvement without deterministic-only fallback, but still without explicit wrong-branch or branch-switch success evidence.",
            "The engineering conclusion is therefore narrower than a promoted repair lever: the frontier has been sharply localized, but explicit branch-switch behavior still needs to be forced by a later lane.",
            "Comparative work remains maintenance-only and did not reopen in v0.3.7.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.7 Closeout",
                "",
                f"- classification: `{payload['classification']}`",
                f"- lane_status: `{payload['metrics']['lane_status']}`",
                f"- admitted_count: `{payload['metrics']['admitted_count']}`",
                f"- planner_invoked_pct: `{payload['metrics']['planner_invoked_pct']}`",
                f"- deterministic_only_pct: `{payload['metrics']['deterministic_only_pct']}`",
                f"- success_after_branch_switch_count: `{payload['metrics']['success_after_branch_switch_count']}`",
                f"- success_without_branch_switch_evidence_count: `{payload['metrics']['success_without_branch_switch_evidence_count']}`",
                f"- wrong_branch_after_restore_count: `{payload['metrics']['wrong_branch_after_restore_count']}`",
                f"- stalled_search_after_progress_count: `{payload['metrics']['stalled_search_after_progress_count']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.7 release closeout summary.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--verifier-summary", required=True)
    parser.add_argument("--previous-closeout-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_7_closeout(
        lane_summary_path=str(args.lane_summary),
        refreshed_summary_path=str(args.refreshed_summary),
        classifier_summary_path=str(args.classifier_summary),
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        verifier_summary_path=str(args.verifier_summary),
        previous_closeout_summary_path=str(args.previous_closeout_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
