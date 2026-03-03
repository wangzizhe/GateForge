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
        "# GateForge Mutation Selection Balance Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- selected_models: `{payload.get('selected_models')}`",
        f"- selected_large_ratio_pct: `{payload.get('selected_large_ratio_pct')}`",
        f"- selected_families: `{payload.get('selected_families')}`",
        f"- selected_source_buckets: `{payload.get('selected_source_buckets')}`",
        f"- max_family_share_pct: `{payload.get('max_family_share_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quality guard for mutation model selection diversity and scale readiness")
    parser.add_argument("--selection-plan-summary", required=True)
    parser.add_argument("--mutation-pack-summary", default=None)
    parser.add_argument("--min-selected-models", type=int, default=4)
    parser.add_argument("--min-large-ratio-pct", type=float, default=25.0)
    parser.add_argument("--min-covered-families", type=int, default=3)
    parser.add_argument("--min-source-buckets", type=int, default=2)
    parser.add_argument("--max-family-share-pct", type=float, default=65.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_selection_balance_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    plan = _load_json(args.selection_plan_summary)
    pack = _load_json(args.mutation_pack_summary)
    reasons: list[str] = []
    if not plan:
        reasons.append("selection_plan_summary_missing")

    selected_models = _to_int(plan.get("selected_models", 0))
    selected_large_ratio_pct = _to_float(plan.get("selected_large_ratio_pct", 0.0))
    selected_families = _to_int(plan.get("selected_families", 0))
    selected_source_buckets = _to_int(plan.get("selected_source_buckets", 0))
    max_family_share_pct = _to_float(plan.get("max_family_share_pct", 0.0))
    plan_status = str(plan.get("status") or "UNKNOWN")

    alerts: list[str] = []
    if plan_status == "FAIL":
        alerts.append("selection_plan_status_fail")
    if selected_models < int(args.min_selected_models):
        alerts.append("selected_models_below_threshold")
    if selected_large_ratio_pct < float(args.min_large_ratio_pct):
        alerts.append("selected_large_ratio_below_threshold")
    if selected_families < int(args.min_covered_families):
        alerts.append("selected_family_coverage_below_threshold")
    if selected_source_buckets < int(args.min_source_buckets):
        alerts.append("selected_source_bucket_coverage_below_threshold")
    if max_family_share_pct > float(args.max_family_share_pct):
        alerts.append("selected_family_concentration_high")

    if pack:
        total_mutations = _to_int(pack.get("total_mutations", 0))
        selected_in_pack = _to_int(pack.get("selected_models", 0))
        if total_mutations <= 0:
            alerts.append("mutation_pack_empty")
        if selected_models > 0 and selected_in_pack > 0 and selected_models != selected_in_pack:
            alerts.append("selection_plan_vs_pack_selected_model_mismatch")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "selected_models": selected_models,
        "selected_large_ratio_pct": selected_large_ratio_pct,
        "selected_families": selected_families,
        "selected_source_buckets": selected_source_buckets,
        "max_family_share_pct": max_family_share_pct,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "selection_plan_summary": args.selection_plan_summary,
            "mutation_pack_summary": args.mutation_pack_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "selected_models": selected_models,
                "selected_large_ratio_pct": selected_large_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
