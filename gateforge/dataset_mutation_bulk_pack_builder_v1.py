from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_FAILURE_TYPES = [
    "simulate_error",
    "model_check_error",
    "semantic_regression",
    "numerical_instability",
    "constraint_violation",
]

OPERATOR_MAP = {
    "simulate_error": "break_solver_stability",
    "model_check_error": "violate_connector_contract",
    "semantic_regression": "invert_control_signal",
    "numerical_instability": "increase_stiffness",
    "constraint_violation": "break_physical_limit",
}

STAGE_MAP = {
    "simulate_error": "simulate",
    "model_check_error": "check",
    "semantic_regression": "postprocess",
    "numerical_instability": "simulate",
    "constraint_violation": "check",
}


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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source"]


def _format_command(template: str, row: dict) -> str:
    try:
        return str(template).format(**row)
    except Exception:
        return f"python -c \"print('mutation {row.get('mutation_id')}')\""


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Bulk Pack Builder v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- selected_models: `{payload.get('selected_models')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- large_scale_mutations: `{payload.get('large_scale_mutations')}`",
        f"- failure_types_count: `{payload.get('failure_types_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build large/medium reproducible mutation pack at scale from model registry")
    parser.add_argument("--model-registry", required=True)
    parser.add_argument("--target-scales", default="medium,large")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--mutations-per-failure-type", type=int, default=2)
    parser.add_argument("--max-models", type=int, default=0)
    parser.add_argument("--seed-base", type=int, default=1000)
    parser.add_argument(
        "--repro-command-template",
        default="python -c \"print('mutation {mutation_id} model={model_id} failure={failure_type}')\"",
    )
    parser.add_argument("--manifest-out", default="artifacts/dataset_mutation_bulk_pack_builder_v1/manifest.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_bulk_pack_builder_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.model_registry)

    reasons: list[str] = []
    if not registry:
        reasons.append("model_registry_missing")

    scales = {_slug(x, default="") for x in str(args.target_scales).split(",") if _slug(x, default="")}
    failure_types = [_slug(x, default="") for x in str(args.failure_types).split(",") if _slug(x, default="")]
    per_type = max(1, int(args.mutations_per_failure_type))

    models = _extract_models(registry)
    selected_models = [m for m in models if _slug(m.get("suggested_scale"), default="small") in scales]
    selected_models.sort(key=lambda x: (0 if _slug(x.get("suggested_scale"), default="small") == "large" else 1, str(x.get("model_id") or "")))
    if int(args.max_models) > 0:
        selected_models = selected_models[: int(args.max_models)]

    mutations: list[dict] = []
    for midx, model in enumerate(selected_models, start=1):
        model_id = str(model.get("model_id") or "")
        model_path = str(model.get("source_path") or "")
        scale = _slug(model.get("suggested_scale"), default="small")
        for fidx, failure_type in enumerate(failure_types, start=1):
            for r in range(per_type):
                seed = int(args.seed_base) + midx * 1000 + fidx * 100 + r
                mutation_id = f"bulk_{model_id}_{failure_type}_{seed}"
                row = {
                    "mutation_id": mutation_id,
                    "target_model_id": model_id,
                    "target_scale": scale,
                    "expected_failure_type": failure_type,
                    "expected_stage": STAGE_MAP.get(failure_type, "simulate"),
                    "operator": OPERATOR_MAP.get(failure_type, "generic_parameter_shift"),
                    "seed": seed,
                    "model_path": model_path,
                    "model_id": model_id,
                    "failure_type": failure_type,
                }
                row["repro_command"] = _format_command(str(args.repro_command_template), row)
                mutations.append(row)

    scale_counts = {
        "small": len([x for x in mutations if str(x.get("target_scale") or "") == "small"]),
        "medium": len([x for x in mutations if str(x.get("target_scale") or "") == "medium"]),
        "large": len([x for x in mutations if str(x.get("target_scale") or "") == "large"]),
    }

    alerts: list[str] = []
    if not selected_models:
        alerts.append("selected_models_empty")
    if not mutations:
        alerts.append("mutations_empty")
    if scale_counts["large"] == 0:
        alerts.append("large_scale_mutations_missing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    manifest = {
        "schema_version": "mutation_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mutations": mutations,
    }
    _write_json(args.manifest_out, manifest)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "selected_models": len(selected_models),
        "total_mutations": len(mutations),
        "large_scale_mutations": scale_counts["large"],
        "failure_types_count": len(failure_types),
        "scale_mutation_counts": scale_counts,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "manifest_out": args.manifest_out,
        "sources": {
            "model_registry": args.model_registry,
            "target_scales": sorted(scales),
            "failure_types": failure_types,
            "mutations_per_failure_type": per_type,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "selected_models": len(selected_models), "total_mutations": len(mutations)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
