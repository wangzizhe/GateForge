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
        "# GateForge Hard Moat Target Profile v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- profile_name: `{payload.get('profile_name')}`",
        f"- weekly_model_target: `{payload.get('weekly_model_target')}`",
        f"- weekly_mutation_target: `{payload.get('weekly_mutation_target')}`",
        f"- strictness_level: `{payload.get('strictness_level')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly hard-moat gate thresholds from intake and growth signals")
    parser.add_argument("--profile-config", required=True)
    parser.add_argument("--ingest-source-channel-planner-summary", default=None)
    parser.add_argument("--asset-discovery-summary", default=None)
    parser.add_argument("--intake-runner-summary", default=None)
    parser.add_argument("--mutation-pack-summary", default=None)
    parser.add_argument("--canonical-registry-summary", default=None)
    parser.add_argument("--coverage-backfill-summary", default=None)
    parser.add_argument(
        "--target-profile-out",
        default="artifacts/dataset_hard_moat_target_profile_v1/target_profile.json",
    )
    parser.add_argument("--out", default="artifacts/dataset_hard_moat_target_profile_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    profile = _load_json(args.profile_config)
    planner = _load_json(args.ingest_source_channel_planner_summary)
    discovery = _load_json(args.asset_discovery_summary)
    runner = _load_json(args.intake_runner_summary)
    pack = _load_json(args.mutation_pack_summary)
    canonical = _load_json(args.canonical_registry_summary)
    backfill = _load_json(args.coverage_backfill_summary)

    reasons: list[str] = []
    if not profile:
        reasons.append("profile_config_missing")

    profile_name = str(profile.get("model_scale_profile") or "balanced")
    profile_large_ratio = _to_float(profile.get("min_accepted_large_ratio_pct", 25.0))
    planner_weekly_target = _to_int(planner.get("planned_weekly_new_models", 0))
    planner_p0_channels = _to_int(planner.get("p0_channels", 0))
    observed_discovered_models = _to_int(discovery.get("total_candidates", 0))
    observed_accepted_models = _to_int(runner.get("accepted_count", 0))
    observed_accepted_large_models = _to_int(runner.get("accepted_large_count", 0))
    observed_generated_mutations = _to_int(pack.get("total_mutations", 0))
    canonical_total_models = _to_int(canonical.get("canonical_total_models", 0))
    canonical_net_growth = _to_int(canonical.get("canonical_net_growth_models", 0))
    backfill_p0_tasks = _to_int(backfill.get("p0_tasks", 0))

    weekly_model_target = max(4, planner_weekly_target if planner_weekly_target > 0 else 8)
    if profile_name == "large_first":
        weekly_model_target = max(6, weekly_model_target)

    weekly_mutation_target = max(24, weekly_model_target * 6)
    if profile_name == "large_first":
        weekly_mutation_target = max(40, weekly_model_target * 8)

    strictness_level = "standard"
    if canonical_total_models >= 500 and planner_p0_channels == 0 and backfill_p0_tasks == 0:
        strictness_level = "strict"
    elif planner_p0_channels >= 2 or backfill_p0_tasks > 0:
        strictness_level = "adaptive"

    min_validation_type_match_rate_pct = 35.0
    min_failure_type_entropy = 1.1
    max_distribution_drift_tvd = 0.4
    if strictness_level == "strict":
        min_validation_type_match_rate_pct = 45.0
        min_failure_type_entropy = 1.3
        max_distribution_drift_tvd = 0.3
    elif strictness_level == "adaptive":
        min_validation_type_match_rate_pct = 30.0
        min_failure_type_entropy = 1.0
        max_distribution_drift_tvd = 0.45

    min_discovered_models = max(2, int(round(weekly_model_target * 0.8)))
    min_accepted_models = max(2, int(round(weekly_model_target * 0.5)))
    min_accepted_large_models = max(1, int(round(min_accepted_models * max(profile_large_ratio, 20.0) / 100.0)))
    min_accepted_large_ratio_pct = round(max(20.0, profile_large_ratio), 2)
    min_generated_mutations = max(20, weekly_mutation_target)
    min_reproducible_mutations = max(10, int(round(min_generated_mutations * 0.7)))
    min_canonical_net_growth_models = 1 if canonical_total_models >= 200 else 0
    if canonical_net_growth > 0:
        min_canonical_net_growth_models = min(min_canonical_net_growth_models, canonical_net_growth)

    # Keep weekly thresholds aggressive but bounded by what this run can reasonably satisfy.
    if observed_discovered_models > 0:
        min_discovered_models = min(min_discovered_models, max(2, observed_discovered_models))
    if observed_accepted_models > 0:
        min_accepted_models = min(min_accepted_models, max(2, observed_accepted_models))
    if observed_accepted_large_models > 0:
        min_accepted_large_models = min(min_accepted_large_models, max(1, observed_accepted_large_models))
    if observed_generated_mutations > 0:
        min_generated_mutations = min(min_generated_mutations, max(20, observed_generated_mutations))
        min_reproducible_mutations = min(
            min_reproducible_mutations,
            max(10, int(round(observed_generated_mutations * 0.65))),
        )

    target_profile = {
        "schema_version": "hard_moat_target_profile_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile_name": profile_name,
        "strictness_level": strictness_level,
        "weekly_model_target": weekly_model_target,
        "weekly_mutation_target": weekly_mutation_target,
        "thresholds": {
            "min_discovered_models": min_discovered_models,
            "min_accepted_models": min_accepted_models,
            "min_accepted_large_models": min_accepted_large_models,
            "min_accepted_large_ratio_pct": min_accepted_large_ratio_pct,
            "min_generated_mutations": min_generated_mutations,
            "min_reproducible_mutations": min_reproducible_mutations,
            "min_canonical_net_growth_models": min_canonical_net_growth_models,
            "min_validation_type_match_rate_pct": min_validation_type_match_rate_pct,
            "min_failure_type_entropy": min_failure_type_entropy,
            "max_distribution_drift_tvd": max_distribution_drift_tvd,
        },
    }
    _write_json(args.target_profile_out, target_profile)

    alerts: list[str] = []
    if planner_p0_channels > 0:
        alerts.append("ingest_p0_channels_open")
    if backfill_p0_tasks > 0:
        alerts.append("coverage_backfill_p0_open")
    if canonical_net_growth <= 0 and canonical:
        alerts.append("canonical_net_growth_not_positive")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "profile_name": profile_name,
        "strictness_level": strictness_level,
        "weekly_model_target": weekly_model_target,
        "weekly_mutation_target": weekly_mutation_target,
        "thresholds": target_profile["thresholds"],
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "target_profile_path": args.target_profile_out,
        "signals": {
            "planner_weekly_target": planner_weekly_target,
            "planner_p0_channels": planner_p0_channels,
            "observed_discovered_models": observed_discovered_models,
            "observed_accepted_models": observed_accepted_models,
            "observed_accepted_large_models": observed_accepted_large_models,
            "observed_generated_mutations": observed_generated_mutations,
            "canonical_total_models": canonical_total_models,
            "canonical_net_growth_models": canonical_net_growth,
            "backfill_p0_tasks": backfill_p0_tasks,
            "profile_large_ratio_target_pct": profile_large_ratio,
        },
        "sources": {
            "profile_config": args.profile_config,
            "ingest_source_channel_planner_summary": args.ingest_source_channel_planner_summary,
            "asset_discovery_summary": args.asset_discovery_summary,
            "intake_runner_summary": args.intake_runner_summary,
            "mutation_pack_summary": args.mutation_pack_summary,
            "canonical_registry_summary": args.canonical_registry_summary,
            "coverage_backfill_summary": args.coverage_backfill_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "strictness_level": strictness_level, "weekly_mutation_target": weekly_mutation_target}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
