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


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _forecast_rows(pack: dict, experiments: dict, moat: dict, guard: dict) -> list[dict]:
    current_moat = _to_float(((moat.get("metrics") or {}).get("moat_score") if isinstance(moat.get("metrics"), dict) else 0.0))

    total_new_cases = _to_int(pack.get("total_target_new_cases", 0))
    medium_cases = _to_int(pack.get("medium_target_new_cases", 0))
    large_cases = _to_int(pack.get("large_target_new_cases", 0))

    exp_rows = experiments.get("experiments") if isinstance(experiments.get("experiments"), list) else []
    top_exp = exp_rows[0] if exp_rows else {}
    top_exp_score = _to_float(top_exp.get("experiment_score", 0.0))
    top_exp_risk = _to_float(top_exp.get("risk_score", 65.0))

    guard_conf = str(guard.get("confidence_level") or "medium")
    guard_status = str(guard.get("status") or "NEEDS_REVIEW")
    confidence_multiplier = 1.0 if guard_conf == "high" else (0.82 if guard_conf == "medium" else 0.6)
    if guard_status == "FAIL":
        confidence_multiplier *= 0.75

    base_case_uplift = ((total_new_cases * 0.9) + (medium_cases * 1.1) + (large_cases * 1.6) + (top_exp_score * 0.18))
    risk_drag = top_exp_risk * 0.08

    scenarios = [
        {"scenario": "cautious", "uplift_factor": 0.65, "risk_factor": 1.2},
        {"scenario": "base", "uplift_factor": 1.0, "risk_factor": 1.0},
        {"scenario": "stretch", "uplift_factor": 1.25, "risk_factor": 1.1},
    ]

    rows: list[dict] = []
    for s in scenarios:
        projected_gain = max(0.0, (base_case_uplift * s["uplift_factor"] * confidence_multiplier) - (risk_drag * s["risk_factor"]))
        projected_score = _clamp(current_moat + projected_gain)
        rows.append(
            {
                "scenario": s["scenario"],
                "projected_moat_score_30d": _round(projected_score),
                "projected_gain_30d": _round(projected_gain),
                "confidence_multiplier": _round(confidence_multiplier),
                "execution_load_index": _round(total_new_cases * (1.2 if s["scenario"] == "stretch" else 1.0)),
            }
        )

    rows.sort(key=lambda x: {"cautious": 0, "base": 1, "stretch": 2}.get(str(x.get("scenario")), 9))
    return rows


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Moat Execution Forecast",
        "",
        f"- status: `{payload.get('status')}`",
        f"- recommendation: `{payload.get('recommendation')}`",
        f"- preferred_scenario: `{payload.get('preferred_scenario')}`",
        f"- projected_moat_score_30d: `{payload.get('projected_moat_score_30d')}`",
        "",
        "## Scenario Forecast",
        "",
    ]

    for row in payload.get("forecast") if isinstance(payload.get("forecast"), list) else []:
        lines.append(
            f"- `{row.get('scenario')}` projected_moat_score_30d=`{row.get('projected_moat_score_30d')}` gain=`{row.get('projected_gain_30d')}`"
        )

    lines.extend(["", "## Reasons", ""])
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Forecast 30-day moat outcome from pack execution and policy experiments")
    parser.add_argument("--modelica-failure-pack-planner", required=True)
    parser.add_argument("--policy-experiment-runner", required=True)
    parser.add_argument("--moat-trend-snapshot", default=None)
    parser.add_argument("--replay-quality-guard", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_execution_forecast/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    pack = _load_json(args.modelica_failure_pack_planner)
    experiments = _load_json(args.policy_experiment_runner)
    moat = _load_json(args.moat_trend_snapshot)
    guard = _load_json(args.replay_quality_guard)

    reasons: list[str] = []
    if not pack:
        reasons.append("modelica_failure_pack_plan_missing")
    if not experiments:
        reasons.append("policy_experiment_runner_missing")

    forecast = _forecast_rows(pack, experiments, moat, guard) if (pack and experiments) else []
    base = next((x for x in forecast if x.get("scenario") == "base"), {})
    cautious = next((x for x in forecast if x.get("scenario") == "cautious"), {})

    guard_status = str(guard.get("status") or "NEEDS_REVIEW")
    recommended = str(experiments.get("recommended_experiment_id") or "")

    status = "PASS"
    recommendation = "EXECUTE_BASE_PLAN"
    preferred_scenario = "base"

    base_score = _to_float(base.get("projected_moat_score_30d", 0.0))
    cautious_score = _to_float(cautious.get("projected_moat_score_30d", 0.0))

    if not pack or not experiments:
        status = "FAIL"
        recommendation = "BLOCKED"
        preferred_scenario = "none"
    elif guard_status == "FAIL":
        status = "NEEDS_REVIEW"
        recommendation = "EXECUTE_CAUTIOUS_ONLY"
        preferred_scenario = "cautious"
        reasons.append("replay_quality_guard_failed")
    elif base_score < 65.0:
        status = "NEEDS_REVIEW"
        recommendation = "RAISE_COVERAGE_BEFORE_SCALING"
        reasons.append("forecast_below_target")

    if recommended and "aggressive" in recommended and guard_status != "PASS":
        reasons.append("aggressive_experiment_with_limited_confidence")
        if preferred_scenario == "base":
            preferred_scenario = "cautious"

    projected_score = base_score if preferred_scenario == "base" else cautious_score
    if preferred_scenario == "none":
        projected_score = 0.0

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "recommendation": recommendation,
        "preferred_scenario": preferred_scenario,
        "projected_moat_score_30d": _round(projected_score),
        "forecast": forecast,
        "reasons": sorted(set(reasons)),
        "sources": {
            "modelica_failure_pack_planner": args.modelica_failure_pack_planner,
            "policy_experiment_runner": args.policy_experiment_runner,
            "moat_trend_snapshot": args.moat_trend_snapshot,
            "replay_quality_guard": args.replay_quality_guard,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "recommendation": recommendation, "projected_moat_score_30d": payload["projected_moat_score_30d"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
