from __future__ import annotations

import argparse
import hashlib
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


def _sha256_file(path: str) -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _freeze_id(parts: list[str]) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"realmodel-freeze-{digest[:12]}"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Mutation Weekly Freeze Manifest v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- freeze_id: `{payload.get('freeze_id')}`",
        f"- week_tag: `{payload.get('week_tag')}`",
        f"- accepted_models: `{payload.get('accepted_models')}`",
        f"- generated_mutations: `{payload.get('generated_mutations')}`",
        f"- reproducible_mutations: `{payload.get('reproducible_mutations')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze weekly real-model + mutation moat artifacts")
    parser.add_argument("--week-tag", required=True)
    parser.add_argument("--scale-batch-summary", required=True)
    parser.add_argument("--canonical-registry-summary", required=True)
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-validation-summary", required=True)
    parser.add_argument("--mutation-validation-matrix-v2-summary", required=True)
    parser.add_argument("--failure-distribution-stability-guard-summary", required=True)
    parser.add_argument("--freeze-manifest-out", default="artifacts/dataset_real_model_mutation_weekly_freeze_manifest_v1/freeze_manifest.json")
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_weekly_freeze_manifest_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    scale = _load_json(args.scale_batch_summary)
    canonical = _load_json(args.canonical_registry_summary)
    manifest = _load_json(args.mutation_manifest)
    validation = _load_json(args.mutation_validation_summary)
    validation_v2 = _load_json(args.mutation_validation_matrix_v2_summary)
    guard = _load_json(args.failure_distribution_stability_guard_summary)

    reasons: list[str] = []
    if not scale:
        reasons.append("scale_batch_summary_missing")
    if not canonical:
        reasons.append("canonical_registry_summary_missing")
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not validation:
        reasons.append("mutation_validation_summary_missing")
    if not validation_v2:
        reasons.append("mutation_validation_matrix_v2_summary_missing")
    if not guard:
        reasons.append("failure_distribution_stability_guard_summary_missing")

    source_paths = [
        args.scale_batch_summary,
        args.canonical_registry_summary,
        args.mutation_manifest,
        args.mutation_validation_summary,
        args.mutation_validation_matrix_v2_summary,
        args.failure_distribution_stability_guard_summary,
    ]
    checksums = {p: _sha256_file(p) for p in source_paths}

    accepted_models = _to_int(scale.get("accepted_models", 0))
    generated_mutations = _to_int(scale.get("generated_mutations", 0))
    reproducible_mutations = _to_int(scale.get("reproducible_mutations", 0))
    canonical_net_growth = _to_int(canonical.get("canonical_net_growth_models", 0))
    validation_type_match = _to_float((validation_v2.get("overall") or {}).get("type_match_rate_pct", 0.0))
    guard_status = str(guard.get("status") or "UNKNOWN")

    gate_checks = {
        "scale_bundle_status": "PASS" if str(scale.get("bundle_status") or "") == "PASS" else "FAIL",
        "canonical_registry_status": "PASS" if str(canonical.get("status") or "") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
        "validation_status": "PASS" if str(validation.get("status") or "") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
        "validation_v2_status": "PASS" if str(validation_v2.get("status") or "") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
        "distribution_guard_status": "PASS" if guard_status in {"PASS", "NEEDS_REVIEW"} else "FAIL",
        "accepted_models_positive": "PASS" if accepted_models > 0 else "FAIL",
        "generated_mutations_positive": "PASS" if generated_mutations > 0 else "FAIL",
    }

    alerts: list[str] = []
    if canonical_net_growth <= 0:
        alerts.append("canonical_net_growth_not_positive")
    if reproducible_mutations < max(1, int(generated_mutations * 0.6)):
        alerts.append("reproducible_mutation_count_low")
    if validation_type_match < 30.0:
        alerts.append("validation_type_match_low")
    if guard_status == "NEEDS_REVIEW":
        alerts.append("distribution_guard_needs_review")

    freeze_id = _freeze_id(
        [
            args.week_tag,
            str(accepted_models),
            str(generated_mutations),
            str(reproducible_mutations),
            str(canonical_net_growth),
            str(validation_type_match),
            *(checksums.get(p, "") for p in source_paths),
        ]
    )

    freeze_manifest = {
        "schema_version": "real_model_mutation_weekly_freeze_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_id": freeze_id,
        "week_tag": args.week_tag,
        "snapshot": {
            "accepted_models": accepted_models,
            "generated_mutations": generated_mutations,
            "reproducible_mutations": reproducible_mutations,
            "canonical_net_growth_models": canonical_net_growth,
            "validation_type_match_rate_pct": validation_type_match,
            "distribution_guard_status": guard_status,
        },
        "gate_checks": gate_checks,
        "sources": source_paths,
        "checksums_sha256": checksums,
    }
    _write_json(args.freeze_manifest_out, freeze_manifest)

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif any(v == "FAIL" for v in gate_checks.values()) or alerts:
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "freeze_id": freeze_id,
        "week_tag": args.week_tag,
        "accepted_models": accepted_models,
        "generated_mutations": generated_mutations,
        "reproducible_mutations": reproducible_mutations,
        "canonical_net_growth_models": canonical_net_growth,
        "validation_type_match_rate_pct": round(validation_type_match, 2),
        "distribution_guard_status": guard_status,
        "gate_checks": gate_checks,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "freeze_manifest_path": args.freeze_manifest_out,
        "sources": {
            "scale_batch_summary": args.scale_batch_summary,
            "canonical_registry_summary": args.canonical_registry_summary,
            "mutation_manifest": args.mutation_manifest,
            "mutation_validation_summary": args.mutation_validation_summary,
            "mutation_validation_matrix_v2_summary": args.mutation_validation_matrix_v2_summary,
            "failure_distribution_stability_guard_summary": args.failure_distribution_stability_guard_summary,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "freeze_id": freeze_id}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
