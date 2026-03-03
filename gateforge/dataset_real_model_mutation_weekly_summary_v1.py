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


def _round(v: float) -> float:
    return round(v, 2)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    kpis = payload.get("kpis") if isinstance(payload.get("kpis"), dict) else {}
    lines = [
        "# GateForge Real Model Mutation Weekly Summary v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- week_tag: `{payload.get('week_tag')}`",
        f"- accepted_models: `{kpis.get('real_model_count')}`",
        f"- accepted_large_models: `{kpis.get('large_model_count')}`",
        f"- reproducible_mutations: `{kpis.get('reproducible_mutation_count')}`",
        f"- mutation_depth_per_failure_type: `{kpis.get('mutations_per_failure_type')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly summary from real-model + mutation scale outputs")
    parser.add_argument("--week-tag", required=True)
    parser.add_argument("--open-source-bootstrap-summary", required=True)
    parser.add_argument("--scale-batch-summary", required=True)
    parser.add_argument("--scale-gate-summary", required=True)
    parser.add_argument("--depth-upgrade-report-summary", default=None)
    parser.add_argument("--uniqueness-guard-summary", default=None)
    parser.add_argument("--min-accepted-models", type=int, default=300)
    parser.add_argument("--min-unique-accepted-models", type=int, default=260)
    parser.add_argument("--min-large-models", type=int, default=80)
    parser.add_argument("--min-reproducibility-ratio-pct", type=float, default=98.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_weekly_summary_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    bootstrap = _load_json(args.open_source_bootstrap_summary)
    scale_batch = _load_json(args.scale_batch_summary)
    scale_gate = _load_json(args.scale_gate_summary)
    depth = _load_json(args.depth_upgrade_report_summary)
    uniqueness = _load_json(args.uniqueness_guard_summary)

    reasons: list[str] = []
    if not bootstrap:
        reasons.append("open_source_bootstrap_summary_missing")
    if not scale_batch:
        reasons.append("scale_batch_summary_missing")
    if not scale_gate:
        reasons.append("scale_gate_summary_missing")

    accepted_models = _to_int(scale_batch.get("accepted_models", 0))
    large_models = _to_int(scale_batch.get("accepted_large_models", 0))
    generated_mutations = _to_int(scale_batch.get("generated_mutations", 0))
    reproducible_mutations = _to_int(scale_batch.get("reproducible_mutations", 0))
    mutations_per_failure_type = _to_int(scale_batch.get("mutations_per_failure_type", 0))
    failure_types_count = _to_int(scale_batch.get("failure_types_count", 0))
    selected_mutation_models = _to_int(scale_batch.get("selected_mutation_models", 0))
    harvest_total_candidates = _to_int(bootstrap.get("harvest_total_candidates", 0))
    source_library_count = _to_int(depth.get("source_library_count", 0))
    unique_real_model_count = _to_int(uniqueness.get("effective_unique_accepted_models", accepted_models))
    duplicate_ratio_pct = _to_float(uniqueness.get("duplicate_ratio_pct", 0.0))
    uniqueness_status = str(uniqueness.get("status") or "UNKNOWN")

    reproducibility_ratio_pct = _round(100.0 * reproducible_mutations / max(1, generated_mutations))
    mutations_per_model = _round(generated_mutations / max(1, accepted_models))
    scale_gate_status = str(scale_gate.get("status") or scale_batch.get("scale_gate_status") or "UNKNOWN")
    bundle_status = str(scale_batch.get("bundle_status") or "UNKNOWN")

    failure_distribution_stability_score = _round(_clamp(reproducibility_ratio_pct))
    gateforge_vs_plain_ci_advantage_score = _round(
        _clamp(
            accepted_models / 12.0
            + large_models / 8.0
            + mutations_per_model * 2.0
            + reproducibility_ratio_pct * 0.25
        )
    )

    focus_next_week: list[str] = []
    if accepted_models < int(args.min_accepted_models):
        focus_next_week.append("increase_accepted_real_models")
    if unique_real_model_count < int(args.min_unique_accepted_models):
        focus_next_week.append("increase_unique_accepted_real_models")
    if large_models < int(args.min_large_models):
        focus_next_week.append("increase_large_real_models")
    if reproducibility_ratio_pct < float(args.min_reproducibility_ratio_pct):
        focus_next_week.append("stabilize_mutation_reproducibility")
    if mutations_per_failure_type < 4:
        focus_next_week.append("upgrade_mutation_depth_to_4")
    if scale_gate_status != "PASS":
        focus_next_week.append("recover_scale_gate_to_pass")

    alerts: list[str] = []
    if scale_gate_status != "PASS":
        alerts.append("scale_gate_not_pass")
    if bundle_status != "PASS":
        alerts.append("scale_batch_bundle_not_pass")
    if uniqueness and uniqueness_status != "PASS":
        alerts.append("uniqueness_guard_not_pass")
    if uniqueness and duplicate_ratio_pct > 8.0:
        alerts.append("duplicate_ratio_above_8pct")
    if reproducibility_ratio_pct < float(args.min_reproducibility_ratio_pct):
        alerts.append("reproducibility_ratio_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts or focus_next_week:
        status = "NEEDS_REVIEW"

    kpis = {
        "real_model_count": accepted_models,
        "unique_real_model_count": unique_real_model_count,
        "duplicate_ratio_pct": _round(duplicate_ratio_pct),
        "uniqueness_status": uniqueness_status,
        "large_model_count": large_models,
        "harvest_total_candidates": harvest_total_candidates,
        "reproducible_mutation_count": reproducible_mutations,
        "generated_mutation_count": generated_mutations,
        "mutation_reproducibility_ratio_pct": reproducibility_ratio_pct,
        "mutations_per_model": mutations_per_model,
        "mutations_per_failure_type": mutations_per_failure_type,
        "failure_types_count": failure_types_count,
        "selected_mutation_models": selected_mutation_models,
        "failure_distribution_stability_score": failure_distribution_stability_score,
        "gateforge_vs_plain_ci_advantage_score": gateforge_vs_plain_ci_advantage_score,
        "source_library_count": source_library_count,
    }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "week_tag": args.week_tag,
        "kpis": kpis,
        "scale_gate_status": scale_gate_status,
        "bundle_status": bundle_status,
        "focus_next_week": focus_next_week,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "open_source_bootstrap_summary": args.open_source_bootstrap_summary,
            "scale_batch_summary": args.scale_batch_summary,
            "scale_gate_summary": args.scale_gate_summary,
            "depth_upgrade_report_summary": args.depth_upgrade_report_summary,
            "uniqueness_guard_summary": args.uniqueness_guard_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "week_tag": args.week_tag,
                "real_model_count": accepted_models,
                "reproducible_mutation_count": reproducible_mutations,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
