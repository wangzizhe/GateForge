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


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Weekly Target Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- weekly_target_status: `{payload.get('weekly_target_status')}`",
        f"- accepted_models: `{payload.get('accepted_models')}`",
        f"- reproducible_mutations: `{payload.get('reproducible_mutations')}`",
        f"- large_model_authenticity_score: `{payload.get('large_model_authenticity_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly target gate for moat growth: real models + reproducible mutations + large authenticity")
    parser.add_argument("--intake-runner-summary", required=True)
    parser.add_argument("--mutation-real-runner-summary", required=True)
    parser.add_argument("--large-model-authenticity-summary", required=True)
    parser.add_argument("--min-weekly-accepted-models", type=int, default=4)
    parser.add_argument("--min-weekly-reproducible-mutations", type=int, default=24)
    parser.add_argument("--min-weekly-large-model-authenticity-score", type=float, default=65.0)
    parser.add_argument("--out", default="artifacts/dataset_moat_weekly_target_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    intake = _load_json(args.intake_runner_summary)
    realrun = _load_json(args.mutation_real_runner_summary)
    large_auth = _load_json(args.large_model_authenticity_summary)
    reasons: list[str] = []
    if not intake:
        reasons.append("intake_runner_summary_missing")
    if not realrun:
        reasons.append("mutation_real_runner_summary_missing")
    if not large_auth:
        reasons.append("large_model_authenticity_summary_missing")

    accepted_models = _to_int(intake.get("accepted_count", 0))
    reproducible_mutations = _to_int(realrun.get("executed_count", 0))
    large_model_authenticity_score = _to_float(large_auth.get("large_model_authenticity_score", 0.0))

    target_gaps: list[str] = []
    if accepted_models < int(args.min_weekly_accepted_models):
        target_gaps.append("accepted_models_below_weekly_target")
    if reproducible_mutations < int(args.min_weekly_reproducible_mutations):
        target_gaps.append("reproducible_mutations_below_weekly_target")
    if large_model_authenticity_score < float(args.min_weekly_large_model_authenticity_score):
        target_gaps.append("large_model_authenticity_score_below_weekly_target")
    if str(large_auth.get("status") or "") == "FAIL":
        target_gaps.append("large_model_authenticity_status_fail")

    weekly_target_status = "PASS" if not target_gaps else "NEEDS_REVIEW"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif target_gaps:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "weekly_target_status": weekly_target_status,
        "accepted_models": accepted_models,
        "reproducible_mutations": reproducible_mutations,
        "large_model_authenticity_score": round(large_model_authenticity_score, 4),
        "target_gaps": sorted(set(target_gaps)),
        "reasons": sorted(set(reasons)),
        "thresholds": {
            "min_weekly_accepted_models": int(args.min_weekly_accepted_models),
            "min_weekly_reproducible_mutations": int(args.min_weekly_reproducible_mutations),
            "min_weekly_large_model_authenticity_score": float(args.min_weekly_large_model_authenticity_score),
        },
        "sources": {
            "intake_runner_summary": args.intake_runner_summary,
            "mutation_real_runner_summary": args.mutation_real_runner_summary,
            "large_model_authenticity_summary": args.large_model_authenticity_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "weekly_target_status": weekly_target_status, "target_gap_count": len(target_gaps)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
