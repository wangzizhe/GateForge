from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        rows.append(json.loads(s))
    return rows


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True))
            f.write("\n")


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Policy Auto-Tune Governance Advisor History",
        "",
        f"- total_records: `{payload.get('total_records')}`",
        f"- latest_action: `{payload.get('latest_action')}`",
        f"- tighten_rate: `{payload.get('tighten_rate')}`",
        f"- rollback_review_rate: `{payload.get('rollback_review_rate')}`",
        f"- pairwise_patch_rate: `{payload.get('pairwise_patch_rate')}`",
        f"- leaderboard_instability_rate: `{payload.get('leaderboard_instability_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for a in alerts:
            lines.append(f"- `{a}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append autotune governance advisor summaries to history and summarize")
    parser.add_argument("--record", action="append", default=[], help="Advisor summary JSON path (repeatable)")
    parser.add_argument(
        "--ledger",
        default="artifacts/policy_autotune_governance_advisor_history/history.jsonl",
        help="History JSONL path",
    )
    parser.add_argument(
        "--out",
        default="artifacts/policy_autotune_governance_advisor_history/summary.json",
        help="History summary JSON path",
    )
    parser.add_argument("--report-out", default=None, help="History summary markdown path")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    ledger_path = Path(args.ledger)
    append_rows: list[dict] = []
    for path in args.record:
        payload = _load_json(path)
        advice = payload.get("advice") if isinstance(payload.get("advice"), dict) else {}
        action = str(advice.get("action") or "UNKNOWN")
        patch = advice.get("threshold_patch") if isinstance(advice.get("threshold_patch"), dict) else {}
        pairwise_patch = patch.get("require_min_pairwise_net_margin")
        append_rows.append(
            {
                "recorded_at_utc": now,
                "source_record_path": path,
                "action": action,
                "profile": advice.get("suggested_policy_profile"),
                "confidence": advice.get("confidence"),
                "reasons_count": len(advice.get("reasons") or []),
                "is_tighten": action == "TIGHTEN",
                "is_rollback_review": action == "ROLLBACK_REVIEW",
                "pairwise_patch": pairwise_patch,
                "is_pairwise_patch_enabled": isinstance(pairwise_patch, int) and pairwise_patch > 0,
                "has_leaderboard_instability_reason": any(
                    str(r) in {"compare_leader_pairwise_loss_detected", "compare_runner_up_gap_non_positive"}
                    for r in (advice.get("reasons") or [])
                ),
            }
        )
    if append_rows:
        _append_jsonl(ledger_path, append_rows)

    rows = _load_jsonl(ledger_path)
    total = len(rows)
    latest = rows[-1] if rows else {}

    tighten_count = sum(1 for r in rows if bool(r.get("is_tighten")))
    rollback_count = sum(1 for r in rows if bool(r.get("is_rollback_review")))
    pairwise_patch_count = sum(1 for r in rows if bool(r.get("is_pairwise_patch_enabled")))
    leaderboard_instability_count = sum(1 for r in rows if bool(r.get("has_leaderboard_instability_reason")))
    keep_count = sum(1 for r in rows if str(r.get("action")) == "KEEP")

    tighten_rate = round(tighten_count / max(1, total), 4)
    rollback_rate = round(rollback_count / max(1, total), 4)
    pairwise_patch_rate = round(pairwise_patch_count / max(1, total), 4)
    leaderboard_instability_rate = round(leaderboard_instability_count / max(1, total), 4)

    alerts: list[str] = []
    if str(latest.get("action")) == "ROLLBACK_REVIEW":
        alerts.append("latest_action_rollback_review")
    if rollback_rate >= 0.3 and total >= 3:
        alerts.append("rollback_review_rate_high")
    if tighten_rate >= 0.7 and total >= 3:
        alerts.append("tighten_rate_high")
    if pairwise_patch_rate >= 0.5 and total >= 3:
        alerts.append("pairwise_patch_rate_high")
    if leaderboard_instability_rate >= 0.4 and total >= 3:
        alerts.append("leaderboard_instability_rate_high")

    summary = {
        "generated_at_utc": now,
        "ledger_path": str(ledger_path),
        "ingested_count": len(append_rows),
        "total_records": total,
        "latest_action": latest.get("action"),
        "latest_profile": latest.get("profile"),
        "latest_confidence": latest.get("confidence"),
        "keep_count": keep_count,
        "tighten_count": tighten_count,
        "rollback_review_count": rollback_count,
        "pairwise_patch_count": pairwise_patch_count,
        "tighten_rate": tighten_rate,
        "rollback_review_rate": rollback_rate,
        "pairwise_patch_rate": pairwise_patch_rate,
        "leaderboard_instability_count": leaderboard_instability_count,
        "leaderboard_instability_rate": leaderboard_instability_rate,
        "alerts": alerts,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"total_records": total, "latest_action": summary.get("latest_action"), "alerts": alerts}))


if __name__ == "__main__":
    main()
