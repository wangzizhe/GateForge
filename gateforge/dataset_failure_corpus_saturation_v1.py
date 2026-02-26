from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_TYPES = [
    "simulate_error",
    "model_check_error",
    "semantic_regression",
    "numerical_instability",
    "constraint_violation",
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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _extract_cases(db: dict) -> list[dict]:
    rows = db.get("cases") if isinstance(db.get("cases"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_target_types(baseline: dict, validated: dict) -> list[str]:
    out = set(DEFAULT_TYPES)
    base_rows = baseline.get("selected_cases") if isinstance(baseline.get("selected_cases"), list) else []
    for row in base_rows:
        if not isinstance(row, dict):
            continue
        t = _slug(row.get("failure_type"), default="")
        if t:
            out.add(t)
    val_rows = validated.get("mutations") if isinstance(validated.get("mutations"), list) else []
    for row in val_rows:
        if not isinstance(row, dict):
            continue
        t1 = _slug(row.get("expected_failure_type"), default="")
        t2 = _slug(row.get("observed_majority_failure_type"), default="")
        if t1:
            out.add(t1)
        if t2:
            out.add(t2)
    return sorted(out)


def _count_type(rows: list[dict], failure_type: str) -> int:
    return len([x for x in rows if _slug(x.get("failure_type"), default="unknown") == failure_type])


def _count_large_type(rows: list[dict], failure_type: str) -> int:
    return len(
        [
            x
            for x in rows
            if _slug(x.get("failure_type"), default="unknown") == failure_type
            and _slug(x.get("model_scale"), default="unknown") == "large"
        ]
    )


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Corpus Saturation v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- saturation_index: `{payload.get('saturation_index')}`",
        f"- coverage_ratio_pct: `{payload.get('coverage_ratio_pct')}`",
        f"- large_coverage_ratio_pct: `{payload.get('large_coverage_ratio_pct')}`",
        f"- total_gap_actions: `{payload.get('total_gap_actions')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure failure corpus saturation across failure types and large-model slices")
    parser.add_argument("--failure-corpus-db", required=True)
    parser.add_argument("--failure-baseline-pack", default=None)
    parser.add_argument("--validated-mutation-manifest", default=None)
    parser.add_argument("--target-min-per-failure-type", type=int, default=4)
    parser.add_argument("--target-min-large-per-failure-type", type=int, default=2)
    parser.add_argument("--out", default="artifacts/dataset_failure_corpus_saturation_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    db = _load_json(args.failure_corpus_db)
    baseline = _load_json(args.failure_baseline_pack)
    validated = _load_json(args.validated_mutation_manifest)

    reasons: list[str] = []
    if not db:
        reasons.append("failure_corpus_db_missing")

    rows = _extract_cases(db)
    if db and not rows:
        reasons.append("failure_corpus_empty")

    target_types = _extract_target_types(baseline, validated)
    per_type_target = max(1, int(args.target_min_per_failure_type))
    large_target = max(1, int(args.target_min_large_per_failure_type))

    coverage_table: list[dict] = []
    gap_actions: list[dict] = []
    covered_units = 0
    total_units = 0
    large_covered_units = 0
    large_total_units = 0

    for t in target_types:
        total = _count_type(rows, t)
        large = _count_large_type(rows, t)
        all_gap = max(0, per_type_target - total)
        large_gap = max(0, large_target - large)

        covered_units += min(per_type_target, total)
        total_units += per_type_target
        large_covered_units += min(large_target, large)
        large_total_units += large_target

        coverage_table.append(
            {
                "failure_type": t,
                "total_count": total,
                "large_count": large,
                "target_total_count": per_type_target,
                "target_large_count": large_target,
                "total_gap": all_gap,
                "large_gap": large_gap,
            }
        )
        if all_gap > 0 or large_gap > 0:
            gap_actions.append(
                {
                    "action_id": f"sat.{t}",
                    "failure_type": t,
                    "generate_total_cases": all_gap,
                    "generate_large_cases": large_gap,
                    "priority": "P0" if large_gap > 0 else "P1",
                }
            )

    coverage_ratio = _round((covered_units / total_units) * 100.0) if total_units > 0 else 0.0
    large_ratio = _round((large_covered_units / large_total_units) * 100.0) if large_total_units > 0 else 0.0
    saturation_index = _round(_clamp((coverage_ratio * 0.6) + (large_ratio * 0.4)))
    large_share_pct = _round(
        (len([x for x in rows if _slug(x.get("model_scale"), default="unknown") == "large"]) / len(rows)) * 100.0
    ) if rows else 0.0

    alerts: list[str] = []
    if gap_actions:
        alerts.append("failure_type_coverage_gaps_present")
    if large_ratio < 80.0:
        alerts.append("large_failure_coverage_ratio_low")
    if large_share_pct < 20.0:
        alerts.append("large_case_share_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "saturation_index": saturation_index,
        "coverage_ratio_pct": coverage_ratio,
        "large_coverage_ratio_pct": large_ratio,
        "large_case_share_pct": large_share_pct,
        "target_failure_types": target_types,
        "coverage_table": coverage_table,
        "gap_actions": gap_actions,
        "total_gap_actions": len(gap_actions),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_corpus_db": args.failure_corpus_db,
            "failure_baseline_pack": args.failure_baseline_pack,
            "validated_mutation_manifest": args.validated_mutation_manifest,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "saturation_index": saturation_index, "gap_actions": len(gap_actions)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
