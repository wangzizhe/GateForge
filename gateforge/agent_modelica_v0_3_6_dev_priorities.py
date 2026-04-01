from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_6_dev_priorities"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_6_dev_priorities"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _failure_counts(classifier: dict) -> dict:
    metrics = classifier.get("metrics")
    if isinstance(metrics, dict):
        counts = metrics.get("failure_bucket_counts")
        if isinstance(counts, dict):
            return counts
    return {}


def _next_bottleneck_from_counts(counts: dict) -> tuple[str, str]:
    stalled = int(counts.get("stalled_search_after_progress") or 0)
    wrong_branch = int(counts.get("wrong_branch_after_restore") or 0)
    verifier_reject = int(counts.get("verifier_reject_after_restore") or 0)
    residual_semantic = int(counts.get("residual_semantic_conflict_after_restore") or 0)
    success_beyond = int(counts.get("success_beyond_single_sweep") or 0)

    if wrong_branch > 0:
        return "branch_followup_policy", "wrong_branch_after_restore_present"
    if verifier_reject > 0:
        return "verifier_consistent_followup", "verifier_reject_after_restore_present"
    if stalled > 0:
        return "guided_replan_after_progress", "stalled_search_after_progress_present"
    if residual_semantic > 0:
        return "post_restore_semantic_followup", "residual_semantic_conflict_after_restore_present"
    if success_beyond >= 3:
        return "multi_step_followup_policy", "success_beyond_single_sweep_majority"
    return "", ""


def build_v0_3_6_dev_priorities(
    *,
    lane_summary_path: str,
    classifier_summary_path: str,
    operator_analysis_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    lane_wrapper = _load_json(lane_summary_path)
    lane = lane_wrapper.get("lane_summary") if isinstance(lane_wrapper.get("lane_summary"), dict) else lane_wrapper
    classifier = _load_json(classifier_summary_path)
    operator = _load_json(operator_analysis_summary_path)

    counts = _failure_counts(classifier)
    composition = lane.get("composition") if isinstance(lane.get("composition"), dict) else {}
    threshold_checks = lane.get("threshold_checks") if isinstance(lane.get("threshold_checks"), dict) else {}
    success_beyond = int((classifier.get("metrics") or {}).get("success_beyond_single_sweep_count") or 0)
    success_beyond_rate = float((classifier.get("metrics") or {}).get("success_beyond_single_sweep_rate_pct") or 0.0)
    single_sweep_rate = float(composition.get("single_sweep_success_rate_pct") or 0.0)
    lane_status = _norm(lane.get("lane_status"))
    recommended_operator = _norm(operator.get("recommended_operator"))

    next_bottleneck, bottleneck_reason = _next_bottleneck_from_counts(counts)
    deterministic_coverage_extends = single_sweep_rate > 0.0
    identified_next_bottleneck = bool(next_bottleneck)
    status = "PASS" if identified_next_bottleneck or deterministic_coverage_extends else "PARTIAL"

    next_actions = []
    if identified_next_bottleneck:
        next_actions.append(
            f"Treat `{next_bottleneck}` as the next v0.3.6 capability lever because `{bottleneck_reason}` was observed on the collapse-only harder lane."
        )
    if deterministic_coverage_extends:
        next_actions.append(
            f"Preserve the explanation that baseline single-sweep coverage still resolves `{single_sweep_rate}%` of the collapse-only lane, so future generation should avoid those subfamilies."
        )
    next_actions.append(
        f"Continue expanding `{recommended_operator or 'paired_value_collapse'}` instead of weaker operators while keeping the v0.3.5 baseline measurement protocol fixed in authority artifacts."
    )
    next_actions.append(
        "Keep comparative work in maintenance-only mode until the v0.3.6 comparative reopen checkpoint is explicitly generated."
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "primary_harder_direction": {
            "family_id": "post_restore_residual_semantic_conflict",
            "operator": recommended_operator or "paired_value_collapse",
            "lane_status": lane_status,
        },
        "next_bottleneck": {
            "lever": next_bottleneck,
            "reason": bottleneck_reason,
            "identified": identified_next_bottleneck,
        },
        "deterministic_coverage_explanation": {
            "present": deterministic_coverage_extends,
            "single_sweep_success_rate_pct": single_sweep_rate,
            "explanation": (
                "single_sweep_coverage_still_present_on_collapse_lane"
                if deterministic_coverage_extends
                else ""
            ),
        },
        "evidence": {
            "success_beyond_single_sweep_count": success_beyond,
            "success_beyond_single_sweep_rate_pct": success_beyond_rate,
            "threshold_checks": threshold_checks,
            "failure_bucket_counts": counts,
        },
        "roadmap_continuity": {
            "from_v0_3_5": "simulate_error_parameter_recovery_sweep",
            "to_v0_3_6": "post_restore_residual_semantic_conflict",
            "comparative_mode": "maintenance_only",
        },
        "next_actions": next_actions,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica v0.3.6 Dev Priorities",
        "",
        f"- status: `{payload.get('status')}`",
        f"- primary_harder_direction: `{(payload.get('primary_harder_direction') or {}).get('family_id')}`",
        f"- next_bottleneck: `{(payload.get('next_bottleneck') or {}).get('lever')}`",
        f"- deterministic_coverage_present: `{(payload.get('deterministic_coverage_explanation') or {}).get('present')}`",
        "",
        "## Next Actions",
        "",
    ]
    for idx, item in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build actionable v0.3.6 development priorities from harder-lane evidence.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--operator-analysis-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_6_dev_priorities(
        lane_summary_path=str(args.lane_summary),
        classifier_summary_path=str(args.classifier_summary),
        operator_analysis_summary_path=str(args.operator_analysis_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_bottleneck": (payload.get("next_bottleneck") or {}).get("lever")}))


if __name__ == "__main__":
    main()
