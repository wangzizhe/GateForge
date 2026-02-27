from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATTERNS = {
    "simulate_error": "break_solver_stability",
    "model_check_error": "violate_connector_type",
    "semantic_regression": "invert_control_polarity",
    "numerical_instability": "increase_step_stiffness",
    "constraint_violation": "break_constraint_limit",
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


def _extract_failure_types(saturation: dict) -> list[str]:
    rows = saturation.get("target_failure_types") if isinstance(saturation.get("target_failure_types"), list) else []
    out = sorted({_slug(x, default="") for x in rows if _slug(x, default="")})
    return out or sorted(DEFAULT_PATTERNS.keys())


def _extract_missing_types(balance: dict) -> set[str]:
    rows = balance.get("missing_failure_types") if isinstance(balance.get("missing_failure_types"), list) else []
    return {_slug(x, default="") for x in rows if _slug(x, default="")}


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Mutation Recipe Library v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_recipes: `{payload.get('total_recipes')}`",
        f"- large_scale_recipes: `{payload.get('large_scale_recipes')}`",
        f"- high_priority_recipes: `{payload.get('high_priority_recipes')}`",
        f"- recipe_coverage_score: `{payload.get('recipe_coverage_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reusable mutation recipe library from coverage gaps and scale readiness")
    parser.add_argument("--failure-corpus-saturation-summary", required=True)
    parser.add_argument("--mutation-portfolio-balance-summary", default=None)
    parser.add_argument("--model-scale-ladder-summary", default=None)
    parser.add_argument("--recipes-out", default="artifacts/dataset_modelica_mutation_recipe_library_v1/recipes.json")
    parser.add_argument("--out", default="artifacts/dataset_modelica_mutation_recipe_library_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    saturation = _load_json(args.failure_corpus_saturation_summary)
    balance = _load_json(args.mutation_portfolio_balance_summary)
    ladder = _load_json(args.model_scale_ladder_summary)

    reasons: list[str] = []
    if not saturation:
        reasons.append("failure_corpus_saturation_summary_missing")

    target_types = _extract_failure_types(saturation)
    missing_types = _extract_missing_types(balance)
    large_ready = bool(ladder.get("large_ready", True))

    recipes: list[dict] = []
    for failure_type in target_types:
        for scale in ["medium", "large"]:
            priority = "P2"
            if failure_type in missing_types:
                priority = "P0"
            elif scale == "large":
                priority = "P1"
            execution_mode = "execute"
            if scale == "large" and not large_ready:
                execution_mode = "plan_only"

            recipes.append(
                {
                    "recipe_id": f"recipe.{failure_type}.{scale}",
                    "failure_type": failure_type,
                    "target_scale": scale,
                    "mutation_pattern": DEFAULT_PATTERNS.get(failure_type, "generic_parameter_shift"),
                    "recommended_seed_count": 3 if scale == "medium" else 5,
                    "execution_mode": execution_mode,
                    "priority": priority,
                }
            )

    alerts: list[str] = []
    if not recipes:
        alerts.append("no_recipes_generated")
    if not large_ready:
        alerts.append("large_scale_not_ready_recipe_mode_plan_only")
    target_lane = len(target_types) * 2
    recipe_coverage_score = round((len(recipes) / target_lane) * 100.0, 2) if target_lane > 0 else 0.0
    lane_allocation = {
        "p0_lane": len([x for x in recipes if x.get("priority") == "P0"]),
        "p1_lane": len([x for x in recipes if x.get("priority") == "P1"]),
        "p2_lane": len([x for x in recipes if x.get("priority") == "P2"]),
    }

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    recipes_payload = {
        "schema_version": "modelica_mutation_recipe_library_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "recipes": recipes,
    }
    _write_json(args.recipes_out, recipes_payload)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_recipes": len(recipes),
        "large_scale_recipes": len([x for x in recipes if x.get("target_scale") == "large"]),
        "high_priority_recipes": len([x for x in recipes if x.get("priority") == "P0"]),
        "recipe_coverage_score": recipe_coverage_score,
        "lane_allocation": lane_allocation,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "recipes_path": args.recipes_out,
        "signals": {
            "target_failure_type_count": len(target_types),
            "missing_failure_type_count": len(missing_types),
            "large_ready": large_ready,
        },
        "sources": {
            "failure_corpus_saturation_summary": args.failure_corpus_saturation_summary,
            "mutation_portfolio_balance_summary": args.mutation_portfolio_balance_summary,
            "model_scale_ladder_summary": args.model_scale_ladder_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_recipes": len(recipes), "high_priority_recipes": payload["high_priority_recipes"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
