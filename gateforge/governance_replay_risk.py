from __future__ import annotations

import argparse
import json
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_rows(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda x: str(x.get("recorded_at_utc") or ""))
    return rows


def _latest_non_pass_streak(rows: list[dict]) -> int:
    streak = 0
    for row in reversed(rows):
        decision = str(row.get("decision") or "UNKNOWN").upper()
        if decision in {"NEEDS_REVIEW", "FAIL"}:
            streak += 1
        else:
            break
    return streak


def _compute_score(rows: list[dict]) -> dict:
    if not rows:
        return {
            "score": 0,
            "level": "low",
            "components": {
                "latest_decision_component": 0,
                "mismatch_volume_component": 0,
                "non_pass_streak_component": 0,
                "unique_mismatch_component": 0,
            },
        }

    latest_decision = str(rows[-1].get("decision") or "UNKNOWN").upper()
    latest_component = 0
    if latest_decision == "NEEDS_REVIEW":
        latest_component = 20
    elif latest_decision == "FAIL":
        latest_component = 40

    mismatch_total = 0
    mismatch_codes: set[str] = set()
    for row in rows:
        mismatches = row.get("mismatches", [])
        if not isinstance(mismatches, list):
            continue
        mismatch_total += len(mismatches)
        for item in mismatches:
            if isinstance(item, dict) and isinstance(item.get("code"), str):
                mismatch_codes.add(str(item["code"]))
    avg_mismatch = mismatch_total / max(len(rows), 1)
    mismatch_volume_component = min(int(round(avg_mismatch * 15)), 30)

    streak = _latest_non_pass_streak(rows)
    streak_component = min(streak * 10, 30)
    unique_component = min(len(mismatch_codes) * 5, 20)

    score = min(latest_component + mismatch_volume_component + streak_component + unique_component, 100)
    level = "low"
    if score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    return {
        "score": score,
        "level": level,
        "components": {
            "latest_decision_component": latest_component,
            "mismatch_volume_component": mismatch_volume_component,
            "non_pass_streak_component": streak_component,
            "unique_mismatch_component": unique_component,
        },
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    risk = summary.get("risk", {})
    components = risk.get("components", {})
    lines = [
        "# GateForge Governance Replay Risk",
        "",
        f"- total_rows: `{summary.get('total_rows')}`",
        f"- latest_decision: `{summary.get('latest_decision')}`",
        f"- score: `{risk.get('score')}`",
        f"- level: `{risk.get('level')}`",
        "",
        "## Components",
        "",
        f"- latest_decision_component: `{components.get('latest_decision_component')}`",
        f"- mismatch_volume_component: `{components.get('mismatch_volume_component')}`",
        f"- non_pass_streak_component: `{components.get('non_pass_streak_component')}`",
        f"- unique_mismatch_component: `{components.get('unique_mismatch_component')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute replay risk score from governance replay ledger")
    parser.add_argument("--ledger", required=True, help="Replay ledger JSONL path")
    parser.add_argument("--last-n", type=int, default=20, help="Use last N rows for risk scoring")
    parser.add_argument("--out", default="artifacts/governance_replay/risk.json", help="Risk summary JSON path")
    parser.add_argument("--report", default=None, help="Risk summary markdown path")
    args = parser.parse_args()

    rows = _load_rows(args.ledger)
    window = rows[-max(1, int(args.last_n)) :] if rows else []
    risk = _compute_score(window)
    summary = {
        "total_rows": len(window),
        "latest_decision": window[-1].get("decision") if window else None,
        "risk": risk,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"score": risk.get("score"), "level": risk.get("level")}))


if __name__ == "__main__":
    main()
