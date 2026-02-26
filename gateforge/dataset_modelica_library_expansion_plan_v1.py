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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Library Expansion Plan v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- expansion_readiness_score: `{payload.get('expansion_readiness_score')}`",
        f"- weekly_new_models_target: `{payload.get('weekly_new_models_target')}`",
        f"- target_large_models_weekly: `{payload.get('target_large_models_weekly')}`",
        f"- target_medium_models_weekly: `{payload.get('target_medium_models_weekly')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly Modelica library expansion plan from intake, coverage, and saturation signals")
    parser.add_argument("--open-source-intake-summary", required=True)
    parser.add_argument("--modelica-library-registry-summary", required=True)
    parser.add_argument("--failure-corpus-saturation-summary", required=True)
    parser.add_argument("--large-coverage-push-v1-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_modelica_library_expansion_plan_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    intake = _load_json(args.open_source_intake_summary)
    registry = _load_json(args.modelica_library_registry_summary)
    saturation = _load_json(args.failure_corpus_saturation_summary)
    large_push = _load_json(args.large_coverage_push_v1_summary)

    reasons: list[str] = []
    if not intake:
        reasons.append("open_source_intake_summary_missing")
    if not registry:
        reasons.append("modelica_library_registry_summary_missing")
    if not saturation:
        reasons.append("failure_corpus_saturation_summary_missing")
    if not large_push:
        reasons.append("large_coverage_push_summary_missing")

    accepted = _to_int(intake.get("accepted_count", 0))
    rejected = _to_int(intake.get("rejected_count", 0))
    total_assets = _to_int(registry.get("total_assets", 0))
    scale_counts = registry.get("scale_counts") if isinstance(registry.get("scale_counts"), dict) else {}
    medium_assets = _to_int(scale_counts.get("medium", 0))
    large_assets = _to_int(scale_counts.get("large", 0))
    saturation_index = _to_float(saturation.get("saturation_index", 0.0))
    gap_actions = _to_int(saturation.get("total_gap_actions", 0))
    push_large_target = _to_int(large_push.get("push_target_large_cases", 0))

    acceptance_ratio = _round((accepted / max(1, accepted + rejected)) * 100.0)
    base_target = max(2, min(10, 2 + accepted + (gap_actions // 2)))
    target_large = max(2, min(base_target, max(push_large_target, gap_actions // 2)))
    target_medium = max(2, min(base_target, 2 + (gap_actions // 3)))
    target_small = max(1, base_target - min(base_target - 1, target_large + target_medium))

    if large_assets < medium_assets:
        target_large = min(base_target, target_large + 1)
    if saturation_index < 70:
        target_medium = min(base_target, target_medium + 1)

    backlog_risk = 0
    if gap_actions > 0:
        backlog_risk += 2
    if push_large_target > 0:
        backlog_risk += 2
    if acceptance_ratio < 50.0:
        backlog_risk += 1

    readiness_score = _round(
        _clamp(
            (acceptance_ratio * 0.28)
            + (min(100.0, saturation_index) * 0.34)
            + (min(100.0, total_assets * 2.0) * 0.18)
            + (30.0 if large_assets > 0 and medium_assets > 0 else 12.0)
            - (backlog_risk * 5.0)
        )
    )

    channels = [
        {
            "channel": "open_source_intake",
            "weekly_target": max(1, base_target // 2),
            "focus_scale": "medium",
        },
        {
            "channel": "large_model_synthesizer",
            "weekly_target": target_large,
            "focus_scale": "large",
        },
        {
            "channel": "manual_modelica_authoring",
            "weekly_target": max(1, base_target // 3),
            "focus_scale": "large",
        },
    ]

    alerts: list[str] = []
    if push_large_target > 0:
        alerts.append("large_coverage_debt_open")
    if gap_actions > 0:
        alerts.append("failure_saturation_gaps_open")
    if acceptance_ratio < 45.0:
        alerts.append("intake_acceptance_ratio_low")
    if readiness_score < 72.0:
        alerts.append("expansion_readiness_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "expansion_readiness_score": readiness_score,
        "weekly_new_models_target": base_target,
        "target_large_models_weekly": target_large,
        "target_medium_models_weekly": target_medium,
        "target_small_models_weekly": target_small,
        "channels": channels,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "accepted_count": accepted,
            "rejected_count": rejected,
            "acceptance_ratio_pct": acceptance_ratio,
            "registry_total_assets": total_assets,
            "registry_medium_assets": medium_assets,
            "registry_large_assets": large_assets,
            "saturation_index": saturation_index,
            "saturation_gap_actions": gap_actions,
            "push_target_large_cases": push_large_target,
        },
        "sources": {
            "open_source_intake_summary": args.open_source_intake_summary,
            "modelica_library_registry_summary": args.modelica_library_registry_summary,
            "failure_corpus_saturation_summary": args.failure_corpus_saturation_summary,
            "large_coverage_push_v1_summary": args.large_coverage_push_v1_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "expansion_readiness_score": readiness_score, "weekly_new_models_target": base_target}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
