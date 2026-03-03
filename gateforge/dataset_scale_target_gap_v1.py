from __future__ import annotations

import argparse
import json
import math
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


def _progress(current: float, target: float) -> float:
    if target <= 0:
        return 100.0
    return round(max(0.0, min(100.0, (current / target) * 100.0)), 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Scale Target Gap v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- overall_progress_pct: `{payload.get('overall_progress_pct')}`",
        f"- gap_models: `{payload.get('gap_models')}`",
        f"- gap_reproducible_mutations: `{payload.get('gap_reproducible_mutations')}`",
        f"- gap_hardness_score: `{payload.get('gap_hardness_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track progress against scale moat targets and quantify remaining gaps")
    parser.add_argument("--scale-batch-summary", required=True)
    parser.add_argument("--scale-batch-history-summary", default=None)
    parser.add_argument("--target-model-pool-size", type=int, default=8000)
    parser.add_argument("--target-reproducible-mutations", type=int, default=36000)
    parser.add_argument("--target-hardness-score", type=float, default=85.0)
    parser.add_argument("--target-horizon-weeks", type=int, default=12)
    parser.add_argument("--out", default="artifacts/dataset_scale_target_gap_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    batch = _load_json(args.scale_batch_summary)
    history = _load_json(args.scale_batch_history_summary)

    reasons: list[str] = []
    if not batch:
        reasons.append("scale_batch_summary_missing")

    current_models = _to_int(batch.get("canonical_total_models", 0))
    current_repro_mut = _to_int(batch.get("reproducible_mutations", 0))
    current_hardness = _to_float(batch.get("hard_moat_hardness_score", 0.0))

    target_models = max(1, int(args.target_model_pool_size))
    target_repro_mut = max(1, int(args.target_reproducible_mutations))
    target_hardness = max(1.0, float(args.target_hardness_score))
    horizon_weeks = max(1, int(args.target_horizon_weeks))

    gap_models = max(0, target_models - current_models)
    gap_repro_mut = max(0, target_repro_mut - current_repro_mut)
    gap_hardness = round(max(0.0, target_hardness - current_hardness), 2)

    model_progress_pct = _progress(float(current_models), float(target_models))
    reproducible_mutation_progress_pct = _progress(float(current_repro_mut), float(target_repro_mut))
    hardness_progress_pct = _progress(float(current_hardness), float(target_hardness))
    overall_progress_pct = round((model_progress_pct * 0.45) + (reproducible_mutation_progress_pct * 0.4) + (hardness_progress_pct * 0.15), 2)

    required_weekly_new_models = int(math.ceil(gap_models / float(horizon_weeks)))
    required_weekly_new_repro_mutations = int(math.ceil(gap_repro_mut / float(horizon_weeks)))
    required_weekly_hardness_gain = round(gap_hardness / float(horizon_weeks), 4)

    latest_delta_models = _to_int(history.get("delta_canonical_total_models", 0))
    latest_delta_repro_mut = _to_int(history.get("delta_reproducible_mutations", 0))
    avg_growth_models = _to_float(history.get("avg_canonical_net_growth_models", 0.0))

    alerts: list[str] = []
    if gap_models > 0 and latest_delta_models < required_weekly_new_models:
        alerts.append("model_pool_growth_below_required_weekly_rate")
    if gap_repro_mut > 0 and latest_delta_repro_mut < required_weekly_new_repro_mutations:
        alerts.append("reproducible_mutation_growth_below_required_weekly_rate")
    if gap_hardness > 0 and current_hardness < 70.0:
        alerts.append("hardness_score_low")
    if avg_growth_models <= 0 and current_models > 0:
        alerts.append("average_model_growth_stalled")
    if str(batch.get("hard_moat_gates_status") or "") == "FAIL":
        alerts.append("hard_moat_gates_fail")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "overall_progress_pct": overall_progress_pct,
        "target_horizon_weeks": horizon_weeks,
        "current_models": current_models,
        "target_models": target_models,
        "gap_models": gap_models,
        "current_reproducible_mutations": current_repro_mut,
        "target_reproducible_mutations": target_repro_mut,
        "gap_reproducible_mutations": gap_repro_mut,
        "current_hardness_score": round(current_hardness, 2),
        "target_hardness_score": round(target_hardness, 2),
        "gap_hardness_score": gap_hardness,
        "model_progress_pct": model_progress_pct,
        "reproducible_mutation_progress_pct": reproducible_mutation_progress_pct,
        "hardness_progress_pct": hardness_progress_pct,
        "required_weekly_new_models": required_weekly_new_models,
        "required_weekly_new_reproducible_mutations": required_weekly_new_repro_mutations,
        "required_weekly_hardness_gain": required_weekly_hardness_gain,
        "history_latest_delta_models": latest_delta_models,
        "history_latest_delta_reproducible_mutations": latest_delta_repro_mut,
        "history_avg_model_growth": avg_growth_models,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "scale_batch_summary": args.scale_batch_summary,
            "scale_batch_history_summary": args.scale_batch_history_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "overall_progress_pct": overall_progress_pct, "gap_models": gap_models, "gap_reproducible_mutations": gap_repro_mut}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
