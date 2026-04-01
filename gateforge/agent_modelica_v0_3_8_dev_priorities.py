from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_branch_switch_forcing_family_spec_v0_3_8 import evaluate_behavior_forcing_gate


SCHEMA_VERSION = "agent_modelica_v0_3_8_dev_priorities"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_8_dev_priorities"


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


def build_v0_3_8_dev_priorities(
    *,
    lane_summary_path: str,
    refreshed_summary_path: str,
    classifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    refreshed = _load_json(refreshed_summary_path)
    classifier = _load_json(classifier_summary_path)
    gate_eval = evaluate_behavior_forcing_gate(refreshed)
    counts = ((classifier.get("metrics") or {}).get("failure_bucket_counts") or {})
    success_after_switch = int(counts.get("success_after_branch_switch") or 0)
    success_without_evidence = int(counts.get("success_without_branch_switch_evidence") or 0)

    next_lever = ""
    reason = ""
    status = "PARTIAL"
    if success_after_switch >= 3 and gate_eval["admission_valid"]:
        next_lever = "branch_switch_replan_after_stall"
        reason = "explicit_branch_switch_success_is_mainline"
        status = "PASS"
    elif success_without_evidence > 0:
        next_lever = "alternative_absorption_mechanism_analysis"
        reason = "success_still_absorbed_without_branch_switch_evidence"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "primary_direction": {
            "family_id": str(lane.get("family_id") or ""),
            "lane_status": gate_eval["lane_status"],
            "admission_valid": gate_eval["admission_valid"],
        },
        "next_bottleneck": {
            "lever": next_lever,
            "reason": reason,
            "identified": bool(next_lever),
        },
        "evidence": {
            "success_after_branch_switch_count": success_after_switch,
            "success_without_branch_switch_evidence_count": success_without_evidence,
            "gate_evaluation": gate_eval,
        },
        "next_actions": [
            "Keep v0.3.8 focused on behavior-forcing for explicit branch switch; do not widen back into general replan.",
            "Preserve the fixed v0.3.7 baseline measurement protocol in every authority artifact.",
            (
                f"Treat `{next_lever}` as the active next lever because `{reason}`."
                if next_lever
                else "Continue tightening branch-switch evidence capture before claiming a promoted repair lever."
            ),
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# Agent Modelica v0.3.8 Dev Priorities",
                "",
                f"- status: `{payload['status']}`",
                f"- lane_status: `{payload['primary_direction']['lane_status']}`",
                f"- next_bottleneck: `{payload['next_bottleneck']['lever']}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build actionable v0.3.8 development priorities from branch-switch forcing evidence.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_8_dev_priorities(
        lane_summary_path=str(args.lane_summary),
        refreshed_summary_path=str(args.refreshed_summary),
        classifier_summary_path=str(args.classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_bottleneck": (payload.get("next_bottleneck") or {}).get("lever")}))


if __name__ == "__main__":
    main()
