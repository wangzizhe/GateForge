from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
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


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _record_snapshot(snapshot_path: str, history_dir: str, label: str | None = None) -> dict:
    src = Path(snapshot_path)
    payload = json.loads(src.read_text(encoding="utf-8"))

    record_time = _now_utc_iso()
    digest = _snapshot_digest(payload)
    hid = digest[:12]

    hdir = Path(history_dir)
    hdir.mkdir(parents=True, exist_ok=True)
    dest = hdir / f"{record_time.replace(':', '').replace('-', '')}_{hid}.json"

    record = {
        "recorded_at_utc": record_time,
        "snapshot_path": str(src),
        "snapshot_copy_path": str(dest),
        "digest": digest,
        "label": label,
        "status": payload.get("status"),
        "risks": payload.get("risks", []),
        "kpis": payload.get("kpis", {}),
    }

    wrapper = {
        "record": record,
        "snapshot": payload,
    }
    dest.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")

    index = hdir / "index.jsonl"
    with index.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")

    return record


def _load_records(history_dir: str) -> list[dict]:
    hdir = Path(history_dir)
    index = hdir / "index.jsonl"
    rows: list[dict] = []
    if not index.exists():
        return rows
    for line in index.read_text(encoding="utf-8").splitlines():
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


def _status_score(status: str | None) -> int:
    value = str(status or "UNKNOWN").upper()
    if value == "PASS":
        return 2
    if value == "NEEDS_REVIEW":
        return 1
    if value == "FAIL":
        return 0
    return -1


def _summarize_last_n(records: list[dict], last_n: int, worse_streak_threshold: int) -> dict:
    items = records[-max(1, int(last_n)) :] if records else []
    status_counts = Counter()
    risk_counts = Counter()

    transitions = []
    for i, row in enumerate(items):
        status = str(row.get("status") or "UNKNOWN").upper()
        status_counts[status] += 1
        for r in row.get("risks", []) or []:
            if isinstance(r, str):
                risk_counts[r] += 1

        if i > 0:
            prev = str(items[i - 1].get("status") or "UNKNOWN").upper()
            curr = status
            relation = "unchanged"
            if _status_score(curr) > _status_score(prev):
                relation = "improved"
            elif _status_score(curr) < _status_score(prev):
                relation = "worse"
            transitions.append(
                {
                    "from": prev,
                    "to": curr,
                    "relation": relation,
                    "from_recorded_at_utc": items[i - 1].get("recorded_at_utc"),
                    "to_recorded_at_utc": row.get("recorded_at_utc"),
                }
            )

    improved_count = sum(1 for t in transitions if t["relation"] == "improved")
    worse_count = sum(1 for t in transitions if t["relation"] == "worse")
    current_worse_streak = 0
    max_worse_streak = 0
    for t in transitions:
        if t["relation"] == "worse":
            current_worse_streak += 1
            if current_worse_streak > max_worse_streak:
                max_worse_streak = current_worse_streak
        else:
            current_worse_streak = 0
    latest_worse_streak = 0
    for t in reversed(transitions):
        if t["relation"] == "worse":
            latest_worse_streak += 1
        else:
            break
    alerts = []
    if max_worse_streak >= max(1, int(worse_streak_threshold)):
        alerts.append("consecutive_worsening_detected")

    return {
        "total_records": len(records),
        "window_size": len(items),
        "window_start_utc": items[0].get("recorded_at_utc") if items else None,
        "window_end_utc": items[-1].get("recorded_at_utc") if items else None,
        "status_counts": dict(status_counts),
        "risk_counts": dict(risk_counts),
        "transitions": transitions,
        "transition_kpis": {
            "transition_count": len(transitions),
            "improved_count": improved_count,
            "worse_count": worse_count,
            "max_worse_streak": max_worse_streak,
            "latest_worse_streak": latest_worse_streak,
            "worse_streak_threshold": int(worse_streak_threshold),
        },
        "latest_status": items[-1].get("status") if items else None,
        "alerts": alerts,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Governance History Summary",
        "",
        f"- total_records: `{summary.get('total_records')}`",
        f"- window_size: `{summary.get('window_size')}`",
        f"- window_start_utc: `{summary.get('window_start_utc')}`",
        f"- window_end_utc: `{summary.get('window_end_utc')}`",
        f"- latest_status: `{summary.get('latest_status')}`",
        "",
        "## Status Counts",
        "",
    ]

    sc = summary.get("status_counts", {})
    if sc:
        for k in sorted(sc.keys()):
            lines.append(f"- {k}: `{sc[k]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Risk Counts", ""])
    rc = summary.get("risk_counts", {})
    if rc:
        for k in sorted(rc.keys()):
            lines.append(f"- {k}: `{rc[k]}`")
    else:
        lines.append("- `none`")

    tk = summary.get("transition_kpis", {})
    lines.extend(
        [
            "",
            "## Transition KPIs",
            "",
            f"- transition_count: `{tk.get('transition_count')}`",
            f"- improved_count: `{tk.get('improved_count')}`",
            f"- worse_count: `{tk.get('worse_count')}`",
            f"- max_worse_streak: `{tk.get('max_worse_streak')}`",
            f"- latest_worse_streak: `{tk.get('latest_worse_streak')}`",
            f"- worse_streak_threshold: `{tk.get('worse_streak_threshold')}`",
            "",
            "## Alerts",
            "",
        ]
    )
    alerts = summary.get("alerts", [])
    if alerts:
        for item in alerts:
            lines.append(f"- `{item}`")
    else:
        lines.append("- `none`")

    lines.extend(
        [
            "",
            "## Transitions",
            "",
        ]
    )

    tr = summary.get("transitions", [])
    if tr:
        for t in tr:
            lines.append(
                f"- `{t.get('from')}` -> `{t.get('to')}` ({t.get('relation')}) "
                f"at `{t.get('to_recorded_at_utc')}`"
            )
    else:
        lines.append("- `none`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record governance snapshots and summarize recent trend window")
    parser.add_argument("--history-dir", default="artifacts/governance_history", help="History storage directory")
    parser.add_argument("--snapshot", default=None, help="Optional governance snapshot JSON to record")
    parser.add_argument("--label", default=None, help="Optional label for snapshot record")
    parser.add_argument("--last-n", type=int, default=5, help="Window size for trend summary")
    parser.add_argument(
        "--worse-streak-threshold",
        type=int,
        default=2,
        help="Trigger consecutive worsening alert when max worse streak reaches this threshold",
    )
    parser.add_argument("--out", default="artifacts/governance_history/summary.json", help="Summary JSON path")
    parser.add_argument("--report", default=None, help="Summary markdown path")
    args = parser.parse_args()

    recorded = None
    if args.snapshot:
        recorded = _record_snapshot(args.snapshot, args.history_dir, label=args.label)

    records = _load_records(args.history_dir)
    summary = _summarize_last_n(records, last_n=args.last_n, worse_streak_threshold=args.worse_streak_threshold)
    if recorded:
        summary["last_record"] = recorded

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)

    print(
        json.dumps(
            {
                "total_records": summary.get("total_records"),
                "window_size": summary.get("window_size"),
                "latest_status": summary.get("latest_status"),
            }
        )
    )


if __name__ == "__main__":
    main()
