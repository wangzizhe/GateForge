from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_7_dev_priorities"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_7_dev_priorities"


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


def build_v0_3_7_dev_priorities(
    *,
    lane_summary_path: str,
    refreshed_summary_path: str,
    classifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    refreshed = _load_json(refreshed_summary_path)
    classifier = _load_json(classifier_summary_path)

    metrics = classifier.get("metrics") if isinstance(classifier.get("metrics"), dict) else {}
    counts = metrics.get("failure_bucket_counts") if isinstance(metrics.get("failure_bucket_counts"), dict) else {}
    refreshed_metrics = refreshed.get("metrics") if isinstance(refreshed.get("metrics"), dict) else {}

    lane_status = str(lane.get("lane_status") or "")
    success_after_switch = int(counts.get("success_after_branch_switch") or 0)
    wrong_branch = int(counts.get("wrong_branch_after_restore") or 0)
    stalled = int(counts.get("stalled_search_after_progress") or 0)

    next_lever = ""
    reason = ""
    if wrong_branch > 0:
        next_lever = "branch_switch_replan_after_stall"
        reason = "wrong_branch_after_restore_present"
    elif stalled > 0:
        next_lever = "branch_switch_replan_after_stall"
        reason = "stalled_search_after_progress_present"

    status = "PASS" if lane_status == "CANDIDATE_READY" and (success_after_switch > 0 or wrong_branch > 0 or stalled > 0) else "PARTIAL"
    next_actions = [
        "Keep v0.3.7 focused on the narrow branch-switch-after-stall lane; do not widen back into general replan work.",
        "Preserve the v0.3.6 baseline measurement protocol in every authority artifact for this lane.",
    ]
    if next_lever:
        next_actions.append(
            f"Treat `{next_lever}` as the active v0.3.7 repair lever because `{reason}` is now supported by the refreshed branch-switch evidence."
        )
    else:
        next_actions.append(
            "Collect live authority evidence on the branch-switch lane before promoting a stronger replan lever; current evidence is still design-strong but behavior-light."
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "primary_replan_direction": {
            "family_id": "post_restore_branch_switch_after_stall",
            "lane_status": lane_status,
            "candidate_ready": lane_status == "CANDIDATE_READY",
        },
        "next_bottleneck": {
            "lever": next_lever,
            "reason": reason,
            "identified": bool(next_lever),
        },
        "evidence": {
            "planner_invoked_pct": refreshed_metrics.get("planner_invoked_pct"),
            "deterministic_only_pct": refreshed_metrics.get("deterministic_only_pct"),
            "wrong_branch_after_restore_count": wrong_branch,
            "stalled_search_after_progress_count": stalled,
            "success_after_branch_switch_count": success_after_switch,
        },
        "roadmap_continuity": {
            "from_v0_3_6": "guided_replan_after_progress",
            "to_v0_3_7": "branch_switch_after_stall",
            "comparative_mode": "maintenance_only",
        },
        "next_actions": next_actions,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica v0.3.7 Dev Priorities",
        "",
        f"- status: `{payload.get('status')}`",
        f"- primary_replan_direction: `{(payload.get('primary_replan_direction') or {}).get('family_id')}`",
        f"- next_bottleneck: `{(payload.get('next_bottleneck') or {}).get('lever')}`",
        "",
        "## Next Actions",
        "",
    ]
    for idx, item in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build actionable v0.3.7 development priorities from branch-switch evidence.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_7_dev_priorities(
        lane_summary_path=str(args.lane_summary),
        refreshed_summary_path=str(args.refreshed_summary),
        classifier_summary_path=str(args.classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_bottleneck": (payload.get("next_bottleneck") or {}).get("lever")}))


if __name__ == "__main__":
    main()
