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


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _round(value: float) -> float:
    return round(value, 2)


def _compute_metrics(evidence_pack: dict, registry: dict, backlog: dict, replay_eval: dict) -> dict:
    evidence_strength = _to_float(evidence_pack.get("evidence_strength_score", 0.0))
    sections_present = _to_int(evidence_pack.get("evidence_sections_present", 0))

    total_records = _to_int(registry.get("total_records", 0))
    missing_scales = len(registry.get("missing_model_scales") or []) if isinstance(registry.get("missing_model_scales"), list) else 3
    scale_coverage_score = (3 - min(3, missing_scales)) * 10

    coverage_depth_index = _clamp((min(50, total_records * 2.0) + scale_coverage_score + min(20, sections_present * 2.0)))

    replay_score = _to_int(replay_eval.get("evaluation_score", 0))
    replay_status = str(replay_eval.get("status") or "")
    replay_status_bonus = 8 if replay_status == "PASS" else (2 if replay_status == "NEEDS_REVIEW" else -6)
    governance_effectiveness_index = _clamp((evidence_strength * 0.65) + ((replay_score + 5) * 3.5) + replay_status_bonus)

    p0_count = _to_int(((backlog.get("priority_counts") or {}).get("P0", 0)))
    open_tasks = _to_int(backlog.get("total_open_tasks", 0))
    replay_reco = str(replay_eval.get("recommendation") or "")
    reco_bonus = 10 if replay_reco == "ADOPT_PATCH" else (3 if replay_reco == "LIMITED_ROLLOUT" else -8)
    policy_learning_velocity = _clamp(55 - min(25, p0_count * 6) - min(10, int(open_tasks / 2)) + reco_bonus)

    moat_score = _clamp((coverage_depth_index * 0.4) + (governance_effectiveness_index * 0.4) + (policy_learning_velocity * 0.2))

    return {
        "coverage_depth_index": _round(coverage_depth_index),
        "governance_effectiveness_index": _round(governance_effectiveness_index),
        "policy_learning_velocity": _round(policy_learning_velocity),
        "moat_score": _round(moat_score),
    }


def _compute_status(moat_score: float, evidence_status: str) -> str:
    if evidence_status == "FAIL":
        return "FAIL"
    if moat_score >= 70:
        return "PASS"
    return "NEEDS_REVIEW"


def _trend(current: dict, previous: dict) -> dict:
    prev_metrics = previous.get("metrics") if isinstance(previous.get("metrics"), dict) else {}
    curr_metrics = current.get("metrics") if isinstance(current.get("metrics"), dict) else {}

    def delta(key: str) -> float:
        return _round(_to_float(curr_metrics.get(key, 0.0)) - _to_float(prev_metrics.get(key, 0.0)))

    status_transition = f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"
    moat_delta = delta("moat_score")
    alerts: list[str] = []
    if moat_delta < -5:
        alerts.append("moat_score_drop_significant")
    if status_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("status_worsened")

    return {
        "status_transition": status_transition,
        "delta": {
            "coverage_depth_index": delta("coverage_depth_index"),
            "governance_effectiveness_index": delta("governance_effectiveness_index"),
            "policy_learning_velocity": delta("policy_learning_velocity"),
            "moat_score": moat_delta,
        },
        "alerts": alerts,
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Moat Trend Snapshot",
        "",
        f"- status: `{payload.get('status')}`",
        f"- moat_score: `{metrics.get('moat_score')}`",
        f"- coverage_depth_index: `{metrics.get('coverage_depth_index')}`",
        f"- governance_effectiveness_index: `{metrics.get('governance_effectiveness_index')}`",
        f"- policy_learning_velocity: `{metrics.get('policy_learning_velocity')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- moat_score_delta: `{(trend.get('delta') or {}).get('moat_score')}`",
        "",
        "## Trend Alerts",
        "",
    ]
    alerts = trend.get("alerts") if isinstance(trend.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build moat trend snapshot from governance evidence signals")
    parser.add_argument("--evidence-pack", required=True)
    parser.add_argument("--failure-corpus-registry-summary", default=None)
    parser.add_argument("--blind-spot-backlog", default=None)
    parser.add_argument("--policy-patch-replay-evaluator", default=None)
    parser.add_argument("--previous-snapshot", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_trend_snapshot/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    evidence_pack = _load_json(args.evidence_pack)
    registry = _load_json(args.failure_corpus_registry_summary)
    backlog = _load_json(args.blind_spot_backlog)
    replay_eval = _load_json(args.policy_patch_replay_evaluator)
    previous = _load_json(args.previous_snapshot)

    metrics = _compute_metrics(evidence_pack, registry, backlog, replay_eval)
    status = _compute_status(_to_float(metrics.get("moat_score", 0.0)), str(evidence_pack.get("status") or ""))

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "metrics": metrics,
        "sources": {
            "evidence_pack": args.evidence_pack,
            "failure_corpus_registry_summary": args.failure_corpus_registry_summary,
            "blind_spot_backlog": args.blind_spot_backlog,
            "policy_patch_replay_evaluator": args.policy_patch_replay_evaluator,
            "previous_snapshot": args.previous_snapshot,
        },
    }
    summary["trend"] = _trend(summary, previous if previous else {"status": status, "metrics": metrics})

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "moat_score": metrics.get("moat_score")}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
