from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_12_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_12_closeout"
DEFAULT_BLOCK_B_RUNNER_SUMMARY = "artifacts/agent_modelica_v0_3_12_block_b_runner_current/summary.json"
DEFAULT_BLOCK_B_DECISION_SUMMARY = "artifacts/agent_modelica_v0_3_12_block_b_decision_current/summary.json"
DEFAULT_RESOLUTION_AUDIT_SUMMARY = "artifacts/agent_modelica_v0_3_12_resolution_audit_current/summary.json"
DEFAULT_FAILURE_NOTE_SUMMARY = "artifacts/agent_modelica_v0_3_12_failure_note_current/summary.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def build_v0_3_12_closeout(
    *,
    block_b_runner_summary_path: str = DEFAULT_BLOCK_B_RUNNER_SUMMARY,
    block_b_decision_summary_path: str = DEFAULT_BLOCK_B_DECISION_SUMMARY,
    resolution_audit_summary_path: str = DEFAULT_RESOLUTION_AUDIT_SUMMARY,
    failure_note_summary_path: str = DEFAULT_FAILURE_NOTE_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    block_b_runner = _load_json(block_b_runner_summary_path)
    block_b_decision = _load_json(block_b_decision_summary_path)
    resolution_audit = _load_json(resolution_audit_summary_path)
    failure_note = _load_json(failure_note_summary_path)

    decision = str(block_b_decision.get("decision") or "missing_block_b_decision")
    reason = str(block_b_decision.get("reason") or "")
    metrics = block_b_decision.get("metrics") if isinstance(block_b_decision.get("metrics"), dict) else {}
    audit_overall = resolution_audit.get("overall") if isinstance(resolution_audit.get("overall"), dict) else {}

    classification = decision
    if decision in {"one_shot_hypothesis_confirmed", "one_shot_hypothesis_rejected"}:
        version_status = "hypothesis_resolved"
    else:
        version_status = "hypothesis_not_resolved"

    takeaways = [
        f"Block B reached admitted_count={int(metrics.get('admitted_count') or 0)} but successful_labeled_count={int(metrics.get('successful_labeled_count') or 0)}, so the one-shot hypothesis remains unresolved under the fixed v0.3.12 gate.",
        "Track A and Track B remain deterministic-rule dominated and therefore are not suitable as the main planner-comparative substrate.",
        "Planner-sensitive evidence exists only on the small calibration lane, while harder holdout remains mixed and includes unresolved failures.",
    ]
    next_actions = [
        "Do not promote same_branch_one_shot_or_accidental_success from the current v0.3.12 run.",
        str(audit_overall.get("paper_claim_recommendation") or "design_new_track_c_slice_away_from_deterministic_tracks"),
        "Preserve the harder-holdout persistent failure note as the paper-route failure sidecar.",
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "version": "v0.3.12",
        "classification": classification,
        "version_status": version_status,
        "block_b_decision": decision,
        "block_b_reason": reason,
        "paper_claim_status": str(audit_overall.get("paper_claim_status") or ""),
        "paper_claim_recommendation": str(audit_overall.get("paper_claim_recommendation") or ""),
        "evidence": {
            "block_b_runner_summary_path": str(Path(block_b_runner_summary_path).resolve()) if Path(block_b_runner_summary_path).exists() else str(block_b_runner_summary_path),
            "block_b_decision_summary_path": str(Path(block_b_decision_summary_path).resolve()) if Path(block_b_decision_summary_path).exists() else str(block_b_decision_summary_path),
            "resolution_audit_summary_path": str(Path(resolution_audit_summary_path).resolve()) if Path(resolution_audit_summary_path).exists() else str(resolution_audit_summary_path),
            "failure_note_summary_path": str(Path(failure_note_summary_path).resolve()) if Path(failure_note_summary_path).exists() else str(failure_note_summary_path),
            "block_b": {
                "planner_backend": block_b_runner.get("planner_backend"),
                "task_count": block_b_runner.get("task_count"),
                "decision": decision,
                "admitted_count": metrics.get("admitted_count"),
                "successful_case_count": metrics.get("successful_case_count"),
                "successful_labeled_count": metrics.get("successful_labeled_count"),
                "unknown_success_pct": metrics.get("unknown_success_pct"),
                "true_continuity_pct": metrics.get("true_continuity_pct"),
            },
            "resolution_audit": {
                "deterministic_dominated_lanes": list(audit_overall.get("deterministic_dominated_lanes") or []),
                "planner_expressive_lanes": list(audit_overall.get("planner_expressive_lanes") or []),
                "unresolved_lanes": list(audit_overall.get("unresolved_lanes") or []),
            },
            "failure_note": {
                "representative_case_count": int(failure_note.get("representative_case_count") or 0),
                "representative_cases": list(failure_note.get("representative_cases") or []),
            },
        },
        "takeaways": takeaways,
        "next_actions": next_actions,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# GateForge v0.3.12 Closeout",
        "",
        f"- classification: `{payload.get('classification')}`",
        f"- version_status: `{payload.get('version_status')}`",
        f"- paper_claim_status: `{payload.get('paper_claim_status')}`",
        f"- paper_claim_recommendation: `{payload.get('paper_claim_recommendation')}`",
        "",
        "## Evidence",
        "",
    ]
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    block_b = evidence.get("block_b") if isinstance(evidence.get("block_b"), dict) else {}
    lines.append(
        f"- Block B: `planner_backend={block_b.get('planner_backend')}`, `task_count={block_b.get('task_count')}`, `admitted_count={block_b.get('admitted_count')}`, `successful_labeled_count={block_b.get('successful_labeled_count')}`, `decision={block_b.get('decision')}`"
    )
    resolution = evidence.get("resolution_audit") if isinstance(evidence.get("resolution_audit"), dict) else {}
    lines.append(
        f"- Resolution audit: `deterministic_dominated_lanes={','.join(resolution.get('deterministic_dominated_lanes') or [])}`, `planner_expressive_lanes={','.join(resolution.get('planner_expressive_lanes') or [])}`, `unresolved_lanes={','.join(resolution.get('unresolved_lanes') or [])}`"
    )
    failure = evidence.get("failure_note") if isinstance(evidence.get("failure_note"), dict) else {}
    lines.append(f"- Failure note: `representative_case_count={failure.get('representative_case_count')}`")
    lines.append("")
    lines.append("## Takeaways")
    lines.append("")
    for row in payload.get("takeaways") or []:
        lines.append(f"- {row}")
    lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    for row in payload.get("next_actions") or []:
        lines.append(f"- {row}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.12 closeout summary from Block B/C/D artifacts.")
    parser.add_argument("--block-b-runner-summary", default=DEFAULT_BLOCK_B_RUNNER_SUMMARY)
    parser.add_argument("--block-b-decision-summary", default=DEFAULT_BLOCK_B_DECISION_SUMMARY)
    parser.add_argument("--resolution-audit-summary", default=DEFAULT_RESOLUTION_AUDIT_SUMMARY)
    parser.add_argument("--failure-note-summary", default=DEFAULT_FAILURE_NOTE_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_12_closeout(
        block_b_runner_summary_path=str(args.block_b_runner_summary),
        block_b_decision_summary_path=str(args.block_b_decision_summary),
        resolution_audit_summary_path=str(args.resolution_audit_summary),
        failure_note_summary_path=str(args.failure_note_summary),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "classification": payload.get("classification"),
                "paper_claim_recommendation": payload.get("paper_claim_recommendation"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
