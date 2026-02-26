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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _advantage_score_normalized(compare: dict) -> float:
    raw = _to_int(compare.get("advantage_score", 0))
    verdict = str(compare.get("verdict") or "")
    base = (raw + 5) * 10.0
    if verdict == "GATEFORGE_ADVANTAGE":
        base += 8.0
    elif verdict == "PLAIN_CI_BETTER":
        base -= 15.0
    return _clamp(base)


def _build_claims(anchor: dict, compare: dict, benchmark: dict, moat: dict, push: dict) -> list[dict]:
    claims: list[dict] = []
    release_score = _to_float(anchor.get("release_score", 0.0))
    verdict = str(compare.get("verdict") or "UNKNOWN")
    drift = _to_float(benchmark.get("failure_type_drift", 0.0))
    moat_score = _to_float(((moat.get("metrics") or {}).get("moat_score", 0.0)))
    push_target = _to_int(push.get("push_target_large_cases", 0))

    claims.append(
        {
            "claim_id": "claim.release_strength",
            "text": f"Anchor release evidence score reached {release_score}",
            "metric": "release_score",
            "value": release_score,
        }
    )
    claims.append(
        {
            "claim_id": "claim.comparison_verdict",
            "text": f"GateForge vs plain CI verdict is {verdict}",
            "metric": "comparison_verdict",
            "value": verdict,
        }
    )
    claims.append(
        {
            "claim_id": "claim.failure_distribution",
            "text": f"Failure type drift is {drift}",
            "metric": "failure_type_drift",
            "value": drift,
        }
    )
    claims.append(
        {
            "claim_id": "claim.moat_score",
            "text": f"Current moat trend score is {moat_score}",
            "metric": "moat_score",
            "value": moat_score,
        }
    )
    claims.append(
        {
            "claim_id": "claim.large_push_target",
            "text": f"Additional large-case push target is {push_target}",
            "metric": "push_target_large_cases",
            "value": push_target,
        }
    )
    return claims


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Anchor Public Release v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- public_release_ready: `{payload.get('public_release_ready')}`",
        f"- public_release_score: `{payload.get('public_release_score')}`",
        "",
        "## Risk Disclosures",
        "",
    ]
    risks = payload.get("risk_disclosures") if isinstance(payload.get("risk_disclosures"), list) else []
    if risks:
        for item in risks:
            lines.append(f"- `{item}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public-facing anchor release card from dataset evidence signals")
    parser.add_argument("--anchor-release-bundle-v3-summary", required=True)
    parser.add_argument("--gateforge-vs-plain-ci-summary", required=True)
    parser.add_argument("--failure-distribution-benchmark-v2-summary", required=True)
    parser.add_argument("--moat-trend-snapshot-summary", default=None)
    parser.add_argument("--large-coverage-push-v1-summary", default=None)
    parser.add_argument("--min-public-release-score", type=float, default=75.0)
    parser.add_argument("--out", default="artifacts/dataset_anchor_public_release_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    anchor = _load_json(args.anchor_release_bundle_v3_summary)
    compare = _load_json(args.gateforge_vs_plain_ci_summary)
    benchmark = _load_json(args.failure_distribution_benchmark_v2_summary)
    moat = _load_json(args.moat_trend_snapshot_summary)
    push = _load_json(args.large_coverage_push_v1_summary)

    reasons: list[str] = []
    if not anchor:
        reasons.append("anchor_release_bundle_missing")
    if not compare:
        reasons.append("gateforge_vs_plain_ci_summary_missing")
    if not benchmark:
        reasons.append("failure_distribution_benchmark_v2_summary_missing")

    release_score = _to_float(anchor.get("release_score", 0.0))
    advantage_norm = _advantage_score_normalized(compare)
    benchmark_match_ratio = _to_float(benchmark.get("validated_match_ratio_pct", 0.0))
    drift = _to_float(benchmark.get("failure_type_drift", 1.0))
    moat_score = _to_float(((moat.get("metrics") or {}).get("moat_score", 50.0))
    )
    push_target = _to_int(push.get("push_target_large_cases", 0))
    push_status = str(push.get("status") or "")

    public_score = (
        release_score * 0.42
        + advantage_norm * 0.24
        + benchmark_match_ratio * 0.18
        + moat_score * 0.16
    )
    if drift > 0.4:
        public_score -= 8.0
    if push_target > 0:
        public_score -= min(8.0, push_target * 0.8)
    if push_status == "FAIL":
        public_score -= 6.0
    public_score = _round(_clamp(public_score))

    risk_disclosures: list[str] = []
    verdict = str(compare.get("verdict") or "")
    if verdict != "GATEFORGE_ADVANTAGE":
        risk_disclosures.append("comparison_verdict_not_gateforge_advantage")
    if drift > 0.35:
        risk_disclosures.append("failure_distribution_drift_high")
    if benchmark_match_ratio < 70.0:
        risk_disclosures.append("validated_match_ratio_low")
    if push_target > 0:
        risk_disclosures.append("large_model_coverage_gap_open")
    if push_status == "FAIL":
        risk_disclosures.append("large_coverage_push_source_invalid")

    public_release_ready = (
        public_score >= float(args.min_public_release_score)
        and not risk_disclosures
        and not reasons
    )

    status = "PASS" if public_release_ready else "NEEDS_REVIEW"
    if any(x.endswith("_missing") for x in reasons):
        status = "FAIL"

    anchor_id = str(anchor.get("release_bundle_id") or "unknown_anchor")
    playbook = anchor.get("reproducible_playbook") if isinstance(anchor.get("reproducible_playbook"), list) else []
    claims = _build_claims(anchor, compare, benchmark, moat, push)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "public_release_ready": public_release_ready,
        "public_release_score": public_score,
        "anchor_release_bundle_id": anchor_id,
        "headline_claims": claims,
        "risk_disclosures": risk_disclosures,
        "reproducibility_playbook": playbook[:12],
        "sources": {
            "anchor_release_bundle_v3_summary": args.anchor_release_bundle_v3_summary,
            "gateforge_vs_plain_ci_summary": args.gateforge_vs_plain_ci_summary,
            "failure_distribution_benchmark_v2_summary": args.failure_distribution_benchmark_v2_summary,
            "moat_trend_snapshot_summary": args.moat_trend_snapshot_summary,
            "large_coverage_push_v1_summary": args.large_coverage_push_v1_summary,
        },
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "public_release_ready": public_release_ready, "public_release_score": public_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
