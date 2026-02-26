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


def _extract_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Campaign Tracker v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- campaign_phase: `{payload.get('campaign_phase')}`",
        f"- planned_weekly_mutations: `{payload.get('planned_weekly_mutations')}`",
        f"- executed_weekly_mutations: `{payload.get('executed_weekly_mutations')}`",
        f"- completion_ratio_pct: `{payload.get('completion_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track weekly mutation campaign progress using portfolio, expansion, and evidence-chain signals")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-portfolio-balance-summary", required=True)
    parser.add_argument("--modelica-library-expansion-plan-summary", required=True)
    parser.add_argument("--evidence-chain-summary", required=True)
    parser.add_argument("--replay-observation-store-summary", default=None)
    parser.add_argument("--large-model-benchmark-pack-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_mutation_campaign_tracker_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    portfolio = _load_json(args.mutation_portfolio_balance_summary)
    expansion = _load_json(args.modelica_library_expansion_plan_summary)
    chain = _load_json(args.evidence_chain_summary)
    replay_store = _load_json(args.replay_observation_store_summary)
    large_pack = _load_json(args.large_model_benchmark_pack_summary)

    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not portfolio:
        reasons.append("mutation_portfolio_balance_summary_missing")
    if not expansion:
        reasons.append("modelica_library_expansion_plan_summary_missing")
    if not chain:
        reasons.append("evidence_chain_summary_missing")

    mutations = _extract_mutations(manifest)
    total_mutations = len(mutations)
    rebalance_actions = portfolio.get("rebalance_actions") if isinstance(portfolio.get("rebalance_actions"), list) else []
    rebalance_count = len(rebalance_actions)
    expansion_target = _to_int(expansion.get("weekly_new_models_target", 0))
    pack_target = _to_int(large_pack.get("selected_large_mutations", 0))

    planned_weekly = max(4, min(total_mutations, (expansion_target * 2) + (rebalance_count * 2) + max(0, pack_target // 3)))
    executed_weekly = _to_int(replay_store.get("ingested_records", replay_store.get("total_store_records", 0)))
    completion_ratio = _ratio(executed_weekly, planned_weekly)

    chain_status = str(chain.get("status") or "UNKNOWN")
    portfolio_status = str(portfolio.get("status") or "UNKNOWN")
    chain_score = _to_float(chain.get("chain_health_score", 0.0))
    portfolio_score = _to_float(portfolio.get("portfolio_balance_score", 0.0))

    campaign_phase = "scale_out"
    if completion_ratio >= 100.0 and chain_status == "PASS" and portfolio_status == "PASS":
        campaign_phase = "accelerate"
    elif completion_ratio < 60.0 or chain_status != "PASS":
        campaign_phase = "stabilize"

    alerts: list[str] = []
    if completion_ratio < 70.0:
        alerts.append("weekly_completion_ratio_low")
    if chain_status != "PASS":
        alerts.append("evidence_chain_not_pass")
    if portfolio_status != "PASS":
        alerts.append("portfolio_balance_not_pass")
    if planned_weekly > total_mutations and total_mutations > 0:
        alerts.append("planned_weekly_exceeds_manifest_supply")
    if chain_score < 70.0:
        alerts.append("chain_health_score_below_target")
    if portfolio_score < 72.0:
        alerts.append("portfolio_balance_score_below_target")

    lane_allocations = {
        "large_lane_target": max(1, int(round(planned_weekly * 0.4))),
        "medium_lane_target": max(1, int(round(planned_weekly * 0.35))),
        "small_lane_target": max(1, planned_weekly - max(1, int(round(planned_weekly * 0.4))) - max(1, int(round(planned_weekly * 0.35)))),
    }

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign_phase": campaign_phase,
        "planned_weekly_mutations": planned_weekly,
        "executed_weekly_mutations": executed_weekly,
        "completion_ratio_pct": completion_ratio,
        "total_manifest_mutations": total_mutations,
        "lane_allocations": lane_allocations,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "rebalance_action_count": rebalance_count,
            "expansion_weekly_new_models_target": expansion_target,
            "large_pack_selected_mutations": pack_target,
            "chain_status": chain_status,
            "chain_health_score": chain_score,
            "portfolio_status": portfolio_status,
            "portfolio_balance_score": portfolio_score,
        },
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "mutation_portfolio_balance_summary": args.mutation_portfolio_balance_summary,
            "modelica_library_expansion_plan_summary": args.modelica_library_expansion_plan_summary,
            "evidence_chain_summary": args.evidence_chain_summary,
            "replay_observation_store_summary": args.replay_observation_store_summary,
            "large_model_benchmark_pack_summary": args.large_model_benchmark_pack_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "campaign_phase": campaign_phase, "completion_ratio_pct": completion_ratio}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
