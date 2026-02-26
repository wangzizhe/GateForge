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


def _slug(v: object, *, default: str = "unknown") -> str:
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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _extract_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return _round((count / total) * 100.0)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Portfolio Balance v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- portfolio_balance_score: `{payload.get('portfolio_balance_score')}`",
        f"- large_mutation_ratio_pct: `{payload.get('large_mutation_ratio_pct')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Assess mutation portfolio balance across failure types and model scales")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--failure-corpus-saturation-summary", required=True)
    parser.add_argument("--evidence-chain-summary", default=None)
    parser.add_argument("--min-large-mutation-ratio-pct", type=float, default=25.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_portfolio_balance_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    saturation = _load_json(args.failure_corpus_saturation_summary)
    chain = _load_json(args.evidence_chain_summary)

    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not saturation:
        reasons.append("failure_corpus_saturation_summary_missing")

    rows = _extract_mutations(manifest)
    if manifest and not rows:
        reasons.append("mutation_manifest_empty")

    total = len(rows)
    scale_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        scale = _slug(row.get("target_scale"), default="unknown")
        ftype = _slug(row.get("expected_failure_type"), default="unknown")
        scale_counts[scale] = scale_counts.get(scale, 0) + 1
        type_counts[ftype] = type_counts.get(ftype, 0) + 1

    large_count = _to_int(scale_counts.get("large", 0))
    medium_count = _to_int(scale_counts.get("medium", 0))
    large_ratio = _ratio(large_count, total)

    target_types = saturation.get("target_failure_types") if isinstance(saturation.get("target_failure_types"), list) else []
    target_type_set = {_slug(x, default="") for x in target_types if _slug(x, default="")}
    missing_types = sorted([x for x in target_type_set if _to_int(type_counts.get(x, 0)) == 0])

    gap_actions = _to_int(saturation.get("total_gap_actions", 0))
    chain_score = _to_float(chain.get("chain_health_score", 72.0))

    diversity_ratio = _ratio(len([k for k, v in type_counts.items() if v > 0]), len(target_type_set) if target_type_set else 1)
    balance_score = _clamp(
        12.0
        + (large_ratio * 0.4)
        + (diversity_ratio * 0.38)
        + (min(100.0, chain_score) * 0.22)
        - (min(15.0, gap_actions * 1.5))
    )
    balance_score = _round(balance_score)

    rebalance_actions: list[dict] = []
    for t in missing_types:
        rebalance_actions.append(
            {
                "action_id": f"portfolio.ft.{t}",
                "action_type": "increase_failure_type_mutations",
                "failure_type": t,
                "recommended_new_mutations": max(2, gap_actions // 2),
                "priority": "P0",
            }
        )
    if large_ratio < float(args.min_large_mutation_ratio_pct):
        rebalance_actions.append(
            {
                "action_id": "portfolio.scale.large",
                "action_type": "increase_large_scale_mutations",
                "recommended_new_mutations": max(3, int(float(args.min_large_mutation_ratio_pct) // 10)),
                "priority": "P0",
            }
        )
    if medium_count == 0 and total > 0:
        rebalance_actions.append(
            {
                "action_id": "portfolio.scale.medium",
                "action_type": "backfill_medium_scale_mutations",
                "recommended_new_mutations": 2,
                "priority": "P1",
            }
        )

    alerts: list[str] = []
    if missing_types:
        alerts.append("failure_type_mutation_coverage_gaps")
    if large_ratio < float(args.min_large_mutation_ratio_pct):
        alerts.append("large_mutation_ratio_low")
    if balance_score < 72.0:
        alerts.append("portfolio_balance_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "portfolio_balance_score": balance_score,
        "large_mutation_ratio_pct": large_ratio,
        "failure_type_diversity_ratio_pct": diversity_ratio,
        "total_mutations": total,
        "scale_counts": scale_counts,
        "failure_type_counts": type_counts,
        "missing_failure_types": missing_types,
        "rebalance_actions": rebalance_actions,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "failure_corpus_saturation_summary": args.failure_corpus_saturation_summary,
            "evidence_chain_summary": args.evidence_chain_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "portfolio_balance_score": balance_score, "rebalance_actions": len(rebalance_actions)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
