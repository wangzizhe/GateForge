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


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _load_jsonl(path: str | None) -> list[dict]:
    if not path:
        return []
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


def _status_from_signals(signals: dict) -> str:
    if bool(signals.get("latest_replay_fail")):
        return "FAIL"
    if bool(signals.get("replay_non_pass_streak_alert")):
        return "NEEDS_REVIEW"
    if bool(signals.get("mismatch_volume_alert")):
        return "NEEDS_REVIEW"
    if bool(signals.get("compare_strict_fail_present")):
        return "NEEDS_REVIEW"
    return "PASS"


def _compute_summary(ledger_rows: list[dict], history: dict, risk: dict, replay_compare: dict) -> dict:
    latest = ledger_rows[-1] if ledger_rows else {}
    latest_decision = str(latest.get("decision") or "UNKNOWN").upper()
    latest_mismatch_count = int(latest.get("mismatch_count") or 0)
    history_alerts = history.get("alerts", []) if isinstance(history.get("alerts"), list) else []
    compare_rows = replay_compare.get("profile_results", []) if isinstance(replay_compare.get("profile_results"), list) else []
    strict_fail_present = any(str(r.get("final_status") or "").upper() == "FAIL" for r in compare_rows)
    signals = {
        "latest_replay_fail": latest_decision == "FAIL",
        "latest_replay_needs_review": latest_decision == "NEEDS_REVIEW",
        "latest_mismatch_count": latest_mismatch_count,
        "mismatch_volume_alert": "mismatch_volume_high" in history_alerts,
        "replay_non_pass_streak_alert": "replay_non_pass_streak_detected" in history_alerts,
        "compare_strict_fail_present": strict_fail_present,
        "risk_level": (risk.get("risk") or {}).get("level"),
    }
    status = _status_from_signals(signals)
    risks: list[str] = []
    if signals["latest_replay_fail"]:
        risks.append("latest_replay_failed")
    if signals["mismatch_volume_alert"]:
        risks.append("replay_mismatch_volume_high")
    if signals["replay_non_pass_streak_alert"]:
        risks.append("replay_non_pass_streak_detected")
    if signals["compare_strict_fail_present"]:
        risks.append("replay_compare_contains_fail_profile")
    if str(signals.get("risk_level") or "").lower() == "high":
        risks.append("replay_risk_level_high")

    return {
        "status": status,
        "signals": signals,
        "kpis": {
            "latest_replay_decision": latest_decision,
            "latest_mismatch_count": latest_mismatch_count,
            "history_total_rows": int(history.get("total_rows") or 0),
            "history_mismatch_total": int(history.get("mismatch_total") or 0),
            "history_latest_decision": history.get("latest_decision"),
            "history_alert_count": len(history_alerts),
            "risk_score": (risk.get("risk") or {}).get("score"),
            "risk_level": (risk.get("risk") or {}).get("level"),
            "compare_status": replay_compare.get("status"),
            "compare_best_profile": replay_compare.get("best_profile"),
            "compare_profile_count": len(compare_rows),
        },
        "sources": {
            "replay_ledger_path": None,
            "replay_history_summary_path": None,
            "replay_risk_summary_path": None,
            "replay_compare_summary_path": None,
        },
        "risks": risks,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    kpis = summary.get("kpis", {})
    lines = [
        "# GateForge Governance Replay Snapshot",
        "",
        f"- status: `{summary.get('status')}`",
        f"- latest_replay_decision: `{kpis.get('latest_replay_decision')}`",
        f"- latest_mismatch_count: `{kpis.get('latest_mismatch_count')}`",
        f"- history_mismatch_total: `{kpis.get('history_mismatch_total')}`",
        f"- risk_score: `{kpis.get('risk_score')}`",
        f"- risk_level: `{kpis.get('risk_level')}`",
        f"- compare_status: `{kpis.get('compare_status')}`",
        f"- compare_best_profile: `{kpis.get('compare_best_profile')}`",
        "",
        "## Risks",
        "",
    ]
    risks = summary.get("risks", [])
    if risks:
        for r in risks:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Sources", ""])
    for k, v in (summary.get("sources") or {}).items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate replay assets into governance replay snapshot")
    parser.add_argument("--replay-ledger", default=None, help="Replay ledger JSONL path")
    parser.add_argument("--replay-history-summary", default=None, help="Replay history summary JSON path")
    parser.add_argument("--replay-risk-summary", default=None, help="Replay risk summary JSON path")
    parser.add_argument("--replay-compare-summary", default=None, help="Replay compare summary JSON path")
    parser.add_argument("--out", default="artifacts/governance_replay_snapshot/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    ledger_rows = _load_jsonl(args.replay_ledger)
    history = _load_json(args.replay_history_summary)
    risk = _load_json(args.replay_risk_summary)
    replay_compare = _load_json(args.replay_compare_summary)
    summary = _compute_summary(ledger_rows, history, risk, replay_compare)
    summary["sources"]["replay_ledger_path"] = args.replay_ledger
    summary["sources"]["replay_history_summary_path"] = args.replay_history_summary
    summary["sources"]["replay_risk_summary_path"] = args.replay_risk_summary
    summary["sources"]["replay_compare_summary_path"] = args.replay_compare_summary

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "risks": summary.get("risks", [])}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
