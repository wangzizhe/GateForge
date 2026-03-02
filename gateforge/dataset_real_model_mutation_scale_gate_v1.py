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
        "# GateForge Real Model + Mutation Scale Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- discovered_models: `{payload.get('discovered_models')}`",
        f"- accepted_models: `{payload.get('accepted_models')}`",
        f"- accepted_large_models: `{payload.get('accepted_large_models')}`",
        f"- generated_mutations: `{payload.get('generated_mutations')}`",
        f"- reproducible_mutations: `{payload.get('reproducible_mutations')}`",
        f"- mutation_per_accepted_model: `{payload.get('mutation_per_accepted_model')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate whether real model and mutation scale reached operational target")
    parser.add_argument("--asset-discovery-summary", required=True)
    parser.add_argument("--intake-pipeline-summary", required=True)
    parser.add_argument("--intake-runner-summary", required=True)
    parser.add_argument("--mutation-pack-summary", required=True)
    parser.add_argument("--mutation-real-runner-summary", default=None)
    parser.add_argument("--min-discovered-models", type=int, default=6)
    parser.add_argument("--min-accepted-models", type=int, default=4)
    parser.add_argument("--min-accepted-large-models", type=int, default=1)
    parser.add_argument("--min-generated-mutations", type=int, default=24)
    parser.add_argument("--min-mutation-per-accepted-model", type=float, default=4.0)
    parser.add_argument("--min-reproducible-mutations", type=int, default=0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_scale_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    discovery = _load_json(args.asset_discovery_summary)
    pipeline = _load_json(args.intake_pipeline_summary)
    runner = _load_json(args.intake_runner_summary)
    pack = _load_json(args.mutation_pack_summary)
    real_runner = _load_json(args.mutation_real_runner_summary)

    reasons: list[str] = []
    if not discovery:
        reasons.append("asset_discovery_summary_missing")
    if not pipeline:
        reasons.append("intake_pipeline_summary_missing")
    if not runner:
        reasons.append("intake_runner_summary_missing")
    if not pack:
        reasons.append("mutation_pack_summary_missing")

    discovered_models = _to_int(discovery.get("total_candidates", 0))
    accepted_models = _to_int(runner.get("accepted_count", pipeline.get("accepted_count", 0)))
    accepted_large_models = _to_int(runner.get("accepted_large_count", 0))
    generated_mutations = _to_int(pack.get("total_mutations", 0))
    reproducible_mutations = _to_int(real_runner.get("executed_count", 0)) if real_runner else 0

    mutation_per_model = round(generated_mutations / max(1, accepted_models), 2) if accepted_models > 0 else 0.0

    alerts: list[str] = []
    if discovered_models < int(args.min_discovered_models):
        alerts.append("discovered_models_below_target")
    if accepted_models < int(args.min_accepted_models):
        alerts.append("accepted_models_below_target")
    if accepted_large_models < int(args.min_accepted_large_models):
        alerts.append("accepted_large_models_below_target")
    if generated_mutations < int(args.min_generated_mutations):
        alerts.append("generated_mutations_below_target")
    if mutation_per_model < float(args.min_mutation_per_accepted_model):
        alerts.append("mutation_per_model_below_target")
    if real_runner:
        if reproducible_mutations < int(args.min_reproducible_mutations):
            alerts.append("reproducible_mutations_below_target")
    else:
        alerts.append("mutation_real_runner_summary_missing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "discovered_models": discovered_models,
        "accepted_models": accepted_models,
        "accepted_large_models": accepted_large_models,
        "generated_mutations": generated_mutations,
        "reproducible_mutations": reproducible_mutations,
        "mutation_per_accepted_model": mutation_per_model,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "asset_discovery_summary": args.asset_discovery_summary,
            "intake_pipeline_summary": args.intake_pipeline_summary,
            "intake_runner_summary": args.intake_runner_summary,
            "mutation_pack_summary": args.mutation_pack_summary,
            "mutation_real_runner_summary": args.mutation_real_runner_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "accepted_models": accepted_models, "generated_mutations": generated_mutations}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
