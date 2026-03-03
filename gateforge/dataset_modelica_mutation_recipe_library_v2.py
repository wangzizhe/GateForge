from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


RECIPE_TEMPLATES = [
    {
        "operator_family": "solver_failure",
        "operator": "inject_divide_by_zero_dynamics",
        "expected_failure_type": "simulate_error",
        "expected_stage": "simulate",
    },
    {
        "operator_family": "solver_failure",
        "operator": "inject_zero_time_constant",
        "expected_failure_type": "simulate_error",
        "expected_stage": "simulate",
    },
    {
        "operator_family": "model_integrity",
        "operator": "inject_undefined_symbol_equation",
        "expected_failure_type": "model_check_error",
        "expected_stage": "check",
    },
    {
        "operator_family": "model_integrity",
        "operator": "inject_bad_connector_equation",
        "expected_failure_type": "model_check_error",
        "expected_stage": "check",
    },
    {
        "operator_family": "semantic_shift",
        "operator": "inject_sign_flip_dynamics",
        "expected_failure_type": "semantic_regression",
        "expected_stage": "simulate",
    },
    {
        "operator_family": "semantic_shift",
        "operator": "inject_parameter_bias_drift",
        "expected_failure_type": "semantic_regression",
        "expected_stage": "simulate",
    },
    {
        "operator_family": "stiffness_pathology",
        "operator": "inject_stiff_gain_blowup",
        "expected_failure_type": "numerical_instability",
        "expected_stage": "simulate",
    },
    {
        "operator_family": "constraint_pathology",
        "operator": "inject_hard_assert_false",
        "expected_failure_type": "constraint_violation",
        "expected_stage": "check",
    },
    {
        "operator_family": "constraint_pathology",
        "operator": "inject_constraint_margin_collapse",
        "expected_failure_type": "constraint_violation",
        "expected_stage": "simulate",
    },
    {
        "operator_family": "event_pathology",
        "operator": "inject_event_chattering_threshold",
        "expected_failure_type": "numerical_instability",
        "expected_stage": "simulate",
    },
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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return "".join(ch if ch.isalnum() else "_" for ch in t).strip("_") or default


def _extract_missing_types(balance: dict) -> set[str]:
    rows = balance.get("missing_failure_types") if isinstance(balance.get("missing_failure_types"), list) else []
    return {_slug(x, default="") for x in rows if _slug(x, default="")}


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Mutation Recipe Library v2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_recipes: `{payload.get('total_recipes')}`",
        f"- operator_family_count: `{payload.get('operator_family_count')}`",
        f"- expected_failure_type_count: `{payload.get('expected_failure_type_count')}`",
        f"- large_scale_recipes: `{payload.get('large_scale_recipes')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build scalable Modelica mutation operator recipe library v2")
    parser.add_argument("--executable-pool-summary", required=True)
    parser.add_argument("--mutation-portfolio-balance-summary", default=None)
    parser.add_argument("--target-scales", default="medium,large")
    parser.add_argument("--recipes-out", default="artifacts/dataset_modelica_mutation_recipe_library_v2/recipes.json")
    parser.add_argument("--out", default="artifacts/dataset_modelica_mutation_recipe_library_v2/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    executable = _load_json(args.executable_pool_summary)
    balance = _load_json(args.mutation_portfolio_balance_summary)

    reasons: list[str] = []
    if not executable:
        reasons.append("executable_pool_summary_missing")

    target_scales = [_slug(x, default="") for x in str(args.target_scales).split(",") if _slug(x, default="")]
    if not target_scales:
        target_scales = ["medium", "large"]

    large_ready = _to_int(executable.get("executable_large_models", 0)) > 0
    missing_types = _extract_missing_types(balance)

    recipes: list[dict] = []
    for scale in target_scales:
        for idx, t in enumerate(RECIPE_TEMPLATES, start=1):
            expected_type = _slug(t.get("expected_failure_type"), default="simulate_error")
            priority = "P2"
            if expected_type in missing_types:
                priority = "P0"
            elif scale == "large":
                priority = "P1"

            execution_mode = "execute"
            if scale == "large" and not large_ready:
                execution_mode = "plan_only"

            recipes.append(
                {
                    "recipe_id": f"v2.{scale}.{idx:02d}.{_slug(t.get('operator_family'), default='family')}",
                    "target_scale": scale,
                    "operator_family": _slug(t.get("operator_family"), default="generic"),
                    "operator": _slug(t.get("operator"), default="inject_generic_mutation"),
                    "expected_failure_type": expected_type,
                    "expected_stage": _slug(t.get("expected_stage"), default="simulate"),
                    "priority": priority,
                    "execution_mode": execution_mode,
                    "recommended_seed_count": 3 if scale == "medium" else 5,
                }
            )

    operator_families = sorted({str(x.get("operator_family") or "") for x in recipes if str(x.get("operator_family") or "")})
    expected_types = sorted({str(x.get("expected_failure_type") or "") for x in recipes if str(x.get("expected_failure_type") or "")})

    alerts: list[str] = []
    if not recipes:
        alerts.append("no_recipes_generated")
    if not large_ready and "large" in target_scales:
        alerts.append("large_scale_recipe_mode_plan_only")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    recipes_payload = {
        "schema_version": "modelica_mutation_recipe_library_v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "recipes": recipes,
    }
    _write_json(args.recipes_out, recipes_payload)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_recipes": len(recipes),
        "operator_family_count": len(operator_families),
        "expected_failure_type_count": len(expected_types),
        "large_scale_recipes": len([x for x in recipes if str(x.get("target_scale") or "") == "large"]),
        "high_priority_recipes": len([x for x in recipes if str(x.get("priority") or "") == "P0"]),
        "recipe_coverage_score": round((len(operator_families) / 6.0) * 100.0, 2),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "large_ready": large_ready,
            "target_scales": target_scales,
            "missing_failure_type_count": len(missing_types),
            "operator_families": operator_families,
            "expected_failure_types": expected_types,
        },
        "recipes_path": args.recipes_out,
        "sources": {
            "executable_pool_summary": args.executable_pool_summary,
            "mutation_portfolio_balance_summary": args.mutation_portfolio_balance_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_recipes": len(recipes),
                "operator_family_count": len(operator_families),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
