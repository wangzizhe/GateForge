from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TAXONOMY_PATH = "benchmarks/agent_modelica_problem_taxonomy_v1.json"
DEFAULT_QUOTA_PATH = "benchmarks/agent_modelica_problem_quota_v1.json"
DEFAULT_SCALES = ("small", "medium", "large")


def _load_json(path: str) -> dict:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Mutation Plan Builder v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_plan_rows: `{payload.get('total_plan_rows')}`",
        f"- total_target_mutants: `{payload.get('total_target_mutants')}`",
        f"- failure_type_count: `{payload.get('failure_type_count')}`",
        "",
        "## Targets By Scale",
        "",
    ]
    by_scale = payload.get("target_mutants_by_scale") if isinstance(payload.get("target_mutants_by_scale"), dict) else {}
    for scale in sorted(by_scale.keys()):
        lines.append(f"- {scale}: `{by_scale.get(scale)}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except Exception:
        return default


def _scales(raw: str) -> list[str]:
    rows = [str(x).strip().lower() for x in str(raw or "").split(",") if str(x).strip()]
    if not rows:
        return list(DEFAULT_SCALES)
    return rows


def _pick_target(quota_payload: dict, failure_type: str, scale: str) -> int:
    overrides = quota_payload.get("failure_type_overrides") if isinstance(quota_payload.get("failure_type_overrides"), dict) else {}
    default_by_scale = (
        quota_payload.get("default_target_per_scale_failure_type")
        if isinstance(quota_payload.get("default_target_per_scale_failure_type"), dict)
        else {}
    )
    row = overrides.get(failure_type) if isinstance(overrides.get(failure_type), dict) else {}
    if scale in row:
        return max(0, _to_int(row.get(scale), 0))
    return max(0, _to_int(default_by_scale.get(scale), 0))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build executable mutation plan from problem taxonomy and quota profile")
    parser.add_argument("--taxonomy", default=DEFAULT_TAXONOMY_PATH)
    parser.add_argument("--quota-profile", default=DEFAULT_QUOTA_PATH)
    parser.add_argument("--scales", default=",".join(DEFAULT_SCALES))
    parser.add_argument("--failure-types", default="")
    parser.add_argument("--operators-per-type", type=int, default=3)
    parser.add_argument("--plan-out", default="artifacts/agent_modelica_mutation_plan_builder_v1/plan.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_mutation_plan_builder_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    taxonomy = _load_json(args.taxonomy)
    quota_profile = _load_json(args.quota_profile)
    scales = _scales(args.scales)
    wanted_failure_types = {str(x).strip().lower() for x in str(args.failure_types or "").split(",") if str(x).strip()}
    operators_per_type = max(1, int(args.operators_per_type))

    reasons: list[str] = []
    problem_types = taxonomy.get("problem_types") if isinstance(taxonomy.get("problem_types"), list) else []
    problem_types = [x for x in problem_types if isinstance(x, dict) and str(x.get("failure_type") or "").strip()]
    if not problem_types:
        reasons.append("problem_taxonomy_missing_or_empty")

    if not quota_profile:
        reasons.append("quota_profile_missing")

    plan_rows: list[dict] = []
    for item in problem_types:
        failure_type = str(item.get("failure_type") or "").strip().lower()
        if wanted_failure_types and failure_type not in wanted_failure_types:
            continue
        operators = [str(x) for x in (item.get("mutation_operators") or []) if isinstance(x, str)]
        operator_candidates = operators[:operators_per_type]
        for scale in scales:
            target_count = _pick_target(quota_profile, failure_type=failure_type, scale=scale)
            if target_count <= 0:
                continue
            plan_rows.append(
                {
                    "plan_id": f"plan.{scale}.{failure_type}",
                    "scale": scale,
                    "failure_type": failure_type,
                    "expected_stage": str(item.get("expected_stage") or "simulate"),
                    "category": str(item.get("category") or ""),
                    "severity": str(item.get("severity") or ""),
                    "common_scenarios": [str(x) for x in (item.get("common_scenarios") or []) if isinstance(x, str)],
                    "patch_objective": str(item.get("patch_objective") or ""),
                    "target_mutant_count": int(target_count),
                    "operator_candidates": operator_candidates,
                    "operator_candidate_count": len(operator_candidates),
                }
            )

    target_mutants_by_scale: dict[str, int] = {}
    target_mutants_by_failure_type: dict[str, int] = {}
    for row in plan_rows:
        scale = str(row.get("scale") or "")
        failure_type = str(row.get("failure_type") or "")
        target = int(row.get("target_mutant_count", 0) or 0)
        target_mutants_by_scale[scale] = int(target_mutants_by_scale.get(scale, 0)) + target
        target_mutants_by_failure_type[failure_type] = int(target_mutants_by_failure_type.get(failure_type, 0)) + target

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif not plan_rows:
        status = "FAIL"
        reasons.append("no_plan_rows_generated")

    plan_payload = {
        "schema_version": "agent_modelica_mutation_plan_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_rows": plan_rows,
    }
    _write_json(args.plan_out, plan_payload)

    summary = {
        "schema_version": "agent_modelica_mutation_plan_builder_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_plan_rows": len(plan_rows),
        "total_target_mutants": sum(int(x.get("target_mutant_count", 0) or 0) for x in plan_rows),
        "failure_type_count": len({str(x.get("failure_type") or "") for x in plan_rows}),
        "target_mutants_by_scale": target_mutants_by_scale,
        "target_mutants_by_failure_type": target_mutants_by_failure_type,
        "sources": {
            "taxonomy": args.taxonomy,
            "quota_profile": args.quota_profile,
            "scales": scales,
            "failure_types_filter": sorted(wanted_failure_types),
            "operators_per_type": operators_per_type,
        },
        "reasons": reasons,
        "plan_out": args.plan_out,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": status,
                "total_plan_rows": len(plan_rows),
                "total_target_mutants": summary.get("total_target_mutants"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
