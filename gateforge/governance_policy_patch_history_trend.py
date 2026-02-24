from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _rate(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return round(float(n) / float(d), 4)


def _status_counts(summary: dict) -> dict:
    v = summary.get("status_counts")
    return v if isinstance(v, dict) else {}


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend", {})
    lines = [
        "# GateForge Policy Patch History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- current_total_records: `{payload.get('current_total_records')}`",
        f"- previous_total_records: `{payload.get('previous_total_records')}`",
        f"- delta_total_records: `{trend.get('delta_total_records')}`",
        f"- current_fail_rate: `{trend.get('current_fail_rate')}`",
        f"- previous_fail_rate: `{trend.get('previous_fail_rate')}`",
        f"- delta_fail_rate: `{trend.get('delta_fail_rate')}`",
        f"- current_reject_rate: `{trend.get('current_reject_rate')}`",
        f"- previous_reject_rate: `{trend.get('previous_reject_rate')}`",
        f"- delta_reject_rate: `{trend.get('delta_reject_rate')}`",
        f"- current_apply_rate: `{trend.get('current_apply_rate')}`",
        f"- previous_apply_rate: `{trend.get('previous_apply_rate')}`",
        f"- delta_apply_rate: `{trend.get('delta_apply_rate')}`",
        f"- current_pairwise_threshold_enable_rate: `{trend.get('current_pairwise_threshold_enable_rate')}`",
        f"- previous_pairwise_threshold_enable_rate: `{trend.get('previous_pairwise_threshold_enable_rate')}`",
        f"- delta_pairwise_threshold_enable_rate: `{trend.get('delta_pairwise_threshold_enable_rate')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute trend deltas for governance policy patch history summary")
    parser.add_argument("--summary", required=True, help="Current history summary JSON path")
    parser.add_argument("--previous-summary", default=None, help="Previous history summary JSON path")
    parser.add_argument("--out", default="artifacts/governance_policy_patch_history/trend.json", help="Trend JSON path")
    parser.add_argument("--report", default=None, help="Trend markdown path")
    args = parser.parse_args()

    current = _load_json(args.summary)
    previous = _load_json(args.previous_summary) if args.previous_summary else {}
    current_total = int(current.get("total_records", 0))
    previous_total = int(previous.get("total_records", 0))
    current_counts = _status_counts(current)
    previous_counts = _status_counts(previous)
    current_fail = int(current_counts.get("FAIL", 0))
    previous_fail = int(previous_counts.get("FAIL", 0))
    current_reject = int(current.get("reject_count", 0))
    previous_reject = int(previous.get("reject_count", 0))
    current_apply = int(current.get("applied_count", 0))
    previous_apply = int(previous.get("applied_count", 0))
    current_pairwise_enabled = int(current.get("pairwise_threshold_enabled_count", 0))
    previous_pairwise_enabled = int(previous.get("pairwise_threshold_enabled_count", 0))
    current_fail_rate = _rate(current_fail, current_total)
    previous_fail_rate = _rate(previous_fail, previous_total)
    current_reject_rate = _rate(current_reject, current_total)
    previous_reject_rate = _rate(previous_reject, previous_total)
    current_apply_rate = _rate(current_apply, current_total)
    previous_apply_rate = _rate(previous_apply, previous_total)
    current_pairwise_rate = _rate(current_pairwise_enabled, current_total)
    previous_pairwise_rate = _rate(previous_pairwise_enabled, previous_total)

    trend = {
        "delta_total_records": current_total - previous_total,
        "current_fail_rate": current_fail_rate,
        "previous_fail_rate": previous_fail_rate,
        "delta_fail_rate": round(current_fail_rate - previous_fail_rate, 4),
        "current_reject_rate": current_reject_rate,
        "previous_reject_rate": previous_reject_rate,
        "delta_reject_rate": round(current_reject_rate - previous_reject_rate, 4),
        "current_apply_rate": current_apply_rate,
        "previous_apply_rate": previous_apply_rate,
        "delta_apply_rate": round(current_apply_rate - previous_apply_rate, 4),
        "current_pairwise_threshold_enable_rate": current_pairwise_rate,
        "previous_pairwise_threshold_enable_rate": previous_pairwise_rate,
        "delta_pairwise_threshold_enable_rate": round(current_pairwise_rate - previous_pairwise_rate, 4),
    }

    payload = {
        "status": current.get("latest_status"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary_path": args.summary,
        "previous_summary_path": args.previous_summary,
        "current_total_records": current_total,
        "previous_total_records": previous_total,
        "trend": trend,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload["status"], "delta_fail_rate": trend["delta_fail_rate"]}))


if __name__ == "__main__":
    main()
