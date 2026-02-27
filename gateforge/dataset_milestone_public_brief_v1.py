from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Milestone Public Brief v1",
        "",
        f"- milestone_status: `{payload.get('milestone_status')}`",
        f"- milestone_decision: `{payload.get('milestone_decision')}`",
        f"- checkpoint_score: `{payload.get('checkpoint_score')}`",
        f"- moat_public_score: `{payload.get('moat_public_score')}`",
        f"- alignment_score: `{payload.get('alignment_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build concise public-facing milestone brief")
    parser.add_argument("--milestone-checkpoint-summary", required=True)
    parser.add_argument("--moat-public-scoreboard-summary", required=True)
    parser.add_argument("--snapshot-moat-alignment-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_milestone_public_brief_v1/brief.json")
    parser.add_argument("--report-out", default="artifacts/dataset_milestone_public_brief_v1/brief.md")
    args = parser.parse_args()

    checkpoint = _load_json(args.milestone_checkpoint_summary)
    scoreboard = _load_json(args.moat_public_scoreboard_summary)
    alignment = _load_json(args.snapshot_moat_alignment_summary)

    payload = {
        "milestone_status": checkpoint.get("status"),
        "milestone_decision": checkpoint.get("milestone_decision"),
        "checkpoint_score": checkpoint.get("checkpoint_score"),
        "moat_public_score": scoreboard.get("moat_public_score"),
        "alignment_score": alignment.get("alignment_score"),
        "headline": f"GateForge milestone {checkpoint.get('milestone_decision')} at score {checkpoint.get('checkpoint_score')}",
        "key_risks": checkpoint.get("blockers") or checkpoint.get("alerts") or [],
        "sources": {
            "milestone_checkpoint_summary": args.milestone_checkpoint_summary,
            "moat_public_scoreboard_summary": args.moat_public_scoreboard_summary,
            "snapshot_moat_alignment_summary": args.snapshot_moat_alignment_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out, payload)
    print(json.dumps({"milestone_status": payload.get("milestone_status"), "milestone_decision": payload.get("milestone_decision")}))
    if str(payload.get("milestone_status") or "") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
