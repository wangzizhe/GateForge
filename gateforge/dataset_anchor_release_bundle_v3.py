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
        "# GateForge Anchor Release Bundle v3",
        "",
        f"- status: `{payload.get('status')}`",
        f"- release_ready: `{payload.get('release_ready')}`",
        f"- release_score: `{payload.get('release_score')}`",
        f"- release_bundle_id: `{payload.get('release_bundle_id')}`",
        f"- evidence_items: `{payload.get('evidence_items')}`",
        "",
        "## Playbook",
        "",
    ]
    for step in payload.get("reproducible_playbook") if isinstance(payload.get("reproducible_playbook"), list) else []:
        lines.append(f"- `{step}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build release-ready anchor bundle v3 from benchmark and governance evidence")
    parser.add_argument("--anchor-benchmark-pack-v2-summary", required=True)
    parser.add_argument("--open-source-intake-summary", required=True)
    parser.add_argument("--mutation-validator-summary", required=True)
    parser.add_argument("--failure-distribution-benchmark-v2-summary", required=True)
    parser.add_argument("--gateforge-vs-plain-ci-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_anchor_release_bundle_v3/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    anchor_v2 = _load_json(args.anchor_benchmark_pack_v2_summary)
    intake = _load_json(args.open_source_intake_summary)
    validator = _load_json(args.mutation_validator_summary)
    benchmark_v2 = _load_json(args.failure_distribution_benchmark_v2_summary)
    compare = _load_json(args.gateforge_vs_plain_ci_summary)

    reasons: list[str] = []
    if not anchor_v2:
        reasons.append("anchor_benchmark_pack_v2_summary_missing")
    if not intake:
        reasons.append("open_source_intake_summary_missing")
    if not validator:
        reasons.append("mutation_validator_summary_missing")
    if not benchmark_v2:
        reasons.append("failure_distribution_benchmark_v2_summary_missing")
    if not compare:
        reasons.append("gateforge_vs_plain_ci_summary_missing")

    anchor_ready_v2 = bool(anchor_v2.get("anchor_ready", False))
    anchor_score_v2 = _to_float(anchor_v2.get("anchor_pack_score", 0.0))
    accepted_models = _to_int(intake.get("accepted_count", 0))
    validated_count = _to_int(validator.get("validated_count", 0))
    match_ratio = _to_float(validator.get("expected_match_ratio_pct", 0.0))
    drift_score = _to_float(benchmark_v2.get("failure_type_drift", 1.0))
    compare_verdict = str(compare.get("verdict") or "")
    compare_score = _to_int(compare.get("advantage_score", 0))

    score = 0.0
    score += 25.0 if anchor_ready_v2 else min(18.0, anchor_score_v2 * 0.2)
    score += min(15.0, accepted_models * 5.0)
    score += min(20.0, validated_count * 1.5)
    score += min(15.0, match_ratio * 0.15)
    score += max(0.0, 12.0 - drift_score * 20.0)
    score += 13.0 if compare_verdict == "GATEFORGE_ADVANTAGE" else max(0.0, compare_score)

    release_score = round(score, 2)

    if accepted_models < 1:
        reasons.append("no_accepted_open_source_models")
    if validated_count < 3:
        reasons.append("validated_mutation_count_low")
    if match_ratio < 70.0:
        reasons.append("mutation_match_ratio_low")
    if compare_verdict != "GATEFORGE_ADVANTAGE":
        reasons.append("benchmark_advantage_not_established")

    release_ready = release_score >= 72.0 and not reasons

    status = "PASS" if release_ready else "NEEDS_REVIEW"
    if any(r.endswith("_missing") for r in reasons):
        status = "FAIL"

    release_bundle_id = f"anchor_release_v3_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    playbook = [
        "bash scripts/demo_dataset_open_source_model_intake_v1.sh",
        "bash scripts/demo_dataset_modelica_library_registry_v1.sh",
        "bash scripts/demo_dataset_model_family_generator_v1.sh",
        "bash scripts/demo_dataset_mutation_factory_v1.sh",
        "bash scripts/demo_dataset_mutation_execution_validator_v1.sh",
        "bash scripts/demo_dataset_repro_stability_gate_v1.sh",
        "bash scripts/demo_dataset_failure_corpus_ingest_bridge_v1.sh",
        "bash scripts/demo_dataset_failure_baseline_pack_v1.sh",
        "bash scripts/demo_dataset_failure_distribution_benchmark_v2.sh",
        "bash scripts/demo_dataset_gateforge_vs_plain_ci_benchmark_v1.sh",
        "bash scripts/demo_dataset_anchor_benchmark_pack_v2.sh",
    ]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "release_ready": release_ready,
        "release_score": release_score,
        "release_bundle_id": release_bundle_id,
        "evidence_items": 5,
        "key_metrics": {
            "accepted_models": accepted_models,
            "validated_mutation_count": validated_count,
            "mutation_match_ratio_pct": match_ratio,
            "failure_type_drift": drift_score,
            "comparison_verdict": compare_verdict,
            "comparison_advantage_score": compare_score,
        },
        "reproducible_playbook": playbook,
        "reasons": sorted(set(reasons)),
        "sources": {
            "anchor_benchmark_pack_v2_summary": args.anchor_benchmark_pack_v2_summary,
            "open_source_intake_summary": args.open_source_intake_summary,
            "mutation_validator_summary": args.mutation_validator_summary,
            "failure_distribution_benchmark_v2_summary": args.failure_distribution_benchmark_v2_summary,
            "gateforge_vs_plain_ci_summary": args.gateforge_vs_plain_ci_summary,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "release_ready": release_ready, "release_score": release_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
