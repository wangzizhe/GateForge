"""
Decision quality gate for the Modelica repair agent.

Reads the decision attribution summary produced by
agent_modelica_decision_attribution_v1 and evaluates three quality
dimensions against configurable thresholds:

  first_plan_quality  -- are first LLM plans selecting the right branch?
  failure_rate        -- is too high a fraction of tasks still failing?
  round_efficiency    -- are too many rounds being wasted on stale errors?

Transferable skill: Gate Pattern in AI agent systems -- the general
pipeline of (analysis output) → (threshold evaluation) → (PASS/NEEDS_REVIEW/FAIL)
that lets quality signals propagate up into release decisions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_decision_quality_gate_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


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
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}

    def _fmt_check(key: str) -> str:
        c = checks.get(key) if isinstance(checks.get(key), dict) else {}
        icon = "✅" if c.get("pass") else "❌"
        return f"  {icon} actual={c.get('actual')}  threshold={c.get('threshold')}"

    lines = [
        "# Decision Quality Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- primary_reason: {payload.get('primary_reason')}",
        "",
        "## Checks",
        "",
        f"- first_plan_quality (min %):",
        _fmt_check("first_plan_quality"),
        f"- failure_rate (max %):",
        _fmt_check("failure_rate"),
        f"- round_efficiency (max median wasted):",
        _fmt_check("round_efficiency"),
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def evaluate_gate(
    summary: dict,
    *,
    min_first_plan_correct_pct: float = 40.0,
    max_failed_pct: float = 30.0,
    max_median_wasted_rounds: float = 2.0,
) -> dict:
    """
    Evaluate decision quality against thresholds.

    Args:
        summary: the summary dict produced by summarize_decision_attribution().
        min_first_plan_correct_pct: minimum acceptable first-plan correctness %.
        max_failed_pct: maximum acceptable task failure rate %.
        max_median_wasted_rounds: maximum acceptable median wasted rounds.

    Returns:
        gate result dict conforming to SCHEMA_VERSION.
    """
    total = int(summary.get("total_tasks") or 0)
    first_plan_pct = _to_float(summary.get("first_plan_correct_pct"))
    dist = summary.get("causal_path_distribution") if isinstance(
        summary.get("causal_path_distribution"), dict
    ) else {}
    failed_count = int(dist.get("failed") or 0)
    failed_pct = round(failed_count / total * 100, 1) if total else 0.0
    median_wasted = _to_float(summary.get("median_wasted_rounds"))

    first_plan_ok = first_plan_pct >= min_first_plan_correct_pct
    failure_rate_ok = failed_pct <= max_failed_pct
    efficiency_ok = median_wasted <= max_median_wasted_rounds

    failed_checks = sum([not first_plan_ok, not failure_rate_ok, not efficiency_ok])

    if failed_checks == 0:
        status = "PASS"
        primary_reason = "all decision quality checks passed"
    elif failed_checks == 1:
        status = "NEEDS_REVIEW"
        if not first_plan_ok:
            primary_reason = (
                f"first-plan correctness {first_plan_pct}% is below threshold "
                f"{min_first_plan_correct_pct}%"
            )
        elif not failure_rate_ok:
            primary_reason = (
                f"task failure rate {failed_pct}% exceeds threshold {max_failed_pct}%"
            )
        else:
            primary_reason = (
                f"median wasted rounds {median_wasted} exceeds threshold "
                f"{max_median_wasted_rounds}"
            )
    else:
        status = "FAIL"
        parts = []
        if not first_plan_ok:
            parts.append(f"first_plan_correct_pct={first_plan_pct}%<{min_first_plan_correct_pct}%")
        if not failure_rate_ok:
            parts.append(f"failed_pct={failed_pct}%>{max_failed_pct}%")
        if not efficiency_ok:
            parts.append(f"median_wasted={median_wasted}>{max_median_wasted_rounds}")
        primary_reason = "; ".join(parts)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "checks": {
            "first_plan_quality": {
                "pass": first_plan_ok,
                "actual": first_plan_pct,
                "threshold": min_first_plan_correct_pct,
                "label": "first_plan_correct_pct >= threshold",
            },
            "failure_rate": {
                "pass": failure_rate_ok,
                "actual": failed_pct,
                "threshold": max_failed_pct,
                "label": "failed_pct <= threshold",
            },
            "round_efficiency": {
                "pass": efficiency_ok,
                "actual": median_wasted,
                "threshold": max_median_wasted_rounds,
                "label": "median_wasted_rounds <= threshold",
            },
        },
        "primary_reason": primary_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate decision quality from an attribution summary."
    )
    parser.add_argument(
        "--decision-attribution",
        required=True,
        help="Path to decision attribution JSON (output of decision_attribution_v1)",
    )
    parser.add_argument(
        "--min-first-plan-correct-pct",
        type=float,
        default=40.0,
        help="Minimum first-plan correctness %% (default: 40.0)",
    )
    parser.add_argument(
        "--max-failed-pct",
        type=float,
        default=30.0,
        help="Maximum task failure rate %% (default: 30.0)",
    )
    parser.add_argument(
        "--max-median-wasted-rounds",
        type=float,
        default=2.0,
        help="Maximum median wasted rounds (default: 2.0)",
    )
    parser.add_argument("--out", required=True, help="Output path for gate JSON")
    parser.add_argument("--report-out", help="Output path for markdown report")
    args = parser.parse_args()

    attribution = _load_json(args.decision_attribution)
    summary = attribution.get("summary") if isinstance(attribution.get("summary"), dict) else attribution

    result = evaluate_gate(
        summary,
        min_first_plan_correct_pct=args.min_first_plan_correct_pct,
        max_failed_pct=args.max_failed_pct,
        max_median_wasted_rounds=args.max_median_wasted_rounds,
    )
    _write_json(args.out, result)
    if args.report_out:
        _write_markdown(args.report_out, result)
    print(json.dumps({"status": result["status"], "primary_reason": result["primary_reason"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
