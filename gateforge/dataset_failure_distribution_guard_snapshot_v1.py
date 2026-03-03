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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Distribution Guard Snapshot v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- stability_score: `{payload.get('stability_score')}`",
        f"- distribution_drift_score: `{payload.get('distribution_drift_score')}`",
        f"- rare_failure_replay_rate: `{payload.get('rare_failure_replay_rate')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stability snapshot from failure-distribution guard for weekly history/trend chain")
    parser.add_argument("--failure-distribution-stability-guard-summary", required=True)
    parser.add_argument("--weekly-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_guard_snapshot_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    guard = _load_json(args.failure_distribution_stability_guard_summary)
    weekly = _load_json(args.weekly_summary)

    reasons: list[str] = []
    if not guard:
        reasons.append("failure_distribution_stability_guard_summary_missing")

    guard_status = str(guard.get("status") or "UNKNOWN")
    drift = _to_float(guard.get("distribution_drift_tvd", 0.0))
    entropy = _to_float(guard.get("failure_type_entropy", 0.0))
    unique_failure_types = _to_int(guard.get("unique_failure_types", 0))

    weekly_kpis = weekly.get("kpis") if isinstance(weekly.get("kpis"), dict) else {}
    weekly_stability_score = _to_float(weekly_kpis.get("failure_distribution_stability_score", 0.0))

    rare_failure_replay_rate = 1.0 if unique_failure_types >= 5 else 0.8 if unique_failure_types >= 3 else 0.5
    score = 80.0
    score += min(12.0, entropy * 6.0)
    score -= min(30.0, drift * 100.0)
    if weekly_stability_score > 0:
        score = (score * 0.6) + (weekly_stability_score * 0.4)
    stability_score = round(_clamp(score), 2)

    alerts: list[str] = []
    if guard_status in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("guard_status_not_pass")
    if drift > 0.25:
        alerts.append("distribution_drift_high")
    if entropy < 1.0:
        alerts.append("failure_type_entropy_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stability_score": stability_score,
        "distribution_drift_score": round(drift, 6),
        "regression_rate_after": 0.0,
        "rare_failure_replay_rate": round(rare_failure_replay_rate, 4),
        "guard_status": guard_status,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_distribution_stability_guard_summary": args.failure_distribution_stability_guard_summary,
            "weekly_summary": args.weekly_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "stability_score": stability_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
