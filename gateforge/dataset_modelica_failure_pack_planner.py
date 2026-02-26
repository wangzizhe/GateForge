from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

SCALES = ["small", "medium", "large"]


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
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


def _parse_scale(task_id: str, size_hint: str) -> str:
    if size_hint in SCALES:
        return size_hint
    if ".large" in task_id:
        return "large"
    if ".medium" in task_id:
        return "medium"
    return "small"


def _build_pack_plan(coverage_plan: dict, ladder: dict, registry: dict) -> tuple[list[dict], list[str]]:
    plan_rows = coverage_plan.get("plan") if isinstance(coverage_plan.get("plan"), list) else []
    ladder_counts = ladder.get("scale_counts") if isinstance(ladder.get("scale_counts"), dict) else {}
    registry_counts = registry.get("model_scale_counts") if isinstance(registry.get("model_scale_counts"), dict) else {}

    bucket: dict[str, dict] = {
        "small": {"target_new_cases": 0, "source_plan_ids": [], "focus_topics": []},
        "medium": {"target_new_cases": 0, "source_plan_ids": [], "focus_topics": []},
        "large": {"target_new_cases": 0, "source_plan_ids": [], "focus_topics": []},
    }

    for row in plan_rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("source_task_id") or "")
        size_hint = str(row.get("size_hint") or "")
        priority = str(row.get("priority") or "P2")
        scale = _parse_scale(task_id, size_hint)
        delta = _to_float(row.get("expected_moat_delta", 0.0))

        base = 1
        if priority == "P0":
            base = 3
        elif priority == "P1":
            base = 2
        extra = 1 if delta >= 6.0 else 0

        bucket[scale]["target_new_cases"] += base + extra
        bucket[scale]["source_plan_ids"].append(str(row.get("plan_id") or task_id or "unknown"))
        bucket[scale]["focus_topics"].append(str(row.get("focus") or "coverage_gap"))

    rows: list[dict] = []
    reasons: list[str] = []

    for scale in SCALES:
        ladder_count = _to_int(ladder_counts.get(scale, 0))
        registry_count = _to_int(registry_counts.get(scale, 0))
        target = _to_int(bucket[scale]["target_new_cases"])

        if scale == "large" and target < 2:
            target = 2
        if scale == "medium" and target < 2:
            target = 2

        readiness = "ready"
        if scale == "large" and ladder_count == 0:
            readiness = "bootstrap_required"
            reasons.append("large_scale_bootstrap_required")
        elif scale == "medium" and ladder_count == 0:
            readiness = "bootstrap_required"
            reasons.append("medium_scale_bootstrap_required")

        confidence = "high" if registry_count >= 5 else ("medium" if registry_count >= 2 else "low")
        if confidence == "low":
            reasons.append(f"{scale}_registry_depth_low")

        rows.append(
            {
                "scale": scale,
                "target_new_cases": target,
                "existing_registry_cases": registry_count,
                "ladder_evidence_cases": ladder_count,
                "readiness": readiness,
                "execution_confidence": confidence,
                "focus_topics": sorted(set(bucket[scale]["focus_topics"]))[:6],
                "source_plan_ids": bucket[scale]["source_plan_ids"][:12],
            }
        )

    rows.sort(key=lambda x: (0 if x.get("scale") == "large" else 1 if x.get("scale") == "medium" else 2))
    return rows, sorted(set(reasons))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Modelica Failure Pack Planner",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_target_new_cases: `{payload.get('total_target_new_cases')}`",
        f"- medium_target_new_cases: `{payload.get('medium_target_new_cases')}`",
        f"- large_target_new_cases: `{payload.get('large_target_new_cases')}`",
        "",
        "## Scale Plan",
        "",
    ]

    for row in payload.get("scale_plan") if isinstance(payload.get("scale_plan"), list) else []:
        lines.append(
            f"- `{row.get('scale')}` target_new_cases=`{row.get('target_new_cases')}` readiness=`{row.get('readiness')}` confidence=`{row.get('execution_confidence')}`"
        )

    lines.extend(["", "## Reasons", ""])
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan Modelica failure-pack construction across small/medium/large scales")
    parser.add_argument("--failure-coverage-planner", required=True)
    parser.add_argument("--model-scale-ladder", default=None)
    parser.add_argument("--failure-corpus-registry-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_modelica_failure_pack_planner/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    coverage_plan = _load_json(args.failure_coverage_planner)
    ladder = _load_json(args.model_scale_ladder)
    registry = _load_json(args.failure_corpus_registry_summary)

    reasons: list[str] = []
    if not coverage_plan:
        reasons.append("failure_coverage_plan_missing")

    scale_plan, derived_reasons = _build_pack_plan(coverage_plan, ladder, registry) if coverage_plan else ([], [])
    reasons.extend(derived_reasons)

    medium_target = sum(_to_int(x.get("target_new_cases", 0)) for x in scale_plan if x.get("scale") == "medium")
    large_target = sum(_to_int(x.get("target_new_cases", 0)) for x in scale_plan if x.get("scale") == "large")
    total_target = sum(_to_int(x.get("target_new_cases", 0)) for x in scale_plan)

    status = "PASS"
    if not coverage_plan:
        status = "FAIL"
    elif total_target > 0:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_target_new_cases": total_target,
        "medium_target_new_cases": medium_target,
        "large_target_new_cases": large_target,
        "scale_plan": scale_plan,
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_coverage_planner": args.failure_coverage_planner,
            "model_scale_ladder": args.model_scale_ladder,
            "failure_corpus_registry_summary": args.failure_corpus_registry_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_target_new_cases": total_target, "large_target_new_cases": large_target}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
