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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _status(payload: dict) -> str:
    return str(payload.get("status") or "UNKNOWN")


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Public Scoreboard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- moat_public_score: `{payload.get('moat_public_score')}`",
        f"- grade: `{payload.get('grade')}`",
        f"- verdict: `{payload.get('verdict')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public-facing moat scoreboard from release, chain, roadmap, campaign, and expansion signals")
    parser.add_argument("--anchor-public-release-v1-summary", required=True)
    parser.add_argument("--evidence-chain-summary", required=True)
    parser.add_argument("--modelica-moat-roadmap-v1-summary", required=True)
    parser.add_argument("--mutation-campaign-tracker-v1-summary", required=True)
    parser.add_argument("--modelica-library-expansion-plan-v1-summary", required=True)
    parser.add_argument("--modelica-library-provenance-guard-v1-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_public_scoreboard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    release = _load_json(args.anchor_public_release_v1_summary)
    chain = _load_json(args.evidence_chain_summary)
    roadmap = _load_json(args.modelica_moat_roadmap_v1_summary)
    campaign = _load_json(args.mutation_campaign_tracker_v1_summary)
    expansion = _load_json(args.modelica_library_expansion_plan_v1_summary)
    provenance = _load_json(args.modelica_library_provenance_guard_v1_summary)

    reasons: list[str] = []
    if not release:
        reasons.append("anchor_public_release_summary_missing")
    if not chain:
        reasons.append("evidence_chain_summary_missing")
    if not roadmap:
        reasons.append("modelica_moat_roadmap_summary_missing")
    if not campaign:
        reasons.append("mutation_campaign_tracker_summary_missing")
    if not expansion:
        reasons.append("modelica_library_expansion_plan_summary_missing")

    release_score = _to_float(release.get("public_release_score", 0.0))
    chain_score = _to_float(chain.get("chain_health_score", 0.0))
    roadmap_score = _to_float(roadmap.get("roadmap_health_score", 0.0))
    campaign_completion = _to_float(campaign.get("completion_ratio_pct", 0.0))
    expansion_score = _to_float(expansion.get("expansion_readiness_score", 0.0))
    provenance_score = _to_float(provenance.get("provenance_completeness_pct", 92.0)) if provenance else 92.0

    moat_public_score = round(
        _clamp(
            (release_score * 0.27)
            + (chain_score * 0.22)
            + (roadmap_score * 0.2)
            + (campaign_completion * 0.16)
            + (expansion_score * 0.1)
            + (provenance_score * 0.05)
        ),
        2,
    )

    component_status = {
        "release": _status(release),
        "chain": _status(chain),
        "roadmap": _status(roadmap),
        "campaign": _status(campaign),
        "expansion": _status(expansion),
        "provenance": _status(provenance) if provenance else "NOT_PROVIDED",
    }

    fail_components = [k for k, v in component_status.items() if v == "FAIL"]
    review_components = [k for k, v in component_status.items() if v == "NEEDS_REVIEW"]

    alerts: list[str] = []
    if fail_components:
        alerts.append("critical_component_failures_present")
    if review_components:
        alerts.append("component_review_items_present")
    if moat_public_score < 78.0:
        alerts.append("moat_public_score_below_target")
    if campaign_completion < 70.0:
        alerts.append("campaign_completion_low")
    if expansion_score < 72.0:
        alerts.append("expansion_readiness_low")

    verdict = "EMERGING_MOAT"
    if moat_public_score >= 85.0 and not fail_components:
        verdict = "STRONG_MOAT_SIGNAL"
    elif moat_public_score < 70.0 or fail_components:
        verdict = "INSUFFICIENT_EVIDENCE"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "moat_public_score": moat_public_score,
        "grade": _grade(moat_public_score),
        "verdict": verdict,
        "component_status": component_status,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "score_breakdown": {
            "release_score": release_score,
            "chain_score": chain_score,
            "roadmap_score": roadmap_score,
            "campaign_completion_ratio_pct": campaign_completion,
            "expansion_readiness_score": expansion_score,
            "provenance_completeness_pct": provenance_score,
        },
        "sources": {
            "anchor_public_release_v1_summary": args.anchor_public_release_v1_summary,
            "evidence_chain_summary": args.evidence_chain_summary,
            "modelica_moat_roadmap_v1_summary": args.modelica_moat_roadmap_v1_summary,
            "mutation_campaign_tracker_v1_summary": args.mutation_campaign_tracker_v1_summary,
            "modelica_library_expansion_plan_v1_summary": args.modelica_library_expansion_plan_v1_summary,
            "modelica_library_provenance_guard_v1_summary": args.modelica_library_provenance_guard_v1_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "moat_public_score": moat_public_score, "verdict": verdict}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
