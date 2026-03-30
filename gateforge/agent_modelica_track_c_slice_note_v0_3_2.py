from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_c_slice_note_v0_3_2"
DEFAULT_AUDIT_SUMMARY = "artifacts/agent_modelica_resolution_audit_v0_3_2/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_slice_note_v0_3_2"
MIN_PRIMARY_SLICE_TASKS = 10


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


def classify_lane(lane: dict, *, min_primary_slice_tasks: int = MIN_PRIMARY_SLICE_TASKS) -> dict:
    lane_id = str(lane.get("lane_id") or "").strip()
    label = str(lane.get("label") or lane_id).strip()
    notes = [str(row).strip() for row in (lane.get("notes") or []) if str(row).strip()]
    task_count = int(lane.get("task_count") or 0)
    success_count = int(lane.get("success_count") or 0)
    deterministic_pct = float(((lane.get("success_resolution_path_pct") or {}).get("deterministic_rule_only")) or 0.0)
    planner_invoked_rate_pct = float(lane.get("planner_invoked_rate_pct") or 0.0)

    reasons: list[str] = []
    implication = ""
    bucket = "excluded_now"
    if str(lane.get("status") or "") != "PASS":
        reasons.append(f"lane status is `{lane.get('status')}`")
        implication = "lane cannot justify Track C slice selection until attribution evidence is upgraded"
        bucket = "pending_decision"
    elif any("unresolved resolution paths" in note for note in notes):
        reasons.append("successful cases still report unresolved resolution paths")
        implication = "attribution fidelity must be repaired before the lane can justify slice selection"
        bucket = "pending_decision"
    elif deterministic_pct >= 80.0:
        reasons.append(
            f"successful cases are overwhelmingly `deterministic_rule_only` ({success_count}/{success_count if success_count else task_count})"
        )
        implication = "useful as an authority lane, but not suitable as the primary Track C comparative slice"
        bucket = "excluded_now"
        if task_count < min_primary_slice_tasks:
            reasons.append(f"current total size is only `{task_count}` tasks")
    elif task_count < min_primary_slice_tasks:
        reasons.append(f"lane exposes higher-layer behavior, but current total size is only `{task_count}` tasks")
        if planner_invoked_rate_pct > 0.0:
            reasons.append(f"planner_invoked_rate_pct is `{planner_invoked_rate_pct}`")
        implication = "promising as a seed lane, but it must be expanded into a larger holdout-clean slice before Track C freeze"
        bucket = "seed_candidate"
    else:
        reasons.append("lane shows non-trivial higher-layer behavior without current attribution anomalies")
        implication = "eligible for primary Track C slice consideration"
        bucket = "primary_candidate"
    return {
        "lane_id": lane_id,
        "label": label,
        "bucket": bucket,
        "reasons": reasons,
        "implication": implication,
        "task_count": task_count,
        "success_count": success_count,
    }


def build_slice_note(audit_payload: dict, *, min_primary_slice_tasks: int = MIN_PRIMARY_SLICE_TASKS) -> dict:
    lanes = [row for row in (audit_payload.get("lanes") or []) if isinstance(row, dict)]
    classified = [classify_lane(row, min_primary_slice_tasks=min_primary_slice_tasks) for row in lanes]
    excluded_now = [row for row in classified if row.get("bucket") == "excluded_now"]
    pending_decision = [row for row in classified if row.get("bucket") == "pending_decision"]
    seed_candidates = [row for row in classified if row.get("bucket") == "seed_candidate"]
    primary_candidates = [row for row in classified if row.get("bucket") == "primary_candidate"]
    decision = "no_current_lane_is_track_c_ready_as_primary_slice"
    if primary_candidates:
        decision = "primary_slice_candidate_available"
    elif seed_candidates:
        decision = "seed_candidate_available_but_no_primary_slice_ready"
    next_actions = [
        "Do not freeze a primary Track C slice until holdout cleanliness and resolution-path evidence are both explicit.",
    ]
    if seed_candidates:
        next_actions.append("Expand the seed candidate lane into a larger holdout-clean comparative slice before Track C freeze.")
    if pending_decision:
        next_actions.append("Close attribution gaps or fidelity anomalies before relying on the affected lanes for Track C design.")
    if excluded_now:
        next_actions.append("Keep deterministic-dominated authority lanes for benchmarking, but do not reuse them as the primary Track C slice.")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PRELIMINARY_NEEDS_MORE_EVIDENCE" if not primary_candidates else "PRIMARY_CANDIDATE_AVAILABLE",
        "decision": decision,
        "primary_candidates": primary_candidates,
        "seed_candidates": seed_candidates,
        "excluded_now": excluded_now,
        "pending_decision": pending_decision,
        "selection_rules": [
            "Do not use a lane as the primary Track C slice if successful cases are overwhelmingly deterministic_rule_only.",
            "Do not use a lane as the primary Track C slice if attribution fidelity is unresolved.",
            "Do not freeze a primary Track C slice until holdout cleanliness and resolution-path evidence are both explicit.",
            "Prefer slices where generic agents have a non-trivial chance under shared oracle access and where higher-layer behavior can actually be observed.",
        ],
        "next_actions": next_actions,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# Track C Slice Note v0.3.2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        "",
    ]
    for section_title, key in (
        ("Primary Candidates", "primary_candidates"),
        ("Seed Candidates", "seed_candidates"),
        ("Excluded Now", "excluded_now"),
        ("Pending Decision", "pending_decision"),
    ):
        rows = payload.get(key) if isinstance(payload.get(key), list) else []
        if not rows:
            continue
        lines.append(f"## {section_title}")
        lines.append("")
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.append(f"### {row.get('label')}")
            lines.append("")
            for reason in row.get("reasons") or []:
                lines.append(f"- reason: {reason}")
            lines.append(f"- implication: {row.get('implication')}")
            lines.append("")
    lines.append("## Selection Rules")
    lines.append("")
    for idx, rule in enumerate(payload.get("selection_rules") or [], start=1):
        lines.append(f"{idx}. {rule}")
    lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    for idx, action in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {action}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_slice_note(
    *,
    audit_summary_path: str = DEFAULT_AUDIT_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
    min_primary_slice_tasks: int = MIN_PRIMARY_SLICE_TASKS,
) -> dict:
    audit_payload = _load_json(audit_summary_path)
    payload = build_slice_note(audit_payload, min_primary_slice_tasks=min_primary_slice_tasks)
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Track C slice note from the v0.3.2 resolution audit")
    parser.add_argument("--audit-summary", default=DEFAULT_AUDIT_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-primary-slice-tasks", type=int, default=MIN_PRIMARY_SLICE_TASKS)
    args = parser.parse_args()
    payload = run_slice_note(
        audit_summary_path=str(args.audit_summary),
        out_dir=str(args.out_dir),
        min_primary_slice_tasks=int(args.min_primary_slice_tasks),
    )
    print(json.dumps({"decision": payload.get("decision")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
