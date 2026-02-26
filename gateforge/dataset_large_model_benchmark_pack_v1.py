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


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _complexity_score(model: dict) -> int:
    c = model.get("complexity") if isinstance(model.get("complexity"), dict) else {}
    return _to_int(c.get("complexity_score", 0))


def _ratio(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return round((n / d) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Large Model Benchmark Pack v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- pack_readiness_score: `{payload.get('pack_readiness_score')}`",
        f"- selected_large_models: `{payload.get('selected_large_models')}`",
        f"- selected_large_mutations: `{payload.get('selected_large_mutations')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build executable large-model benchmark pack from library registry and mutation manifest")
    parser.add_argument("--modelica-library-registry", required=True)
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--failure-corpus-saturation-summary", required=True)
    parser.add_argument("--large-coverage-push-v1-summary", default=None)
    parser.add_argument("--max-models", type=int, default=8)
    parser.add_argument("--max-mutations", type=int, default=24)
    parser.add_argument("--pack-out", default="artifacts/dataset_large_model_benchmark_pack_v1/pack.json")
    parser.add_argument("--out", default="artifacts/dataset_large_model_benchmark_pack_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.modelica_library_registry)
    manifest = _load_json(args.mutation_manifest)
    saturation = _load_json(args.failure_corpus_saturation_summary)
    large_push = _load_json(args.large_coverage_push_v1_summary)

    reasons: list[str] = []
    if not registry:
        reasons.append("modelica_library_registry_missing")
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not saturation:
        reasons.append("failure_corpus_saturation_summary_missing")

    models = _extract_models(registry)
    large_models = [
        x
        for x in models
        if str(x.get("asset_type") or "") == "model_source" and str(x.get("suggested_scale") or "") == "large"
    ]
    large_models.sort(key=lambda x: (-_complexity_score(x), str(x.get("model_id") or "")))
    selected_models = large_models[: max(1, int(args.max_models))]
    selected_model_ids = {str(x.get("model_id") or "") for x in selected_models if x.get("model_id")}

    mutations = _extract_mutations(manifest)
    large_mutations = [x for x in mutations if str(x.get("target_scale") or "") == "large"]
    on_selected_models = [x for x in large_mutations if str(x.get("target_model_id") or "") in selected_model_ids]
    chosen_mutations = on_selected_models if on_selected_models else large_mutations

    target_failure_types = saturation.get("target_failure_types") if isinstance(saturation.get("target_failure_types"), list) else []
    target_types = [str(x) for x in target_failure_types if str(x).strip()]

    selected_mutations: list[dict] = []
    covered_types: set[str] = set()
    for t in target_types:
        for row in chosen_mutations:
            ftype = str(row.get("expected_failure_type") or "")
            if ftype == t and str(row.get("mutation_id") or "") not in {str(x.get("mutation_id") or "") for x in selected_mutations}:
                selected_mutations.append(row)
                covered_types.add(ftype)
                break

    for row in chosen_mutations:
        if len(selected_mutations) >= max(1, int(args.max_mutations)):
            break
        mid = str(row.get("mutation_id") or "")
        if mid in {str(x.get("mutation_id") or "") for x in selected_mutations}:
            continue
        selected_mutations.append(row)
        if row.get("expected_failure_type"):
            covered_types.add(str(row.get("expected_failure_type")))

    selected_mutations = selected_mutations[: max(1, int(args.max_mutations))]

    selected_large_models = len(selected_models)
    selected_large_mutations = len(selected_mutations)
    type_coverage_ratio = _ratio(len(covered_types), len(target_types) if target_types else 1)
    large_push_target = _to_int(large_push.get("push_target_large_cases", 0))

    alerts: list[str] = []
    if selected_large_models < 2:
        alerts.append("selected_large_models_low")
    if selected_large_mutations < 4:
        alerts.append("selected_large_mutations_low")
    if type_coverage_ratio < 70.0:
        alerts.append("failure_type_coverage_ratio_low")
    if large_push_target > 0 and selected_large_mutations < large_push_target:
        alerts.append("selected_large_mutations_below_push_target")

    readiness_score = round(
        max(
            0.0,
            min(
                100.0,
                (selected_large_models * 8.0)
                + (selected_large_mutations * 2.5)
                + (type_coverage_ratio * 0.35)
                - (large_push_target * 1.5),
            ),
        ),
        2,
    )
    if readiness_score < 70.0:
        alerts.append("pack_readiness_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    pack_payload = {
        "schema_version": "large_model_benchmark_pack_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "models": selected_models,
        "mutations": selected_mutations,
        "metadata": {
            "target_failure_types": target_types,
            "covered_failure_types": sorted(covered_types),
            "type_coverage_ratio_pct": type_coverage_ratio,
        },
    }
    _write_json(args.pack_out, pack_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "pack_readiness_score": readiness_score,
        "pack_out": args.pack_out,
        "selected_large_models": selected_large_models,
        "selected_large_mutations": selected_large_mutations,
        "target_failure_types_count": len(target_types),
        "covered_failure_types_count": len(covered_types),
        "type_coverage_ratio_pct": type_coverage_ratio,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "modelica_library_registry": args.modelica_library_registry,
            "mutation_manifest": args.mutation_manifest,
            "failure_corpus_saturation_summary": args.failure_corpus_saturation_summary,
            "large_coverage_push_v1_summary": args.large_coverage_push_v1_summary,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": status,
                "selected_large_models": selected_large_models,
                "selected_large_mutations": selected_large_mutations,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
