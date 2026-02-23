from __future__ import annotations

import argparse
import json
from collections import Counter
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


def _status_score(status: str | None) -> int:
    value = str(status or "UNKNOWN").upper()
    if value == "PASS":
        return 2
    if value == "NEEDS_REVIEW":
        return 1
    if value == "FAIL":
        return 0
    return -1


def _load_records(path: str) -> list[dict]:
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


def _summarize(records: list[dict], last_n: int, mismatch_threshold: int, non_pass_streak_threshold: int) -> dict:
    window = records[-max(1, int(last_n)) :] if records else []
    decision_counts = Counter()
    mismatch_codes = Counter()
    transitions: list[dict] = []
    mismatch_total = 0

    for idx, row in enumerate(window):
        decision = str(row.get("decision") or "UNKNOWN").upper()
        decision_counts[decision] += 1
        mismatches = row.get("mismatches", [])
        if isinstance(mismatches, list):
            mismatch_total += len(mismatches)
            for item in mismatches:
                if isinstance(item, dict):
                    code = item.get("code")
                    if isinstance(code, str):
                        mismatch_codes[code] += 1
        if idx > 0:
            prev = str(window[idx - 1].get("decision") or "UNKNOWN").upper()
            relation = "unchanged"
            if _status_score(decision) > _status_score(prev):
                relation = "improved"
            elif _status_score(decision) < _status_score(prev):
                relation = "worse"
            transitions.append(
                {
                    "from": prev,
                    "to": decision,
                    "relation": relation,
                    "from_recorded_at_utc": window[idx - 1].get("recorded_at_utc"),
                    "to_recorded_at_utc": row.get("recorded_at_utc"),
                }
            )

    non_pass_streak = 0
    max_non_pass_streak = 0
    for row in window:
        decision = str(row.get("decision") or "UNKNOWN").upper()
        if decision in {"NEEDS_REVIEW", "FAIL"}:
            non_pass_streak += 1
            if non_pass_streak > max_non_pass_streak:
                max_non_pass_streak = non_pass_streak
        else:
            non_pass_streak = 0

    latest_non_pass_streak = 0
    for row in reversed(window):
        decision = str(row.get("decision") or "UNKNOWN").upper()
        if decision in {"NEEDS_REVIEW", "FAIL"}:
            latest_non_pass_streak += 1
        else:
            break

    alerts: list[str] = []
    if mismatch_total >= max(1, int(mismatch_threshold)):
        alerts.append("mismatch_volume_high")
    if latest_non_pass_streak >= max(1, int(non_pass_streak_threshold)):
        alerts.append("replay_non_pass_streak_detected")

    return {
        "total_records": len(records),
        "window_size": len(window),
        "window_start_utc": window[0].get("recorded_at_utc") if window else None,
        "window_end_utc": window[-1].get("recorded_at_utc") if window else None,
        "latest_decision": window[-1].get("decision") if window else None,
        "decision_counts": dict(decision_counts),
        "mismatch_code_counts": dict(mismatch_codes),
        "mismatch_total": mismatch_total,
        "transitions": transitions,
        "transition_kpis": {
            "transition_count": len(transitions),
            "max_non_pass_streak": max_non_pass_streak,
            "latest_non_pass_streak": latest_non_pass_streak,
            "mismatch_threshold": int(mismatch_threshold),
            "non_pass_streak_threshold": int(non_pass_streak_threshold),
        },
        "alerts": alerts,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Replay History",
        "",
        f"- total_records: `{summary.get('total_records')}`",
        f"- window_size: `{summary.get('window_size')}`",
        f"- window_start_utc: `{summary.get('window_start_utc')}`",
        f"- window_end_utc: `{summary.get('window_end_utc')}`",
        f"- latest_decision: `{summary.get('latest_decision')}`",
        f"- mismatch_total: `{summary.get('mismatch_total')}`",
        "",
        "## Decision Counts",
        "",
    ]
    decision_counts = summary.get("decision_counts", {})
    if decision_counts:
        for key in sorted(decision_counts.keys()):
            lines.append(f"- {key}: `{decision_counts[key]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Mismatch Code Counts", ""])
    mismatch_counts = summary.get("mismatch_code_counts", {})
    if mismatch_counts:
        for key in sorted(mismatch_counts.keys()):
            lines.append(f"- {key}: `{mismatch_counts[key]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Alerts", ""])
    alerts = summary.get("alerts", [])
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize governance replay history")
    parser.add_argument("--ledger", default="artifacts/governance_replay/history.jsonl", help="Replay history JSONL path")
    parser.add_argument("--last-n", type=int, default=10, help="Window size for summary")
    parser.add_argument(
        "--mismatch-threshold",
        type=int,
        default=5,
        help="Alert when total mismatch count in window reaches this threshold",
    )
    parser.add_argument(
        "--non-pass-streak-threshold",
        type=int,
        default=2,
        help="Alert when trailing non-pass replay streak reaches this threshold",
    )
    parser.add_argument("--out", default="artifacts/governance_replay/history_summary.json", help="Summary output JSON path")
    parser.add_argument("--report", default=None, help="Summary markdown output path")
    args = parser.parse_args()

    rows = _load_records(args.ledger)
    summary = _summarize(
        rows,
        last_n=args.last_n,
        mismatch_threshold=args.mismatch_threshold,
        non_pass_streak_threshold=args.non_pass_streak_threshold,
    )
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"latest_decision": summary.get("latest_decision"), "alerts": summary.get("alerts", [])}))


if __name__ == "__main__":
    main()
