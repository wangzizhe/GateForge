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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Ingest Source Channel Planner v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- readiness_score: `{payload.get('readiness_score')}`",
        f"- total_channels: `{payload.get('total_channels')}`",
        f"- p0_channels: `{payload.get('p0_channels')}`",
        f"- planned_weekly_new_models: `{payload.get('planned_weekly_new_models')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan source ingest channels to expand real Modelica model intake")
    parser.add_argument("--asset-discovery-summary", required=True)
    parser.add_argument("--intake-runner-summary", required=True)
    parser.add_argument("--canonical-registry-summary", required=True)
    parser.add_argument("--coverage-backfill-summary", default=None)
    parser.add_argument("--profile-config", default=None)
    parser.add_argument("--target-weekly-new-models", type=int, default=24)
    parser.add_argument("--target-large-ratio-pct", type=float, default=30.0)
    parser.add_argument("--min-ready-discovered-models", type=int, default=12)
    parser.add_argument("--min-ready-accepted-models", type=int, default=6)
    parser.add_argument(
        "--plan-out",
        default="artifacts/dataset_ingest_source_channel_planner_v1/channels.json",
    )
    parser.add_argument("--out", default="artifacts/dataset_ingest_source_channel_planner_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    discovery = _load_json(args.asset_discovery_summary)
    runner = _load_json(args.intake_runner_summary)
    canonical = _load_json(args.canonical_registry_summary)
    backfill = _load_json(args.coverage_backfill_summary)
    profile = _load_json(args.profile_config)

    reasons: list[str] = []
    if not discovery:
        reasons.append("asset_discovery_summary_missing")
    if not runner:
        reasons.append("intake_runner_summary_missing")
    if not canonical:
        reasons.append("canonical_registry_summary_missing")

    discovered_models = _to_int(discovery.get("total_candidates", 0))
    accepted_models = _to_int(runner.get("accepted_count", 0))
    accepted_large_models = _to_int(runner.get("accepted_large_count", 0))
    rejected_models = _to_int(runner.get("rejected_count", 0))
    canonical_new_models = _to_int(canonical.get("canonical_new_models", 0))
    canonical_net_growth_models = _to_int(canonical.get("canonical_net_growth_models", 0))
    backfill_p0 = _to_int(backfill.get("p0_tasks", 0))
    backfill_total = _to_int(backfill.get("total_tasks", 0))

    accepted_large_ratio_pct = round((accepted_large_models / max(1, accepted_models)) * 100.0, 2)
    acceptance_ratio_pct = round((accepted_models / max(1, accepted_models + rejected_models)) * 100.0, 2)

    deficit_models = max(0, int(args.target_weekly_new_models) - accepted_models)
    deficit_large_ratio = max(0.0, float(args.target_large_ratio_pct) - accepted_large_ratio_pct)
    high_reject_pressure = acceptance_ratio_pct < 55.0

    channels = [
        {
            "channel_id": "open_source_shard_expansion",
            "priority": "P0" if deficit_models > 0 else "P1",
            "focus_scale": "medium",
            "weekly_target_models": max(4, deficit_models // 2 if deficit_models > 0 else max(2, accepted_models // 3)),
            "selection_strategy": "top_libraries_with_medium_density",
            "activation_reason": "weekly_model_deficit" if deficit_models > 0 else "maintain_pipeline_supply",
        },
        {
            "channel_id": "large_model_reference_pull",
            "priority": "P0" if deficit_large_ratio > 0 else "P1",
            "focus_scale": "large",
            "weekly_target_models": max(2, int(round(deficit_large_ratio / 10.0)) + 1),
            "selection_strategy": "large_packages_and_system_examples",
            "activation_reason": "large_ratio_gap" if deficit_large_ratio > 0 else "keep_large_pool_fresh",
        },
        {
            "channel_id": "internal_manual_authoring",
            "priority": "P1",
            "focus_scale": "large",
            "weekly_target_models": max(1, 1 + backfill_p0),
            "selection_strategy": "author_missing_failure_modes",
            "activation_reason": "coverage_backfill_pressure" if backfill_total > 0 else "steady_large_growth",
        },
        {
            "channel_id": "license_safe_partner_exports",
            "priority": "P1" if high_reject_pressure else "P2",
            "focus_scale": "mixed",
            "weekly_target_models": max(1, deficit_models // 4 + 1),
            "selection_strategy": "high_quality_curated_exports",
            "activation_reason": "quality_reject_pressure" if high_reject_pressure else "diversify_source_mix",
        },
    ]
    channels.sort(key=lambda x: (str(x.get("priority") or "P9"), -_to_int(x.get("weekly_target_models", 0)), str(x.get("channel_id") or "")))

    readiness_score = round(
        max(
            0.0,
            min(
                100.0,
                (accepted_models * 4.0)
                + (accepted_large_ratio_pct * 0.6)
                + (max(0, canonical_net_growth_models) * 3.0)
                + min(20.0, acceptance_ratio_pct * 0.2)
                - min(20.0, backfill_p0 * 3.0),
            ),
        ),
        2,
    )

    alerts: list[str] = []
    if discovered_models < int(args.min_ready_discovered_models):
        alerts.append("discovered_models_below_ready_threshold")
    if accepted_models < int(args.min_ready_accepted_models):
        alerts.append("accepted_models_below_ready_threshold")
    if accepted_large_ratio_pct < float(args.target_large_ratio_pct):
        alerts.append("accepted_large_ratio_below_target")
    if canonical_net_growth_models <= 0:
        alerts.append("canonical_net_growth_not_positive")
    if backfill_p0 > 0:
        alerts.append("backfill_p0_tasks_open")
    if high_reject_pressure:
        alerts.append("acceptance_ratio_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    plan = {
        "schema_version": "ingest_source_channel_planner_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "channels": channels,
    }
    _write_json(args.plan_out, plan)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "readiness_score": readiness_score,
        "total_channels": len(channels),
        "p0_channels": len([x for x in channels if str(x.get("priority") or "") == "P0"]),
        "planned_weekly_new_models": sum(_to_int(x.get("weekly_target_models", 0)) for x in channels),
        "signals": {
            "discovered_models": discovered_models,
            "accepted_models": accepted_models,
            "accepted_large_models": accepted_large_models,
            "accepted_large_ratio_pct": accepted_large_ratio_pct,
            "acceptance_ratio_pct": acceptance_ratio_pct,
            "canonical_new_models": canonical_new_models,
            "canonical_net_growth_models": canonical_net_growth_models,
            "backfill_total_tasks": backfill_total,
            "backfill_p0_tasks": backfill_p0,
            "model_scale_profile": profile.get("model_scale_profile"),
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "plan_path": args.plan_out,
        "sources": {
            "asset_discovery_summary": args.asset_discovery_summary,
            "intake_runner_summary": args.intake_runner_summary,
            "canonical_registry_summary": args.canonical_registry_summary,
            "coverage_backfill_summary": args.coverage_backfill_summary,
            "profile_config": args.profile_config,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_channels": len(channels), "p0_channels": payload["p0_channels"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
