from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


SCHEMA_VERSION = "agent_modelica_post_restore_promotion_summary_v0_3_5"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_post_restore_promotion_summary_v0_3_5"
MIN_PROMOTION_CASES = 10
MIN_SUCCESS_RATE_PCT = 60.0


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_post_restore_promotion_summary(
    *,
    lane_summary_path: str,
    run_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane = _load_json(lane_summary_path)
    run = _load_json(run_summary_path)
    rows = run.get("results") if isinstance(run.get("results"), list) else []
    total = int(run.get("total") or len(rows))
    passed = int(run.get("passed") or 0)
    planner_invoked_count = int(run.get("planner_invoked_count") or 0)
    deterministic_only_count = int(run.get("deterministic_only_count") or 0)
    success_rate_pct = round(100.0 * passed / total, 1) if total else 0.0
    planner_invoked_pct = round(100.0 * planner_invoked_count / total, 1) if total else 0.0
    deterministic_only_pct = round(100.0 * deterministic_only_count / total, 1) if total else 0.0
    rule_then_llm_count = sum(1 for row in rows if str(row.get("resolution_path") or "") == "rule_then_llm")
    rule_then_llm_rate_pct = round(100.0 * rule_then_llm_count / total, 1) if total else 0.0
    rounds = [int(row.get("rounds_used") or 0) for row in rows if int(row.get("rounds_used") or 0) > 0]
    median_rounds = float(median(rounds)) if rounds else 0.0
    lane_status = str(lane.get("lane_status") or "")

    promotion_ready = bool(
        total >= MIN_PROMOTION_CASES
        and lane_status == "FREEZE_READY"
        and success_rate_pct >= MIN_SUCCESS_RATE_PCT
        and planner_invoked_pct >= 70.0
        and deterministic_only_pct <= 30.0
        and rule_then_llm_rate_pct >= 50.0
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PROMOTION_READY" if promotion_ready else "NEEDS_MORE_VALIDATION",
        "promotion_target": "simulate_error_parameter_recovery_sweep",
        "lane_summary_path": str(Path(lane_summary_path).resolve()) if Path(lane_summary_path).exists() else str(lane_summary_path),
        "run_summary_path": str(Path(run_summary_path).resolve()) if Path(run_summary_path).exists() else str(run_summary_path),
        "promotion_threshold": {
            "minimum_cases": MIN_PROMOTION_CASES,
            "minimum_success_rate_pct": MIN_SUCCESS_RATE_PCT,
            "minimum_planner_invoked_pct": 70.0,
            "maximum_deterministic_only_pct": 30.0,
            "minimum_rule_then_llm_rate_pct": 50.0,
        },
        "observed_metrics": {
            "lane_status": lane_status,
            "total_cases": total,
            "passed_cases": passed,
            "success_rate_pct": success_rate_pct,
            "planner_invoked_pct": planner_invoked_pct,
            "deterministic_only_pct": deterministic_only_pct,
            "rule_then_llm_count": rule_then_llm_count,
            "rule_then_llm_rate_pct": rule_then_llm_rate_pct,
            "median_rounds_used": median_rounds,
        },
        "decision": {
            "promote": promotion_ready,
            "reason": (
                "post-restore harder lane achieved freeze-ready status and converted planner-invoked failures into rule_then_llm successes"
                if promotion_ready
                else "promotion criteria not yet met for the post-restore parameter-recovery lever"
            ),
        },
        "next_actions": (
            [
                "Promote simulate_error_parameter_recovery_sweep as the primary v0.3.5 repair lever.",
                "Expand the post-restore lane toward residual conflicts that require more than a single numeric sweep.",
                "Use post-restore failure classification to separate verifier reject, wrong branch, and stalled search after deterministic progress.",
            ]
            if promotion_ready
            else [
                "Collect more post-restore live runs before promoting the parameter-recovery lever.",
            ]
        ),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    observed = payload.get("observed_metrics") if isinstance(payload.get("observed_metrics"), dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    lines = [
        "# Post-Restore Promotion Summary v0.3.5",
        "",
        f"- status: `{payload.get('status')}`",
        f"- promotion_target: `{payload.get('promotion_target')}`",
        f"- lane_status: `{observed.get('lane_status')}`",
        f"- total_cases: `{observed.get('total_cases')}`",
        f"- success_rate_pct: `{observed.get('success_rate_pct')}`",
        f"- planner_invoked_pct: `{observed.get('planner_invoked_pct')}`",
        f"- deterministic_only_pct: `{observed.get('deterministic_only_pct')}`",
        f"- rule_then_llm_rate_pct: `{observed.get('rule_then_llm_rate_pct')}`",
        f"- median_rounds_used: `{observed.get('median_rounds_used')}`",
        f"- promote: `{decision.get('promote')}`",
        f"- reason: `{decision.get('reason')}`",
        "",
        "## Next Actions",
        "",
    ]
    for idx, action in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {action}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize whether the v0.3.5 post-restore parameter-recovery lever should be promoted.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--run-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_post_restore_promotion_summary(
        lane_summary_path=str(args.lane_summary),
        run_summary_path=str(args.run_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "promote": (payload.get("decision") or {}).get("promote")}))


if __name__ == "__main__":
    main()
