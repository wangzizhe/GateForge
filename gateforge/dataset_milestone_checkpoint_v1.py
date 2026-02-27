from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _status(v: object) -> str:
    return str(v or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Milestone Checkpoint v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- checkpoint_score: `{payload.get('checkpoint_score')}`",
        f"- milestone_decision: `{payload.get('milestone_decision')}`",
        f"- blocker_count: `{len(payload.get('blockers') or [])}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute milestone checkpoint from moat, alignment and release signals")
    parser.add_argument("--moat-trend-snapshot-summary", required=True)
    parser.add_argument("--moat-public-scoreboard-summary", required=True)
    parser.add_argument("--snapshot-moat-alignment-summary", required=True)
    parser.add_argument("--modelica-release-candidate-gate-summary", required=True)
    parser.add_argument("--min-checkpoint-score", type=float, default=80.0)
    parser.add_argument("--out", default="artifacts/dataset_milestone_checkpoint_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    moat = _load_json(args.moat_trend_snapshot_summary)
    scoreboard = _load_json(args.moat_public_scoreboard_summary)
    alignment = _load_json(args.snapshot_moat_alignment_summary)
    release_candidate = _load_json(args.modelica_release_candidate_gate_summary)

    reasons: list[str] = []
    if not moat:
        reasons.append("moat_trend_snapshot_summary_missing")
    if not scoreboard:
        reasons.append("moat_public_scoreboard_summary_missing")
    if not alignment:
        reasons.append("snapshot_moat_alignment_summary_missing")
    if not release_candidate:
        reasons.append("modelica_release_candidate_gate_summary_missing")

    moat_score = _to_float((moat.get("metrics") or {}).get("moat_score", moat.get("moat_score", 0.0)))
    public_score = _to_float(scoreboard.get("moat_public_score", 0.0))
    alignment_score = _to_float(alignment.get("alignment_score", 0.0))
    release_score = _to_float(release_candidate.get("release_candidate_score", 0.0))

    checkpoint_score = round((moat_score * 0.3) + (public_score * 0.25) + (alignment_score * 0.2) + (release_score * 0.25), 2)

    blockers: list[str] = []
    if _status(moat.get("status")) == "FAIL":
        blockers.append("moat_trend_fail")
    if _status(scoreboard.get("status")) == "FAIL":
        blockers.append("moat_scoreboard_fail")
    if _status(alignment.get("status")) == "FAIL":
        blockers.append("snapshot_alignment_fail")
    if _status(release_candidate.get("status")) == "FAIL":
        blockers.append("release_candidate_fail")
    if _to_int(alignment.get("contradiction_count", 0)) >= 2:
        blockers.append("alignment_contradictions_high")
    if str(release_candidate.get("candidate_decision") or "") == "HOLD":
        blockers.append("release_candidate_hold")
    if checkpoint_score < float(args.min_checkpoint_score):
        blockers.append("checkpoint_score_below_threshold")

    alerts: list[str] = []
    if _status(moat.get("status")) == "NEEDS_REVIEW":
        alerts.append("moat_trend_needs_review")
    if _status(scoreboard.get("status")) == "NEEDS_REVIEW":
        alerts.append("moat_scoreboard_needs_review")
    if _status(alignment.get("status")) == "NEEDS_REVIEW":
        alerts.append("snapshot_alignment_needs_review")

    milestone_decision = "GO"
    if blockers:
        milestone_decision = "HOLD"
    elif alerts:
        milestone_decision = "LIMITED_GO"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif blockers or alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checkpoint_score": checkpoint_score,
        "milestone_decision": milestone_decision,
        "blockers": blockers,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "score_breakdown": {
            "moat_score": moat_score,
            "public_score": public_score,
            "alignment_score": alignment_score,
            "release_candidate_score": release_score,
        },
        "sources": {
            "moat_trend_snapshot_summary": args.moat_trend_snapshot_summary,
            "moat_public_scoreboard_summary": args.moat_public_scoreboard_summary,
            "snapshot_moat_alignment_summary": args.snapshot_moat_alignment_summary,
            "modelica_release_candidate_gate_summary": args.modelica_release_candidate_gate_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "milestone_decision": milestone_decision, "checkpoint_score": checkpoint_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
