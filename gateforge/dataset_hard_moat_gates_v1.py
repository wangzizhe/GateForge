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


def _gate(observed: float, threshold: float, *, mode: str = "min") -> str:
    if mode == "max":
        return "PASS" if observed <= threshold else "FAIL"
    return "PASS" if observed >= threshold else "FAIL"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Hard Moat Gates v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- moat_hardness_score: `{payload.get('moat_hardness_score')}`",
        f"- failed_gate_count: `{payload.get('failed_gate_count')}`",
        f"- critical_failed_gate_count: `{payload.get('critical_failed_gate_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate hard moat gates for real-model + mutation scale batch outputs")
    parser.add_argument("--asset-discovery-summary", required=True)
    parser.add_argument("--intake-runner-summary", required=True)
    parser.add_argument("--canonical-registry-summary", required=True)
    parser.add_argument("--mutation-pack-summary", required=True)
    parser.add_argument("--mutation-real-runner-summary", required=True)
    parser.add_argument("--mutation-validation-matrix-v2-summary", required=True)
    parser.add_argument("--failure-distribution-stability-guard-summary", required=True)
    parser.add_argument("--mutation-effective-scale-summary", default=None)
    parser.add_argument("--mutation-effective-depth-summary", default=None)
    parser.add_argument("--mutation-source-provenance-summary", default=None)
    parser.add_argument("--min-discovered-models", type=int, default=2)
    parser.add_argument("--min-accepted-models", type=int, default=2)
    parser.add_argument("--min-accepted-large-models", type=int, default=1)
    parser.add_argument("--min-accepted-large-ratio-pct", type=float, default=25.0)
    parser.add_argument("--min-generated-mutations", type=int, default=20)
    parser.add_argument("--min-reproducible-mutations", type=int, default=10)
    parser.add_argument("--min-canonical-net-growth-models", type=int, default=0)
    parser.add_argument("--min-validation-type-match-rate-pct", type=float, default=30.0)
    parser.add_argument("--min-failure-type-entropy", type=float, default=1.0)
    parser.add_argument("--max-distribution-drift-tvd", type=float, default=0.4)
    parser.add_argument("--min-effective-reproducible-mutations", type=int, default=0)
    parser.add_argument("--min-effective-depth-p10", type=float, default=0.0)
    parser.add_argument("--min-source-existing-source-path-ratio-pct", type=float, default=80.0)
    parser.add_argument("--min-source-allowed-root-ratio-pct", type=float, default=80.0)
    parser.add_argument("--min-source-registry-match-ratio-pct", type=float, default=50.0)
    parser.add_argument("--out", default="artifacts/dataset_hard_moat_gates_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    discovery = _load_json(args.asset_discovery_summary)
    runner = _load_json(args.intake_runner_summary)
    canonical = _load_json(args.canonical_registry_summary)
    pack = _load_json(args.mutation_pack_summary)
    realrun = _load_json(args.mutation_real_runner_summary)
    validation_v2 = _load_json(args.mutation_validation_matrix_v2_summary)
    guard = _load_json(args.failure_distribution_stability_guard_summary)
    effective_scale = _load_json(args.mutation_effective_scale_summary)
    effective_depth = _load_json(args.mutation_effective_depth_summary)
    source_provenance = _load_json(args.mutation_source_provenance_summary)

    reasons: list[str] = []
    if not discovery:
        reasons.append("asset_discovery_summary_missing")
    if not runner:
        reasons.append("intake_runner_summary_missing")
    if not canonical:
        reasons.append("canonical_registry_summary_missing")
    if not pack:
        reasons.append("mutation_pack_summary_missing")
    if not realrun:
        reasons.append("mutation_real_runner_summary_missing")
    if not validation_v2:
        reasons.append("mutation_validation_matrix_v2_summary_missing")
    if not guard:
        reasons.append("failure_distribution_stability_guard_summary_missing")

    discovered_models = _to_int(discovery.get("total_candidates", 0))
    accepted_models = _to_int(runner.get("accepted_count", 0))
    accepted_large_models = _to_int(runner.get("accepted_large_count", 0))
    accepted_large_ratio_pct = round((accepted_large_models / max(1, accepted_models)) * 100.0, 2)
    generated_mutations = _to_int(pack.get("total_mutations", 0))
    reproducible_mutations = _to_int(realrun.get("executed_count", 0))
    canonical_net_growth_models = _to_int(canonical.get("canonical_net_growth_models", 0))
    validation_type_match_rate_pct = _to_float((validation_v2.get("overall") or {}).get("type_match_rate_pct", 0.0))
    failure_type_entropy = _to_float(guard.get("failure_type_entropy", 0.0))
    distribution_drift_tvd = _to_float(guard.get("distribution_drift_tvd", 0.0))
    effective_reproducible_mutations = _to_int(effective_scale.get("effective_reproducible_mutations", 0))
    effective_depth_p10 = _to_float(effective_depth.get("p10_effective_mutations_per_model", 0.0))
    source_existing_ratio = _to_float(source_provenance.get("existing_source_path_ratio_pct", 0.0))
    source_allowed_ratio = _to_float(source_provenance.get("allowed_root_ratio_pct", 0.0))
    source_registry_ratio = _to_float(source_provenance.get("registry_match_ratio_pct", 0.0))

    gates = {
        "discovered_models": {
            "critical": True,
            "threshold": int(args.min_discovered_models),
            "mode": "min",
            "observed": discovered_models,
            "status": _gate(float(discovered_models), float(args.min_discovered_models), mode="min"),
        },
        "accepted_models": {
            "critical": True,
            "threshold": int(args.min_accepted_models),
            "mode": "min",
            "observed": accepted_models,
            "status": _gate(float(accepted_models), float(args.min_accepted_models), mode="min"),
        },
        "accepted_large_models": {
            "critical": True,
            "threshold": int(args.min_accepted_large_models),
            "mode": "min",
            "observed": accepted_large_models,
            "status": _gate(float(accepted_large_models), float(args.min_accepted_large_models), mode="min"),
        },
        "accepted_large_ratio_pct": {
            "critical": False,
            "threshold": float(args.min_accepted_large_ratio_pct),
            "mode": "min",
            "observed": accepted_large_ratio_pct,
            "status": _gate(accepted_large_ratio_pct, float(args.min_accepted_large_ratio_pct), mode="min"),
        },
        "generated_mutations": {
            "critical": True,
            "threshold": int(args.min_generated_mutations),
            "mode": "min",
            "observed": generated_mutations,
            "status": _gate(float(generated_mutations), float(args.min_generated_mutations), mode="min"),
        },
        "reproducible_mutations": {
            "critical": True,
            "threshold": int(args.min_reproducible_mutations),
            "mode": "min",
            "observed": reproducible_mutations,
            "status": _gate(float(reproducible_mutations), float(args.min_reproducible_mutations), mode="min"),
        },
        "canonical_net_growth_models": {
            "critical": False,
            "threshold": int(args.min_canonical_net_growth_models),
            "mode": "min",
            "observed": canonical_net_growth_models,
            "status": _gate(float(canonical_net_growth_models), float(args.min_canonical_net_growth_models), mode="min"),
        },
        "validation_type_match_rate_pct": {
            "critical": False,
            "threshold": float(args.min_validation_type_match_rate_pct),
            "mode": "min",
            "observed": round(validation_type_match_rate_pct, 2),
            "status": _gate(validation_type_match_rate_pct, float(args.min_validation_type_match_rate_pct), mode="min"),
        },
        "failure_type_entropy": {
            "critical": False,
            "threshold": float(args.min_failure_type_entropy),
            "mode": "min",
            "observed": round(failure_type_entropy, 4),
            "status": _gate(failure_type_entropy, float(args.min_failure_type_entropy), mode="min"),
        },
        "distribution_drift_tvd": {
            "critical": False,
            "threshold": float(args.max_distribution_drift_tvd),
            "mode": "max",
            "observed": round(distribution_drift_tvd, 6),
            "status": _gate(distribution_drift_tvd, float(args.max_distribution_drift_tvd), mode="max"),
        },
    }

    if effective_scale:
        gates["effective_reproducible_mutations"] = {
            "critical": False,
            "threshold": int(args.min_effective_reproducible_mutations),
            "mode": "min",
            "observed": effective_reproducible_mutations,
            "status": _gate(float(effective_reproducible_mutations), float(args.min_effective_reproducible_mutations), mode="min"),
        }
    if effective_depth:
        gates["effective_depth_p10"] = {
            "critical": False,
            "threshold": float(args.min_effective_depth_p10),
            "mode": "min",
            "observed": round(effective_depth_p10, 4),
            "status": _gate(effective_depth_p10, float(args.min_effective_depth_p10), mode="min"),
        }
    if source_provenance:
        gates["source_existing_source_path_ratio_pct"] = {
            "critical": False,
            "threshold": float(args.min_source_existing_source_path_ratio_pct),
            "mode": "min",
            "observed": round(source_existing_ratio, 4),
            "status": _gate(source_existing_ratio, float(args.min_source_existing_source_path_ratio_pct), mode="min"),
        }
        gates["source_allowed_root_ratio_pct"] = {
            "critical": False,
            "threshold": float(args.min_source_allowed_root_ratio_pct),
            "mode": "min",
            "observed": round(source_allowed_ratio, 4),
            "status": _gate(source_allowed_ratio, float(args.min_source_allowed_root_ratio_pct), mode="min"),
        }
        gates["source_registry_match_ratio_pct"] = {
            "critical": False,
            "threshold": float(args.min_source_registry_match_ratio_pct),
            "mode": "min",
            "observed": round(source_registry_ratio, 4),
            "status": _gate(source_registry_ratio, float(args.min_source_registry_match_ratio_pct), mode="min"),
        }

    failed_gates = [name for name, gate in gates.items() if str(gate.get("status") or "") == "FAIL"]
    critical_failed_gates = [name for name, gate in gates.items() if bool(gate.get("critical")) and str(gate.get("status") or "") == "FAIL"]

    alerts: list[str] = []
    if str(guard.get("status") or "") == "NEEDS_REVIEW":
        alerts.append("distribution_guard_needs_review")
    if str(validation_v2.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("validation_matrix_v2_not_pass")
    if str(canonical.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("canonical_registry_not_pass")
    if effective_scale and str(effective_scale.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("effective_scale_not_pass")
    if effective_depth and str(effective_depth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("effective_depth_not_pass")
    if source_provenance and str(source_provenance.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("source_provenance_not_pass")
    if failed_gates:
        alerts.append("hard_moat_gate_failures_present")

    passed_count = len([1 for g in gates.values() if str(g.get("status") or "") == "PASS"])
    moat_hardness_score = round((passed_count / max(1, len(gates))) * 100.0, 2)

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif critical_failed_gates:
        status = "FAIL"
    elif failed_gates or alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "moat_hardness_score": moat_hardness_score,
        "failed_gate_count": len(failed_gates),
        "critical_failed_gate_count": len(critical_failed_gates),
        "failed_gates": failed_gates,
        "critical_failed_gates": critical_failed_gates,
        "gates": gates,
        "signals": {
            "discovered_models": discovered_models,
            "accepted_models": accepted_models,
            "accepted_large_models": accepted_large_models,
            "accepted_large_ratio_pct": accepted_large_ratio_pct,
            "generated_mutations": generated_mutations,
            "reproducible_mutations": reproducible_mutations,
            "canonical_net_growth_models": canonical_net_growth_models,
            "validation_type_match_rate_pct": round(validation_type_match_rate_pct, 2),
            "failure_type_entropy": round(failure_type_entropy, 4),
            "distribution_drift_tvd": round(distribution_drift_tvd, 6),
            "effective_reproducible_mutations": effective_reproducible_mutations if effective_scale else None,
            "effective_depth_p10": round(effective_depth_p10, 4) if effective_depth else None,
            "source_existing_source_path_ratio_pct": round(source_existing_ratio, 4) if source_provenance else None,
            "source_allowed_root_ratio_pct": round(source_allowed_ratio, 4) if source_provenance else None,
            "source_registry_match_ratio_pct": round(source_registry_ratio, 4) if source_provenance else None,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "asset_discovery_summary": args.asset_discovery_summary,
            "intake_runner_summary": args.intake_runner_summary,
            "canonical_registry_summary": args.canonical_registry_summary,
            "mutation_pack_summary": args.mutation_pack_summary,
            "mutation_real_runner_summary": args.mutation_real_runner_summary,
            "mutation_validation_matrix_v2_summary": args.mutation_validation_matrix_v2_summary,
            "failure_distribution_stability_guard_summary": args.failure_distribution_stability_guard_summary,
            "mutation_effective_scale_summary": args.mutation_effective_scale_summary,
            "mutation_effective_depth_summary": args.mutation_effective_depth_summary,
            "mutation_source_provenance_summary": args.mutation_source_provenance_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "moat_hardness_score": moat_hardness_score, "failed_gate_count": len(failed_gates)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
