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
        "# GateForge Anchor Benchmark Pack v2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- anchor_ready: `{payload.get('anchor_ready')}`",
        f"- anchor_pack_score: `{payload.get('anchor_pack_score')}`",
        f"- baseline_id: `{payload.get('baseline_id')}`",
        f"- reproducible_steps_count: `{len(payload.get('reproducible_steps') or [])}`",
        "",
        "## Reproducible Steps",
        "",
    ]
    for step in payload.get("reproducible_steps") if isinstance(payload.get("reproducible_steps"), list) else []:
        lines.append(f"- `{step}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build externally shareable anchor benchmark pack v2")
    parser.add_argument("--failure-baseline-pack-summary", required=True)
    parser.add_argument("--failure-distribution-quality-gate", required=True)
    parser.add_argument("--mutation-factory-summary", required=True)
    parser.add_argument("--repro-stability-summary", required=True)
    parser.add_argument("--failure-corpus-ingest-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_anchor_benchmark_pack_v2/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    baseline = _load_json(args.failure_baseline_pack_summary)
    gate = _load_json(args.failure_distribution_quality_gate)
    mutation = _load_json(args.mutation_factory_summary)
    stability = _load_json(args.repro_stability_summary)
    ingest = _load_json(args.failure_corpus_ingest_summary)

    reasons: list[str] = []
    if not baseline:
        reasons.append("baseline_summary_missing")
    if not gate:
        reasons.append("distribution_quality_gate_missing")
    if not mutation:
        reasons.append("mutation_factory_summary_missing")
    if not stability:
        reasons.append("repro_stability_summary_missing")
    if not ingest:
        reasons.append("failure_corpus_ingest_summary_missing")

    baseline_status = str(baseline.get("status") or "UNKNOWN")
    gate_result = str(gate.get("gate_result") or gate.get("status") or "UNKNOWN")
    mutation_count = _to_int(mutation.get("total_mutations", 0))
    failure_type_count = _to_int(mutation.get("unique_failure_types", 0))
    stability_ratio = _to_float(stability.get("stability_ratio_pct", 0.0))
    ingested_cases = _to_int(ingest.get("ingested_cases", 0))

    score = 0.0
    score += 20.0 if baseline_status == "PASS" else 10.0
    score += 20.0 if gate_result == "PASS" else 8.0
    score += min(20.0, mutation_count * 0.4)
    score += min(15.0, failure_type_count * 3.0)
    score += min(15.0, stability_ratio * 0.15)
    score += min(10.0, ingested_cases * 2.0)
    anchor_pack_score = round(score, 2)

    anchor_ready = anchor_pack_score >= 70.0 and not reasons

    reproducible_steps = [
        "bash scripts/demo_dataset_modelica_library_registry_v1.sh",
        "bash scripts/demo_dataset_model_family_generator_v1.sh",
        "bash scripts/demo_dataset_mutation_factory_v1.sh",
        "bash scripts/demo_dataset_repro_stability_gate_v1.sh",
        "bash scripts/demo_dataset_failure_corpus_ingest_bridge_v1.sh",
        "bash scripts/demo_dataset_failure_baseline_pack_v1.sh",
        "bash scripts/demo_dataset_failure_distribution_quality_gate_v1.sh",
    ]

    status = "PASS" if anchor_ready else "NEEDS_REVIEW"
    if reasons:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "anchor_ready": anchor_ready,
        "anchor_pack_score": anchor_pack_score,
        "baseline_id": str(baseline.get("baseline_id") or "unknown"),
        "metrics": {
            "mutation_count": mutation_count,
            "unique_failure_types": failure_type_count,
            "stability_ratio_pct": stability_ratio,
            "ingested_cases": ingested_cases,
        },
        "reproducible_steps": reproducible_steps,
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_baseline_pack_summary": args.failure_baseline_pack_summary,
            "failure_distribution_quality_gate": args.failure_distribution_quality_gate,
            "mutation_factory_summary": args.mutation_factory_summary,
            "repro_stability_summary": args.repro_stability_summary,
            "failure_corpus_ingest_summary": args.failure_corpus_ingest_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "anchor_ready": anchor_ready, "anchor_pack_score": anchor_pack_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
