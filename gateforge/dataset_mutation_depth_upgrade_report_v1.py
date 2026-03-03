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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Depth Upgrade Report v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- upgrade_status: `{payload.get('upgrade_status')}`",
        f"- baseline_mutations_per_failure_type: `{payload.get('baseline_mutations_per_failure_type')}`",
        f"- current_mutations_per_failure_type: `{payload.get('current_mutations_per_failure_type')}`",
        f"- generated_mutation_multiplier: `{payload.get('generated_mutation_multiplier')}`",
        f"- reproducibility_ratio_pct: `{payload.get('reproducibility_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare depth-upgraded sprint output against baseline sprint output")
    parser.add_argument("--current-scale-summary", required=True)
    parser.add_argument("--baseline-scale-summary", default=None)
    parser.add_argument("--target-mutations-per-failure-type", type=int, default=4)
    parser.add_argument("--min-generated-multiplier", type=float, default=1.5)
    parser.add_argument("--min-reproducibility-ratio-pct", type=float, default=98.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_depth_upgrade_report_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current_scale_summary)
    baseline = _load_json(args.baseline_scale_summary)

    reasons: list[str] = []
    if not current:
        reasons.append("current_scale_summary_missing")

    current_generated = _to_int(current.get("generated_mutations", 0))
    current_reproducible = _to_int(current.get("reproducible_mutations", 0))
    current_per_type = _to_int(current.get("mutations_per_failure_type", 0))
    current_accepted = _to_int(current.get("accepted_models", 0))

    baseline_generated = _to_int(baseline.get("generated_mutations", 0))
    baseline_reproducible = _to_int(baseline.get("reproducible_mutations", 0))
    baseline_per_type = _to_int(baseline.get("mutations_per_failure_type", 0))

    if baseline and baseline_per_type == 0:
        baseline_models = max(1, _to_int(baseline.get("selected_mutation_models", 0)))
        baseline_failure_types = max(1, _to_int(baseline.get("failure_types_count", 0)))
        baseline_per_type = max(1, _to_int(round(baseline_generated / baseline_models / baseline_failure_types)))

    reproducibility_ratio_pct = _round(100.0 * current_reproducible / max(1, current_generated))
    generated_mutation_multiplier = _round(current_generated / max(1, baseline_generated))
    reproducible_mutation_multiplier = _round(current_reproducible / max(1, baseline_reproducible))
    depth_multiplier = _round(current_per_type / max(1, baseline_per_type))
    current_mutations_per_model = _round(current_generated / max(1, current_accepted))

    alerts: list[str] = []
    if not baseline:
        alerts.append("baseline_scale_summary_missing")
    if current_per_type < int(args.target_mutations_per_failure_type):
        alerts.append("mutations_per_failure_type_below_target")
    if baseline and generated_mutation_multiplier < float(args.min_generated_multiplier):
        alerts.append("generated_mutation_multiplier_below_target")
    if reproducibility_ratio_pct < float(args.min_reproducibility_ratio_pct):
        alerts.append("reproducibility_ratio_below_target")

    upgrade_status = "UPGRADED"
    if current_per_type < int(args.target_mutations_per_failure_type):
        upgrade_status = "NOT_UPGRADED"
    elif baseline and generated_mutation_multiplier <= 1.0:
        upgrade_status = "NO_EFFECT"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "upgrade_status": upgrade_status,
        "baseline_mutations_per_failure_type": baseline_per_type,
        "current_mutations_per_failure_type": current_per_type,
        "depth_multiplier": depth_multiplier,
        "baseline_generated_mutations": baseline_generated,
        "current_generated_mutations": current_generated,
        "baseline_reproducible_mutations": baseline_reproducible,
        "current_reproducible_mutations": current_reproducible,
        "generated_mutation_multiplier": generated_mutation_multiplier,
        "reproducible_mutation_multiplier": reproducible_mutation_multiplier,
        "reproducibility_ratio_pct": reproducibility_ratio_pct,
        "current_mutations_per_model": current_mutations_per_model,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "current_scale_summary": args.current_scale_summary,
            "baseline_scale_summary": args.baseline_scale_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "upgrade_status": upgrade_status,
                "current_mutations_per_failure_type": current_per_type,
                "generated_mutation_multiplier": generated_mutation_multiplier,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
