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


def _status(v: object) -> str:
    return str(v or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Hard Evidence Plan v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- priority_band: `{payload.get('priority_band')}`",
        f"- execution_focus_score: `{payload.get('execution_focus_score')}`",
        f"- planned_actions_count: `{payload.get('planned_actions_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build short-cycle hard-evidence plan for moat execution")
    parser.add_argument("--modelica-representativeness-gate-summary", required=True)
    parser.add_argument("--mutation-depth-pressure-board-summary", required=True)
    parser.add_argument("--failure-distribution-stability-history-trend-summary", required=True)
    parser.add_argument("--moat-weekly-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_hard_evidence_plan_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    represent = _load_json(args.modelica_representativeness_gate_summary)
    depth_board = _load_json(args.mutation_depth_pressure_board_summary)
    stability_trend = _load_json(args.failure_distribution_stability_history_trend_summary)
    weekly = _load_json(args.moat_weekly_summary)

    reasons: list[str] = []
    if not represent:
        reasons.append("modelica_representativeness_gate_summary_missing")
    if not depth_board:
        reasons.append("mutation_depth_pressure_board_summary_missing")
    if not stability_trend:
        reasons.append("failure_distribution_stability_history_trend_summary_missing")

    represent_score = _to_float(represent.get("representativeness_score", 0.0))
    pressure_index = _to_float(depth_board.get("mutation_depth_pressure_index", 0.0))
    delta_stability = _to_float(stability_trend.get("trend", {}).get("delta_avg_stability_score", 0.0))
    delta_drift = _to_float(stability_trend.get("trend", {}).get("delta_avg_distribution_drift_score", 0.0))

    execution_focus_score = round(
        max(
            0.0,
            min(
                100.0,
                (represent_score * 0.35)
                + (max(0.0, 100.0 - pressure_index) * 0.4)
                + (max(0.0, 50.0 + delta_stability * 8.0 - delta_drift * 35.0) * 0.25),
            ),
        ),
        2,
    )

    actions: list[dict] = []
    if represent_score < 70.0:
        actions.append(
            {
                "action_id": "evidence.real_model_density",
                "priority": "P0",
                "target": "增加中大型真实Modelica模型并通过代表性门槛",
                "expected_delta": {"representativeness_score": "+8~+15"},
            }
        )
    if pressure_index > 35.0:
        actions.append(
            {
                "action_id": "evidence.mutation_depth_close",
                "priority": "P0",
                "target": "优先清理高风险mutation gap并提升执行覆盖",
                "expected_delta": {"mutation_depth_pressure_index": "-10~-20"},
            }
        )
    if delta_drift > 0.02 or delta_stability < 0:
        actions.append(
            {
                "action_id": "evidence.failure_stability_recover",
                "priority": "P1",
                "target": "稳定失败分布漂移并恢复stability趋势",
                "expected_delta": {
                    "delta_avg_distribution_drift_score": "<=0",
                    "delta_avg_stability_score": ">=0",
                },
            }
        )

    weekly_status = _status(weekly.get("status")) if weekly else "UNKNOWN"
    if weekly_status in {"NEEDS_REVIEW", "FAIL"}:
        actions.append(
            {
                "action_id": "evidence.weekly_chain_recover",
                "priority": "P1",
                "target": "恢复moat weekly chain到PASS并保持连续",
                "expected_delta": {"weekly_status": "PASS"},
            }
        )

    if not actions:
        actions.append(
            {
                "action_id": "evidence.publish_anchor",
                "priority": "P2",
                "target": "发布本周护城河证据页与复现实验摘要",
                "expected_delta": {"external_signal_strength": "+1"},
            }
        )

    priority_band = "HIGH"
    if execution_focus_score >= 80.0 and pressure_index <= 30.0:
        priority_band = "STABLE"
    elif execution_focus_score >= 65.0 and pressure_index <= 45.0:
        priority_band = "MEDIUM"

    alerts: list[str] = []
    if represent_score < 70.0:
        alerts.append("representativeness_low")
    if pressure_index > 35.0:
        alerts.append("mutation_depth_pressure_high")
    if delta_drift > 0.02:
        alerts.append("distribution_drift_worsening")
    if delta_stability < 0:
        alerts.append("stability_trend_worsening")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "priority_band": priority_band,
        "execution_focus_score": execution_focus_score,
        "planned_actions_count": len(actions),
        "planned_actions": actions,
        "signals": {
            "representativeness_score": represent_score,
            "mutation_depth_pressure_index": pressure_index,
            "delta_avg_stability_score": delta_stability,
            "delta_avg_distribution_drift_score": delta_drift,
            "weekly_status": weekly_status,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "modelica_representativeness_gate_summary": args.modelica_representativeness_gate_summary,
            "mutation_depth_pressure_board_summary": args.mutation_depth_pressure_board_summary,
            "failure_distribution_stability_history_trend_summary": args.failure_distribution_stability_history_trend_summary,
            "moat_weekly_summary": args.moat_weekly_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "priority_band": priority_band, "planned_actions_count": len(actions)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
