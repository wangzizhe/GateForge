from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_l5_performance_trend_v1"
DEFAULT_WINDOW_WEEKS = 4
VOLATILITY_STABLE_THRESHOLD_PP = 10.0
MIN_WEEKS_CALIBRATING = 2
MIN_WEEKS_STABLE = 4


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_ledger(path: str) -> list[dict]:
    """Read a JSONL ledger file; silently skip malformed lines."""
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _group_by_iso_week(rows: list[dict]) -> dict[str, dict]:
    """Group rows by ISO week key; keep only the latest row per week."""
    by_week: dict[str, dict] = {}
    for row in rows:
        dt_text = str(row.get("generated_at_utc") or "").strip()
        try:
            dt = datetime.fromisoformat(dt_text.replace("Z", "+00:00"))
        except ValueError:
            continue
        year, week, _ = dt.isocalendar()
        key = f"{year}-W{week:02d}"
        existing = by_week.get(key)
        if existing is None:
            by_week[key] = row
        else:
            # Keep latest by lexicographic comparison of ISO timestamp strings
            existing_ts = str(existing.get("generated_at_utc") or "")
            if dt_text >= existing_ts:
                by_week[key] = row
    return by_week


def _get_window_rows(by_week: dict[str, dict], window_weeks: int) -> list[dict]:
    """Return the last `window_weeks` rows in chronological order."""
    all_keys = sorted(by_week.keys())
    window_keys = all_keys[-window_weeks:] if window_weeks > 0 else []
    return [by_week[k] for k in window_keys]


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_l5_performance_trend(
    *,
    ledger_path: str,
    window_weeks: int = DEFAULT_WINDOW_WEEKS,
    volatility_stable_threshold_pp: float = VOLATILITY_STABLE_THRESHOLD_PP,
) -> dict:
    """Compute rolling L5 performance trend from a JSONL ledger."""
    rows = _load_ledger(ledger_path)
    by_week = _group_by_iso_week(rows)
    all_week_keys = sorted(by_week.keys())
    total_weeks = len(all_week_keys)

    window_rows = _get_window_rows(by_week, window_weeks)
    window_count = len(window_rows)

    # Success series for the window
    window_success_series = [_to_float(r.get("success_at_k_pct")) for r in window_rows]
    window_gate_results = [str(r.get("gate_result") or r.get("status") or "") for r in window_rows]
    window_week_keys = all_week_keys[-window_weeks:] if window_weeks > 0 and all_week_keys else []

    # baseline_derived_pct — mean success rate over the window
    if window_count >= 1:
        baseline_derived_pct: float | None = round(statistics.mean(window_success_series), 4)
    else:
        baseline_derived_pct = None

    # volatility_pp — standard deviation of success rate over the window
    if window_count >= 2:
        volatility_pp: float | None = round(statistics.stdev(window_success_series), 4)
    elif window_count == 1:
        volatility_pp = 0.0
    else:
        volatility_pp = None

    # trend_direction — compare oldest vs newest in window
    if window_count >= 2:
        oldest = window_success_series[0]
        newest = window_success_series[-1]
        if newest - oldest > 1.0:
            trend_direction = "up"
        elif oldest - newest > 1.0:
            trend_direction = "down"
        else:
            trend_direction = "flat"
    else:
        trend_direction = "unknown"

    # consecutive_pass_weeks / consecutive_fail_weeks — count from most recent backward
    consecutive_pass_weeks = 0
    consecutive_fail_weeks = 0
    for key in reversed(all_week_keys):
        gate = str(by_week[key].get("gate_result") or by_week[key].get("status") or "").strip().upper()
        if gate == "PASS":
            consecutive_pass_weeks += 1
        else:
            break
    for key in reversed(all_week_keys):
        gate = str(by_week[key].get("gate_result") or by_week[key].get("status") or "").strip().upper()
        if gate == "FAIL":
            consecutive_fail_weeks += 1
        else:
            break

    # authority_status
    if total_weeks < MIN_WEEKS_CALIBRATING:
        authority_status = "insufficient_data"
    elif total_weeks < MIN_WEEKS_STABLE:
        authority_status = "calibrating"
    elif volatility_pp is not None and volatility_pp <= volatility_stable_threshold_pp:
        authority_status = "stable"
    else:
        # Enough history but window is too volatile
        authority_status = "calibrating"

    # Advisory reasons (non-blocking)
    reasons: list[str] = []
    if authority_status == "insufficient_data":
        reasons.append("authority_status_insufficient_data")
    elif authority_status == "calibrating":
        reasons.append("authority_status_calibrating")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority_status": authority_status,
        "window_weeks": window_weeks,
        "total_ledger_weeks": total_weeks,
        "window_row_count": window_count,
        "all_week_keys": all_week_keys,
        "window_week_keys": window_week_keys,
        "baseline_derived_pct": baseline_derived_pct,
        "volatility_pp": volatility_pp,
        "trend_direction": trend_direction,
        "consecutive_pass_weeks": consecutive_pass_weeks,
        "consecutive_fail_weeks": consecutive_fail_weeks,
        "window_success_series": window_success_series,
        "window_gate_results": window_gate_results,
        "ledger_path": ledger_path,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_markdown(path: str, payload: dict) -> None:
    window_week_keys = payload.get("window_week_keys") or []
    window_success_series = payload.get("window_success_series") or []
    window_gate_results = payload.get("window_gate_results") or []

    series_lines: list[str] = []
    for i, key in enumerate(window_week_keys):
        pct = window_success_series[i] if i < len(window_success_series) else 0.0
        gate = window_gate_results[i] if i < len(window_gate_results) else ""
        series_lines.append(f"- {key}: `{pct}` ({gate})")

    lines = [
        "# Agent Modelica L5 Performance Trend v1",
        "",
        f"- authority_status: `{payload.get('authority_status')}`",
        f"- window_weeks: `{payload.get('window_weeks')}`",
        f"- total_ledger_weeks: `{payload.get('total_ledger_weeks')}`",
        f"- window_row_count: `{payload.get('window_row_count')}`",
        f"- baseline_derived_pct: `{payload.get('baseline_derived_pct')}`",
        f"- volatility_pp: `{payload.get('volatility_pp')}`",
        f"- trend_direction: `{payload.get('trend_direction')}`",
        f"- consecutive_pass_weeks: `{payload.get('consecutive_pass_weeks')}`",
        f"- consecutive_fail_weeks: `{payload.get('consecutive_fail_weeks')}`",
        f"- reasons: `{payload.get('reasons')}`",
        "",
        "## Window Success Series",
        "",
        *series_lines,
        "",
    ]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Compute L5 performance trend from ledger")
    parser.add_argument(
        "--ledger",
        default="artifacts/private/l5_eval_ledger_v1.jsonl",
        help="Path to l5_eval_ledger_v1.jsonl",
    )
    parser.add_argument(
        "--window-weeks",
        type=int,
        default=DEFAULT_WINDOW_WEEKS,
        help="Rolling window size in weeks (default: 4)",
    )
    parser.add_argument(
        "--volatility-stable-threshold-pp",
        type=float,
        default=VOLATILITY_STABLE_THRESHOLD_PP,
        help="Max stdev to qualify for 'stable' authority_status (default: 10.0)",
    )
    parser.add_argument(
        "--out",
        default="artifacts/agent_modelica_l5_eval_v1/l5_performance_trend.json",
        help="Path for JSON output",
    )
    parser.add_argument(
        "--report-out",
        default=None,
        help="Path for Markdown output (default: --out with .md suffix)",
    )
    args = parser.parse_args()

    result = compute_l5_performance_trend(
        ledger_path=args.ledger,
        window_weeks=args.window_weeks,
        volatility_stable_threshold_pp=args.volatility_stable_threshold_pp,
    )

    _write_json(args.out, result)
    _write_markdown(args.report_out or _default_md_path(args.out), result)

    # Always exit 0 — this module is purely observational
    print(
        json.dumps(
            {
                "authority_status": result["authority_status"],
                "baseline_derived_pct": result["baseline_derived_pct"],
                "volatility_pp": result["volatility_pp"],
                "trend_direction": result["trend_direction"],
                "window_weeks": result["window_weeks"],
                "total_ledger_weeks": result["total_ledger_weeks"],
            }
        )
    )


if __name__ == "__main__":
    main()
