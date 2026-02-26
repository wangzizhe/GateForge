from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


OPERATORS = [
    {"name": "script_parse_error", "expected_failure_type": "script_parse_error"},
    {"name": "model_check_error", "expected_failure_type": "model_check_error"},
    {"name": "simulate_error", "expected_failure_type": "simulate_error"},
    {"name": "semantic_regression", "expected_failure_type": "semantic_regression"},
]


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


def _extract_models(registry: dict) -> dict[str, dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("model_id") or "")
        if model_id:
            out[model_id] = row
    return out


def _extract_families(manifest: dict) -> list[dict]:
    rows = manifest.get("families") if isinstance(manifest.get("families"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _model_priority(scale: str) -> int:
    if scale == "large":
        return 0
    if scale == "medium":
        return 1
    return 2


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Factory v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- unique_failure_types: `{payload.get('unique_failure_types')}`",
        f"- target_large_mutations: `{payload.get('target_large_mutations')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic mutation manifest from model families")
    parser.add_argument("--model-family-manifest", required=True)
    parser.add_argument("--modelica-library-registry", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mutations-per-model", type=int, default=2)
    parser.add_argument("--manifest-out", default="artifacts/dataset_mutation_factory_v1/manifest.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_factory_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    family_manifest = _load_json(args.model_family_manifest)
    registry = _load_json(args.modelica_library_registry)

    reasons: list[str] = []
    if not family_manifest:
        reasons.append("model_family_manifest_missing")
    if not registry:
        reasons.append("modelica_library_registry_missing")

    families = _extract_families(family_manifest)
    model_index = _extract_models(registry)

    if not families:
        reasons.append("family_rows_missing")

    model_candidates: list[tuple[str, str]] = []
    for fam in families:
        scale_map = fam.get("scale_map") if isinstance(fam.get("scale_map"), dict) else {}
        for scale in ["large", "medium", "small"]:
            model_id = str(scale_map.get(scale) or "")
            if model_id:
                model_candidates.append((model_id, scale))

        if not scale_map:
            for model_id in fam.get("member_model_ids") if isinstance(fam.get("member_model_ids"), list) else []:
                row = model_index.get(str(model_id) or "")
                scale = str((row or {}).get("suggested_scale") or "small")
                if model_id:
                    model_candidates.append((str(model_id), scale))

    dedup: dict[str, str] = {}
    for model_id, scale in model_candidates:
        if model_id not in dedup:
            dedup[model_id] = scale

    sorted_models = sorted(dedup.items(), key=lambda x: (_model_priority(x[1]), x[0]))

    mutations: list[dict] = []
    seed_base = int(args.seed)
    per_model = max(1, int(args.mutations_per_model))

    for model_idx, (model_id, scale) in enumerate(sorted_models, start=1):
        target_row = model_index.get(model_id, {})
        source_path = str(target_row.get("source_path") or "")
        selected_ops = OPERATORS[: min(len(OPERATORS), per_model)]
        for op_idx, op in enumerate(selected_ops, start=1):
            seed = seed_base + model_idx * 100 + op_idx
            mutation_id = f"mutv1_{model_id}_{op['name']}_{seed}"
            mutations.append(
                {
                    "mutation_id": mutation_id,
                    "target_model_id": model_id,
                    "target_scale": scale,
                    "operator": op["name"],
                    "expected_failure_type": op["expected_failure_type"],
                    "seed": seed,
                    "patch_hint": f"apply_{op['name']}_operator(seed={seed})",
                    "repro_command": f"python -m gateforge.run --proposal <proposal> --model-script {source_path}",
                }
            )

    failure_types = sorted({str(x.get("expected_failure_type") or "") for x in mutations if x.get("expected_failure_type")})
    type_count = len(failure_types)
    target_large = len([x for x in mutations if str(x.get("target_scale") or "") == "large"])

    if not mutations:
        reasons.append("no_mutations_generated")
    if type_count < 4:
        reasons.append("mutation_failure_type_coverage_low")
    if target_large == 0:
        reasons.append("large_scale_mutations_missing")

    status = "PASS"
    if "model_family_manifest_missing" in reasons or "modelica_library_registry_missing" in reasons:
        status = "FAIL"
    elif reasons:
        status = "NEEDS_REVIEW"

    manifest = {
        "schema_version": "mutation_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mutations": mutations,
    }
    _write_json(args.manifest_out, manifest)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "manifest_path": args.manifest_out,
        "total_mutations": len(mutations),
        "unique_failure_types": type_count,
        "failure_types": failure_types,
        "target_large_mutations": target_large,
        "reasons": sorted(set(reasons)),
        "sources": {
            "model_family_manifest": args.model_family_manifest,
            "modelica_library_registry": args.modelica_library_registry,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_mutations": len(mutations), "unique_failure_types": type_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
