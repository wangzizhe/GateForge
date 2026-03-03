from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
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
    "simulate_error": "inject_divide_by_zero_dynamics",
    "model_check_error": "inject_undefined_symbol_equation",
    "semantic_regression": "inject_sign_flip_dynamics",
    "numerical_instability": "inject_ultra_stiff_dynamics",
    "constraint_violation": "inject_hard_assert_false",
}

OPERATOR_FAILURE_TYPE_MAP = {
    "inject_divide_by_zero_dynamics": "simulate_error",
    "inject_zero_time_constant": "simulate_error",
    "inject_stiff_gain_blowup": "numerical_instability",
    "inject_undefined_symbol_equation": "model_check_error",
    "inject_bad_connector_equation": "model_check_error",
    "inject_sign_flip_dynamics": "semantic_regression",
    "inject_parameter_bias_drift": "semantic_regression",
    "inject_hard_assert_false": "constraint_violation",
    "inject_constraint_margin_collapse": "constraint_violation",
    "inject_event_chattering_threshold": "numerical_instability",
}

STAGE_MAP = {
    "simulate_error": "simulate",
    "model_check_error": "check",
    "semantic_regression": "simulate",
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


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or default


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source"]


def _extract_recipes(recipe_library: dict) -> list[dict]:
    rows = recipe_library.get("recipes") if isinstance(recipe_library.get("recipes"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _find_primary_model_name(text: str) -> str:
    m = re.search(r"(?im)^\s*(?:partial\s+)?model\s+([A-Za-z_]\w*)\b", text)
    if not m:
        return ""
    return str(m.group(1))


def _build_mutation_block(*, failure_type: str, token: str, operator_hint: str = "") -> tuple[list[str], str]:
    state_name = f"__gf_state_{token}"
    unknown_name = f"__gf_undef_{token}"
    op = _slug(operator_hint, default="")

    if op == "inject_bad_connector_equation":
        return (
            [
                "  // GateForge mutation: connector integrity failure",
                "equation",
                f"  {unknown_name}_port.p = 1.0;",
            ],
            op,
        )

    if op == "inject_zero_time_constant":
        return (
            [
                "  // GateForge mutation: zero time constant",
                f"  parameter Real __gf_tau_{token} = 0.0;",
                f"  Real {state_name}(start=0.0);",
                "equation",
                f"  der({state_name}) = (1.0 - {state_name}) / __gf_tau_{token};",
            ],
            op,
        )

    if op == "inject_stiff_gain_blowup":
        return (
            [
                "  // GateForge mutation: stiff gain blowup",
                f"  Real {state_name}(start=1.0);",
                "equation",
                f"  der({state_name}) = 1.0e12 * {state_name};",
            ],
            op,
        )

    if op == "inject_parameter_bias_drift":
        return (
            [
                "  // GateForge mutation: parameter bias drift",
                f"  parameter Real __gf_bias_{token} = 1.0e6;",
                f"  Real {state_name}(start=0.0);",
                "equation",
                f"  der({state_name}) = {state_name} + __gf_bias_{token};",
            ],
            op,
        )

    if op == "inject_constraint_margin_collapse":
        return (
            [
                "  // GateForge mutation: constraint margin collapse",
                f"  Real {state_name}(start=0.0);",
                "equation",
                f'  assert({state_name} < -1.0e9, "gateforge_constraint_margin_collapse_{token}");',
            ],
            op,
        )

    if op == "inject_event_chattering_threshold":
        return (
            [
                "  // GateForge mutation: event chattering threshold",
                f"  Real {state_name}(start=0.0);",
                "equation",
                f"  der({state_name}) = 1.0;",
                f"  when sample(0, 1e-9) then reinit({state_name}, -pre({state_name})); end when;",
            ],
            op,
        )

    if failure_type == "model_check_error":
        return (
            [
                "  // GateForge mutation: model check failure",
                "equation",
                f"  {unknown_name} = 1.0;",
            ],
            OPERATOR_MAP[failure_type],
        )
    if failure_type == "simulate_error":
        return (
            [
                f"  Real {state_name}(start=1.0);",
                "  // GateForge mutation: simulation instability",
                "equation",
                f"  der({state_name}) = 1.0 / 0.0;",
            ],
            OPERATOR_MAP[failure_type],
        )
    if failure_type == "semantic_regression":
        return (
            [
                f"  Real {state_name}(start=1.0);",
                "  // GateForge mutation: semantic sign inversion",
                "equation",
                f"  der({state_name}) = -1.0 * {state_name};",
            ],
            OPERATOR_MAP[failure_type],
        )
    if failure_type == "numerical_instability":
        return (
            [
                f"  Real {state_name}(start=1.0);",
                "  // GateForge mutation: ultra stiff dynamics",
                "equation",
                f"  der({state_name}) = 1.0e12 * {state_name};",
            ],
            OPERATOR_MAP[failure_type],
        )
    return (
        [
            "  // GateForge mutation: hard physical constraint violation",
            "equation",
            f'  assert(false, "gateforge_constraint_violation_{token}");',
        ],
        OPERATOR_MAP["constraint_violation"],
    )


def _materialize_text(source_text: str, *, failure_type: str, token: str, operator_hint: str = "") -> tuple[str, str]:
    model_name = _find_primary_model_name(source_text)
    if not model_name:
        raise ValueError("model_block_missing")
    end_match = re.search(rf"(?im)^\s*end\s+{re.escape(model_name)}\s*;", source_text)
    if not end_match:
        raise ValueError("model_end_missing")

    insert_at = int(end_match.start())
    block, operator = _build_mutation_block(failure_type=failure_type, token=token, operator_hint=operator_hint)
    injection = "\n" + "\n".join(block) + "\n"
    mutated = source_text[:insert_at] + injection + source_text[insert_at:]
    return mutated, operator


def _probe_command(mutated_model_path: str) -> str:
    code = (
        "from pathlib import Path; import sys; "
        f"p = Path({json.dumps(mutated_model_path)}); "
        "txt = p.read_text(encoding='utf-8', errors='ignore').lower(); "
        "sys.exit(0 if ('model ' in txt and 'end ' in txt and p.exists()) else 2)"
    )
    return "python3 -c " + shlex.quote(code)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Model Materializer v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- selected_models: `{payload.get('selected_models')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- materialized_mutations: `{payload.get('materialized_mutations')}`",
        f"- failed_materializations: `{payload.get('failed_materializations')}`",
        f"- large_scale_mutations: `{payload.get('large_scale_mutations')}`",
        f"- operator_family_count: `{payload.get('operator_family_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize real Modelica mutant files at scale")
    parser.add_argument("--model-registry", required=True)
    parser.add_argument("--selection-plan", default=None)
    parser.add_argument("--target-scales", default="medium,large")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--mutations-per-failure-type", type=int, default=2)
    parser.add_argument("--recipe-library", default=None)
    parser.add_argument("--mutations-per-recipe", type=int, default=1)
    parser.add_argument("--max-models", type=int, default=0)
    parser.add_argument("--seed-base", type=int, default=1000)
    parser.add_argument("--mutant-root", default="artifacts/dataset_mutation_model_materializer_v1/mutants")
    parser.add_argument("--manifest-out", default="artifacts/dataset_mutation_model_materializer_v1/mutation_manifest.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_model_materializer_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.model_registry)
    selection_plan = _load_json(args.selection_plan)
    recipe_library = _load_json(args.recipe_library)
    reasons: list[str] = []
    if not registry:
        reasons.append("model_registry_missing")

    scales = {_slug(x, default="") for x in str(args.target_scales).split(",") if _slug(x, default="")}
    failure_types = [_slug(x, default="") for x in str(args.failure_types).split(",") if _slug(x, default="")]
    per_type = max(1, int(args.mutations_per_failure_type))
    per_recipe = max(1, int(args.mutations_per_recipe))
    recipes = _extract_recipes(recipe_library)

    models = _extract_models(registry)
    selected_models = [m for m in models if _slug(m.get("suggested_scale"), default="small") in scales]
    selected_models.sort(
        key=lambda x: (0 if _slug(x.get("suggested_scale"), default="small") == "large" else 1, str(x.get("model_id") or ""))
    )
    selection_plan_requested = bool(args.selection_plan)
    selection_plan_applied = False
    selection_plan_missing_models = 0
    if selection_plan_requested:
        selected_ids = selection_plan.get("selected_model_ids") if isinstance(selection_plan.get("selected_model_ids"), list) else []
        selected_ids = [str(x or "").strip() for x in selected_ids if str(x or "").strip()]
        if selected_ids:
            model_map = {str(x.get("model_id") or ""): x for x in selected_models if str(x.get("model_id") or "")}
            planned = [model_map[mid] for mid in selected_ids if mid in model_map]
            selection_plan_missing_models = max(0, len(selected_ids) - len(planned))
            if planned:
                selected_models = planned
                selection_plan_applied = True
    if int(args.max_models) > 0:
        selected_models = selected_models[: int(args.max_models)]

    mutant_root = Path(args.mutant_root)
    mutant_root.mkdir(parents=True, exist_ok=True)

    mutations: list[dict] = []
    failed_materializations = 0
    materialized_operator_families: set[str] = set()

    for midx, model in enumerate(selected_models, start=1):
        model_id = str(model.get("model_id") or "")
        model_path = str(model.get("source_path") or "")
        scale = _slug(model.get("suggested_scale"), default="small")
        if not model_id or not model_path:
            continue
        source = Path(model_path)
        if not source.exists():
            continue
        source_text = _load_text(source)

        plan_rows: list[dict] = []
        if recipes:
            for ridx, recipe in enumerate(recipes, start=1):
                recipe_scale = _slug(recipe.get("target_scale"), default="")
                if recipe_scale and recipe_scale != scale:
                    continue
                operator = _slug(recipe.get("operator"), default="")
                operator_family = _slug(recipe.get("operator_family"), default="generic")
                expected_failure_type = _slug(recipe.get("expected_failure_type"), default="")
                if not expected_failure_type:
                    expected_failure_type = OPERATOR_FAILURE_TYPE_MAP.get(operator, "simulate_error")
                expected_stage = _slug(recipe.get("expected_stage"), default=STAGE_MAP.get(expected_failure_type, "simulate"))
                recipe_id = str(recipe.get("recipe_id") or f"recipe_{ridx}")
                for r in range(per_recipe):
                    plan_rows.append(
                        {
                            "plan_index": ridx,
                            "plan_repeat": r,
                            "recipe_id": recipe_id,
                            "operator_family": operator_family,
                            "operator": operator or OPERATOR_MAP.get(expected_failure_type, "inject_generic_mutation"),
                            "failure_type": expected_failure_type,
                            "expected_stage": expected_stage,
                        }
                    )
        else:
            for fidx, failure_type in enumerate(failure_types, start=1):
                for r in range(per_type):
                    plan_rows.append(
                        {
                            "plan_index": fidx,
                            "plan_repeat": r,
                            "recipe_id": "",
                            "operator_family": "",
                            "operator": OPERATOR_MAP.get(failure_type, "inject_generic_mutation"),
                            "failure_type": failure_type,
                            "expected_stage": STAGE_MAP.get(failure_type, "simulate"),
                        }
                    )

        for plan in plan_rows:
            failure_type = _slug(plan.get("failure_type"), default="simulate_error")
            operator = _slug(plan.get("operator"), default=OPERATOR_MAP.get(failure_type, "inject_generic_mutation"))
            operator_family = _slug(plan.get("operator_family"), default="")
            recipe_id = str(plan.get("recipe_id") or "")
            pidx = int(plan.get("plan_index") or 0)
            prep = int(plan.get("plan_repeat") or 0)

            seed = int(args.seed_base) + midx * 100000 + pidx * 100 + prep
            mutation_id = f"mat_{model_id}_{failure_type}_{seed}"
            token = f"{seed}"
            mutated_model_path = mutant_root / failure_type / model_id / f"{mutation_id}.mo"

            status = "PASS"
            status_reason = "materialized"
            resolved_operator = operator
            mutated_checksum = ""
            try:
                mutated_text, resolved_operator = _materialize_text(
                    source_text,
                    failure_type=failure_type,
                    token=token,
                    operator_hint=operator,
                )
                _write_text(mutated_model_path, mutated_text)
                mutated_checksum = _sha256_text(mutated_text)
            except Exception as exc:
                status = "FAIL"
                status_reason = f"materialization_failed:{type(exc).__name__}"
                failed_materializations += 1

            if operator_family:
                materialized_operator_families.add(operator_family)

            row = {
                "mutation_id": mutation_id,
                "target_model_id": model_id,
                "target_scale": scale,
                "expected_failure_type": failure_type,
                "expected_stage": _slug(plan.get("expected_stage"), default=STAGE_MAP.get(failure_type, "simulate")),
                "operator": resolved_operator,
                "operator_family": operator_family,
                "recipe_id": recipe_id,
                "seed": seed,
                "source_model_path": model_path,
                "mutated_model_path": str(mutated_model_path),
                "materialization_status": status,
                "materialization_reason": status_reason,
                "mutated_checksum_sha256": mutated_checksum,
                "model_id": model_id,
                "failure_type": failure_type,
            }
            row["repro_command"] = _probe_command(str(mutated_model_path))
            mutations.append(row)

    materialized_mutations = len([x for x in mutations if str(x.get("materialization_status") or "") == "PASS"])
    generated_failure_types = sorted({str(x.get("expected_failure_type") or "") for x in mutations if str(x.get("expected_failure_type") or "")})
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
    if selection_plan_requested and not selection_plan:
        alerts.append("selection_plan_missing_or_empty")
    elif selection_plan_requested and not selection_plan_applied:
        alerts.append("selection_plan_no_matching_models")
    elif selection_plan_missing_models > 0:
        alerts.append("selection_plan_partial_match")
    if args.recipe_library and not recipes:
        alerts.append("recipe_library_empty_or_missing")
    if scale_counts["large"] == 0:
        alerts.append("large_scale_mutations_missing")
    if failed_materializations > 0:
        alerts.append("mutation_materialization_failures_present")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    manifest = {
        "schema_version": "mutation_manifest_v2_materialized",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mutant_root": str(mutant_root),
        "mutations": mutations,
    }
    _write_json(args.manifest_out, manifest)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "selected_models": len(selected_models),
        "total_mutations": len(mutations),
        "materialized_mutations": materialized_mutations,
        "failed_materializations": failed_materializations,
        "large_scale_mutations": scale_counts["large"],
        "failure_types_count": len(generated_failure_types),
        "generated_failure_types": generated_failure_types,
        "operator_family_count": len(materialized_operator_families),
        "scale_mutation_counts": scale_counts,
        "selection_plan_requested": selection_plan_requested,
        "selection_plan_applied": selection_plan_applied,
        "selection_plan_missing_models": selection_plan_missing_models,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "manifest_out": args.manifest_out,
        "mutant_root": str(mutant_root),
        "sources": {
            "model_registry": args.model_registry,
            "target_scales": sorted(scales),
            "failure_types": failure_types,
            "mutations_per_failure_type": per_type,
            "selection_plan": args.selection_plan,
            "recipe_library": args.recipe_library,
            "mutations_per_recipe": per_recipe,
            "max_models": int(args.max_models),
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "selected_models": len(selected_models),
                "total_mutations": len(mutations),
                "materialized_mutations": materialized_mutations,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
