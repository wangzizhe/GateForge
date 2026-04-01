from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_branch_switch_forcing_family_spec_v0_3_8 import evaluate_behavior_forcing_gate


SCHEMA_VERSION = "agent_modelica_v0_3_8_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_8_closeout"


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


def build_v0_3_8_closeout(
    *,
    lane_summary_path: str,
    refreshed_summary_path: str,
    classifier_summary_path: str,
    dev_priorities_summary_path: str,
    verifier_summary_path: str,
    comparative_checkpoint_summary_path: str,
    previous_closeout_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    refreshed = _load_json(refreshed_summary_path)
    classifier = _load_json(classifier_summary_path)
    dev = _load_json(dev_priorities_summary_path)
    verifier = _load_json(verifier_summary_path)
    checkpoint = _load_json(comparative_checkpoint_summary_path)
    previous = _load_json(previous_closeout_summary_path)

    gate_eval = evaluate_behavior_forcing_gate(refreshed)
    metrics = refreshed.get("metrics") if isinstance(refreshed.get("metrics"), dict) else {}
    counts = ((classifier.get("metrics") or {}).get("failure_bucket_counts") or {})
    verifier_status = str(verifier.get("status") or "")
    dev_status = str(dev.get("status") or "")
    checkpoint_decision = str(checkpoint.get("decision") or "")

    success_after_switch = int(counts.get("success_after_branch_switch") or 0)
    success_without = int(counts.get("success_without_branch_switch_evidence") or 0)

    if verifier_status != "PASS":
        classification = "v0_3_8_closeout_blocked_by_verifier"
        status = "FAIL"
    elif gate_eval["admission_valid"] and dev_status == "PASS":
        classification = "branch_switch_behavior_forced_and_promoted"
        status = "PASS"
    elif gate_eval["admission_valid"] and dev_status != "PASS":
        classification = "branch_switch_behavior_forced_partial"
        status = "PASS"
    elif gate_eval["lane_status"] in {"CANDIDATE_READY", "ADMISSION_VALID"} and success_without > 0 and success_after_switch == 0:
        classification = "branch_switch_behavior_still_absorbed_explained"
        status = "PASS"
    else:
        classification = "branch_switch_behavior_forcing_v0_3_8_incomplete"
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
            "comparative_checkpoint_summary_path": str(Path(comparative_checkpoint_summary_path).resolve()) if Path(comparative_checkpoint_summary_path).exists() else str(comparative_checkpoint_summary_path),
            "previous_closeout_summary_path": str(Path(previous_closeout_summary_path).resolve()) if Path(previous_closeout_summary_path).exists() else str(previous_closeout_summary_path),
        },
        "metrics": {
            "previous_classification": str(previous.get("classification") or ""),
            "family_lane_status": str(lane.get("lane_status") or ""),
            "evaluated_lane_status": gate_eval["lane_status"],
            "admission_valid": gate_eval["admission_valid"],
            "gate_results": gate_eval["gates"],
            "success_after_branch_switch_count": success_after_switch,
            "success_without_branch_switch_evidence_count": success_without,
            "checkpoint_decision": checkpoint_decision,
            "verifier_status": verifier_status,
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", "\n".join(["# v0.3.8 Closeout", "", f"- classification: `{classification}`", f"- evaluated_lane_status: `{gate_eval['lane_status']}`", f"- verifier_status: `{verifier_status}`", ""]))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.8 release closeout summary.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--verifier-summary", required=True)
    parser.add_argument("--comparative-checkpoint-summary", required=True)
    parser.add_argument("--previous-closeout-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_8_closeout(
        lane_summary_path=str(args.lane_summary),
        refreshed_summary_path=str(args.refreshed_summary),
        classifier_summary_path=str(args.classifier_summary),
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        verifier_summary_path=str(args.verifier_summary),
        comparative_checkpoint_summary_path=str(args.comparative_checkpoint_summary),
        previous_closeout_summary_path=str(args.previous_closeout_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
