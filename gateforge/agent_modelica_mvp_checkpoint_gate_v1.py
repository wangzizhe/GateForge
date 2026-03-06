from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


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
        "# GateForge Agent Modelica MVP Checkpoint Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- daily_success_at_k_pct: `{(payload.get('daily') or {}).get('success_at_k_pct')}`",
        f"- daily_regression_count: `{(payload.get('daily') or {}).get('regression_count')}`",
        f"- daily_focus_hit_rate_pct: `{(payload.get('daily') or {}).get('focus_hit_rate_pct')}`",
        f"- daily_focus_miss_rate_pct: `{(payload.get('daily') or {}).get('focus_miss_rate_pct')}`",
        f"- holdout_success_at_k_pct: `{(payload.get('holdout') or {}).get('success_at_k_pct')}`",
        f"- holdout_regression_count: `{(payload.get('holdout') or {}).get('regression_count')}`",
        f"- ab_delta_success_at_k_pct: `{(payload.get('retrieval_ab') or {}).get('delta_success_at_k_pct')}`",
        f"- ab_delta_regression_count: `{(payload.get('retrieval_ab') or {}).get('delta_regression_count')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        lines.extend([f"- `{str(x)}`" for x in reasons])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _num(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute GO/HOLD/STOP checkpoint decision from daily+AB+holdout summaries")
    parser.add_argument("--daily-summary", required=True)
    parser.add_argument("--retrieval-ab-summary", default="")
    parser.add_argument("--holdout-summary", default="")
    parser.add_argument("--min-daily-success-at-k-pct", type=float, default=90.0)
    parser.add_argument("--max-daily-regression-count", type=float, default=0.0)
    parser.add_argument("--daily-focus-hit-rate-pct", type=float, default=None)
    parser.add_argument("--min-daily-focus-hit-rate-pct", type=float, default=40.0)
    parser.add_argument("--max-daily-focus-miss-rate-pct", type=float, default=60.0)
    parser.add_argument("--min-holdout-success-at-k-pct", type=float, default=85.0)
    parser.add_argument("--max-holdout-regression-count", type=float, default=1.0)
    parser.add_argument("--max-holdout-physics-fail-count", type=float, default=0.0)
    parser.add_argument("--min-ab-delta-success-at-k-pct", type=float, default=5.0)
    parser.add_argument("--max-ab-delta-regression-count", type=float, default=-1.0)
    parser.add_argument("--out", default="artifacts/agent_modelica_mvp_checkpoint_gate_v1/decision.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    daily = _load_json(args.daily_summary)
    ab = _load_json(args.retrieval_ab_summary) if str(args.retrieval_ab_summary).strip() else {}
    holdout = _load_json(args.holdout_summary) if str(args.holdout_summary).strip() else {}

    reasons: list[str] = []
    daily_status = str((daily.get("daily") or {}).get("status") or daily.get("status") or "")
    daily_success = _num((daily.get("daily") or {}).get("success_at_k_pct"), _num(daily.get("success_at_k_pct")))
    daily_reg = _num((daily.get("daily") or {}).get("regression_count"), _num(daily.get("regression_count")))
    daily_focus_hit_input = args.daily_focus_hit_rate_pct
    daily_focus_hit = (
        float(daily_focus_hit_input)
        if isinstance(daily_focus_hit_input, (int, float))
        else _num((daily.get("daily") or {}).get("focus_hit_rate_pct"), _num(daily.get("focus_hit_rate_pct"), default=-1.0))
    )
    daily_focus_present = daily_focus_hit >= 0.0
    daily_focus_miss = round(max(0.0, 100.0 - daily_focus_hit), 2) if daily_focus_present else None
    if daily_status == "FAIL":
        reasons.append("daily_fail")
    if daily_success < float(args.min_daily_success_at_k_pct):
        reasons.append("daily_success_below_threshold")
    if daily_reg > float(args.max_daily_regression_count):
        reasons.append("daily_regression_above_threshold")
    if daily_focus_present:
        if daily_focus_hit < float(args.min_daily_focus_hit_rate_pct):
            reasons.append("daily_focus_hit_below_threshold")
        if (100.0 - daily_focus_hit) > float(args.max_daily_focus_miss_rate_pct):
            reasons.append("daily_focus_miss_above_threshold")

    holdout_present = bool(holdout)
    holdout_status = str(holdout.get("status") or "")
    holdout_success = _num(holdout.get("success_at_k_pct"))
    holdout_reg = _num(holdout.get("regression_count"))
    holdout_phy = _num(holdout.get("physics_fail_count"))
    if holdout_present:
        if holdout_status == "FAIL":
            reasons.append("holdout_fail")
        if holdout_success < float(args.min_holdout_success_at_k_pct):
            reasons.append("holdout_success_below_threshold")
        if holdout_reg > float(args.max_holdout_regression_count):
            reasons.append("holdout_regression_above_threshold")
        if holdout_phy > float(args.max_holdout_physics_fail_count):
            reasons.append("holdout_physics_fail_above_threshold")

    ab_present = bool(ab)
    delta = ab.get("delta_on_minus_off") if isinstance(ab.get("delta_on_minus_off"), dict) else {}
    ab_delta_success = _num(delta.get("success_at_k_pct"))
    ab_delta_reg = _num(delta.get("regression_count"))
    if ab_present:
        if ab_delta_success < float(args.min_ab_delta_success_at_k_pct):
            reasons.append("ab_delta_success_below_threshold")
        if ab_delta_reg > float(args.max_ab_delta_regression_count):
            reasons.append("ab_delta_regression_above_threshold")

    hard_fail = any(x in reasons for x in ("daily_fail", "holdout_fail"))
    if hard_fail:
        decision = "STOP"
    elif reasons:
        decision = "HOLD"
    else:
        decision = "GO"

    status = "PASS" if decision == "GO" else "NEEDS_REVIEW"
    payload = {
        "schema_version": "agent_modelica_mvp_checkpoint_gate_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": decision,
        "daily": {
            "status": daily_status,
            "success_at_k_pct": round(daily_success, 2),
            "regression_count": round(daily_reg, 2),
            "focus_hit_rate_pct": round(daily_focus_hit, 2) if daily_focus_present else None,
            "focus_miss_rate_pct": daily_focus_miss,
        },
        "holdout": {
            "present": holdout_present,
            "status": holdout_status if holdout_present else None,
            "success_at_k_pct": round(holdout_success, 2) if holdout_present else None,
            "regression_count": round(holdout_reg, 2) if holdout_present else None,
            "physics_fail_count": round(holdout_phy, 2) if holdout_present else None,
        },
        "retrieval_ab": {
            "present": ab_present,
            "delta_success_at_k_pct": round(ab_delta_success, 2) if ab_present else None,
            "delta_regression_count": round(ab_delta_reg, 2) if ab_present else None,
        },
        "thresholds": {
            "min_daily_success_at_k_pct": float(args.min_daily_success_at_k_pct),
            "max_daily_regression_count": float(args.max_daily_regression_count),
            "min_daily_focus_hit_rate_pct": float(args.min_daily_focus_hit_rate_pct),
            "max_daily_focus_miss_rate_pct": float(args.max_daily_focus_miss_rate_pct),
            "min_holdout_success_at_k_pct": float(args.min_holdout_success_at_k_pct),
            "max_holdout_regression_count": float(args.max_holdout_regression_count),
            "max_holdout_physics_fail_count": float(args.max_holdout_physics_fail_count),
            "min_ab_delta_success_at_k_pct": float(args.min_ab_delta_success_at_k_pct),
            "max_ab_delta_regression_count": float(args.max_ab_delta_regression_count),
        },
        "reasons": reasons,
        "sources": {
            "daily_summary": args.daily_summary,
            "retrieval_ab_summary": args.retrieval_ab_summary if str(args.retrieval_ab_summary).strip() else None,
            "holdout_summary": args.holdout_summary if str(args.holdout_summary).strip() else None,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
