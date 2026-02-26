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


def _build_milestones(
    weeks: int,
    chain_status: str,
    chain_score: float,
    saturation_gap_actions: int,
    push_target_large: int,
    public_ready: bool,
) -> list[dict]:
    milestones: list[dict] = []
    total_weeks = max(4, weeks)

    milestones.append(
        {
            "week": 1,
            "milestone_id": "roadmap.w1.chain",
            "objective": "stabilize evidence chain signal quality",
            "kpi_target": f"chain_health_score>={max(72, int(chain_score))}",
            "priority": "P0" if chain_status != "PASS" else "P1",
        }
    )

    if saturation_gap_actions > 0:
        milestones.append(
            {
                "week": 2,
                "milestone_id": "roadmap.w2.saturation",
                "objective": "close top failure-type saturation gaps",
                "kpi_target": f"gap_actions_reduce_by>={max(1, int(saturation_gap_actions * 0.5))}",
                "priority": "P0",
            }
        )
    else:
        milestones.append(
            {
                "week": 2,
                "milestone_id": "roadmap.w2.saturation_hold",
                "objective": "hold saturation baseline",
                "kpi_target": "saturation_index>=85",
                "priority": "P1",
            }
        )

    if push_target_large > 0:
        milestones.append(
            {
                "week": 3,
                "milestone_id": "roadmap.w3.large",
                "objective": "execute large-model coverage push",
                "kpi_target": f"new_large_cases>={push_target_large}",
                "priority": "P0",
            }
        )
    else:
        milestones.append(
            {
                "week": 3,
                "milestone_id": "roadmap.w3.large_hold",
                "objective": "maintain large-model coverage",
                "kpi_target": "push_target_large_cases=0",
                "priority": "P1",
            }
        )

    pub_week = min(total_weeks, 4)
    milestones.append(
        {
            "week": pub_week,
            "milestone_id": f"roadmap.w{pub_week}.public",
            "objective": "ship external anchor evidence bundle",
            "kpi_target": "public_release_ready=true" if public_ready else "public_release_score>=78",
            "priority": "P0" if not public_ready else "P1",
        }
    )

    final_week = total_weeks
    milestones.append(
        {
            "week": final_week,
            "milestone_id": f"roadmap.w{final_week}.moat",
            "objective": "publish moat progress checkpoint",
            "kpi_target": "moat_signal_delta_positive",
            "priority": "P1",
        }
    )
    return milestones


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Moat Roadmap v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- roadmap_health_score: `{payload.get('roadmap_health_score')}`",
        f"- horizon_weeks: `{payload.get('horizon_weeks')}`",
        f"- high_priority_milestones: `{payload.get('high_priority_milestones')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 4-8 week Modelica moat roadmap from chain/saturation/release signals")
    parser.add_argument("--evidence-chain-summary", required=True)
    parser.add_argument("--failure-corpus-saturation-summary", required=True)
    parser.add_argument("--large-coverage-push-v1-summary", required=True)
    parser.add_argument("--anchor-public-release-v1-summary", required=True)
    parser.add_argument("--horizon-weeks", type=int, default=6)
    parser.add_argument("--out", default="artifacts/dataset_modelica_moat_roadmap_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    chain = _load_json(args.evidence_chain_summary)
    saturation = _load_json(args.failure_corpus_saturation_summary)
    large_push = _load_json(args.large_coverage_push_v1_summary)
    release = _load_json(args.anchor_public_release_v1_summary)

    reasons: list[str] = []
    if not chain:
        reasons.append("evidence_chain_summary_missing")
    if not saturation:
        reasons.append("failure_corpus_saturation_summary_missing")
    if not large_push:
        reasons.append("large_coverage_push_summary_missing")
    if not release:
        reasons.append("anchor_public_release_summary_missing")

    chain_status = str(chain.get("status") or "UNKNOWN")
    saturation_status = str(saturation.get("status") or "UNKNOWN")
    push_status = str(large_push.get("status") or "UNKNOWN")
    release_status = str(release.get("status") or "UNKNOWN")

    chain_score = _to_float(chain.get("chain_health_score", 0.0))
    saturation_index = _to_float(saturation.get("saturation_index", 0.0))
    release_score = _to_float(release.get("public_release_score", 0.0))
    push_target_large = _to_int(large_push.get("push_target_large_cases", 0))
    saturation_gap_actions = _to_int(saturation.get("total_gap_actions", 0))
    public_ready = bool(release.get("public_release_ready", False))

    roadmap_score = _clamp(
        (chain_score * 0.34)
        + (saturation_index * 0.32)
        + (release_score * 0.26)
        + (8.0 if push_target_large == 0 else max(0.0, 8.0 - push_target_large * 0.8))
    )
    roadmap_score = _round(roadmap_score)

    milestones = _build_milestones(
        weeks=max(4, min(8, int(args.horizon_weeks))),
        chain_status=chain_status,
        chain_score=chain_score,
        saturation_gap_actions=saturation_gap_actions,
        push_target_large=push_target_large,
        public_ready=public_ready,
    )

    alerts: list[str] = []
    if chain_status != "PASS":
        alerts.append("evidence_chain_not_pass")
    if saturation_status != "PASS":
        alerts.append("corpus_saturation_not_pass")
    if push_status != "PASS":
        alerts.append("large_coverage_push_not_pass")
    if release_status != "PASS":
        alerts.append("public_release_not_pass")
    if roadmap_score < 75.0:
        alerts.append("roadmap_health_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "roadmap_health_score": roadmap_score,
        "horizon_weeks": max(4, min(8, int(args.horizon_weeks))),
        "high_priority_milestones": len([x for x in milestones if str(x.get("priority")) == "P0"]),
        "milestones": milestones,
        "signals": {
            "chain_status": chain_status,
            "chain_health_score": chain_score,
            "saturation_status": saturation_status,
            "saturation_index": saturation_index,
            "large_coverage_push_status": push_status,
            "push_target_large_cases": push_target_large,
            "public_release_status": release_status,
            "public_release_score": release_score,
            "public_release_ready": public_ready,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "evidence_chain_summary": args.evidence_chain_summary,
            "failure_corpus_saturation_summary": args.failure_corpus_saturation_summary,
            "large_coverage_push_v1_summary": args.large_coverage_push_v1_summary,
            "anchor_public_release_v1_summary": args.anchor_public_release_v1_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "roadmap_health_score": roadmap_score, "milestones": len(milestones)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
