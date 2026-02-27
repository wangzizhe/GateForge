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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_json(path: str, payload: object) -> None:
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
        "# GateForge Real Model Intake Weekly Target Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- accepted_large_count: `{payload.get('accepted_large_count')}`",
        f"- reject_rate_pct: `{payload.get('reject_rate_pct')}`",
        "",
        "## Gaps",
        "",
    ]
    gaps = payload.get("target_gaps") if isinstance(payload.get("target_gaps"), list) else []
    if gaps:
        for gap in gaps:
            lines.append(f"- `{gap}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard weekly real-model intake growth targets")
    parser.add_argument("--intake-summary", required=True)
    parser.add_argument("--min-weekly-accepted", type=int, default=3)
    parser.add_argument("--min-weekly-large-accepted", type=int, default=1)
    parser.add_argument("--max-weekly-reject-rate-pct", type=float, default=45.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_intake_weekly_target_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    intake = _load_json(args.intake_summary)

    reasons: list[str] = []
    if not intake:
        reasons.append("intake_summary_missing")

    accepted_count = _to_int(intake.get("accepted_count", 0))
    accepted_large_count = _to_int(
        intake.get("accepted_large_count", ((intake.get("accepted_scale_counts") or {}).get("large", 0)))
    )
    reject_rate_pct = _to_float(intake.get("reject_rate_pct", 0.0))

    target_gaps: list[str] = []
    if accepted_count < int(args.min_weekly_accepted):
        target_gaps.append("weekly_accepted_below_target")
    if accepted_large_count < int(args.min_weekly_large_accepted):
        target_gaps.append("weekly_large_accepted_below_target")
    if reject_rate_pct > float(args.max_weekly_reject_rate_pct):
        target_gaps.append("weekly_reject_rate_above_target")

    intake_status = str(intake.get("status") or "")
    if intake_status == "FAIL":
        target_gaps.append("intake_status_fail")
    if str(intake.get("weekly_target_status") or "") not in {"", "PASS"}:
        target_gaps.append("intake_weekly_target_not_pass")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif target_gaps:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "accepted_count": accepted_count,
        "accepted_large_count": accepted_large_count,
        "reject_rate_pct": round(reject_rate_pct, 2),
        "target_gaps": sorted(set(target_gaps)),
        "reasons": sorted(set(reasons)),
        "thresholds": {
            "min_weekly_accepted": int(args.min_weekly_accepted),
            "min_weekly_large_accepted": int(args.min_weekly_large_accepted),
            "max_weekly_reject_rate_pct": float(args.max_weekly_reject_rate_pct),
        },
        "sources": {
            "intake_summary": args.intake_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "target_gap_count": len(payload.get("target_gaps") or [])}))

    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
