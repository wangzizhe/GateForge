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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Distribution Quality Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- gate_result: `{payload.get('gate_result')}`",
        f"- medium_share_pct: `{payload.get('medium_share_pct')}`",
        f"- large_share_pct: `{payload.get('large_share_pct')}`",
        f"- unique_failure_types: `{payload.get('unique_failure_types')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quality gate for failure baseline distribution and coverage strength")
    parser.add_argument("--failure-baseline-pack", required=True)
    parser.add_argument("--min-medium-share-pct", type=float, default=25.0)
    parser.add_argument("--min-large-share-pct", type=float, default=18.0)
    parser.add_argument("--min-unique-failure-types", type=int, default=5)
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_quality_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    pack = _load_json(args.failure_baseline_pack)

    reasons: list[str] = []
    if not pack:
        reasons.append("failure_baseline_pack_missing")

    cases = pack.get("selected_cases") if isinstance(pack.get("selected_cases"), list) else []
    total = len(cases)
    medium = len([c for c in cases if isinstance(c, dict) and str(c.get("model_scale") or "") == "medium"])
    large = len([c for c in cases if isinstance(c, dict) and str(c.get("model_scale") or "") == "large"])

    medium_share = round((medium / total) * 100.0, 2) if total > 0 else 0.0
    large_share = round((large / total) * 100.0, 2) if total > 0 else 0.0

    failure_types = sorted({str(c.get("failure_type") or "") for c in cases if isinstance(c, dict) and c.get("failure_type")})
    unique_types = len(failure_types)

    if medium_share < float(args.min_medium_share_pct):
        reasons.append("medium_share_below_threshold")
    if large_share < float(args.min_large_share_pct):
        reasons.append("large_share_below_threshold")
    if unique_types < int(args.min_unique_failure_types):
        reasons.append("failure_type_diversity_low")

    gate_result = "PASS"
    if reasons:
        gate_result = "NEEDS_REVIEW"
    status = "PASS" if gate_result == "PASS" else "NEEDS_REVIEW"
    if "failure_baseline_pack_missing" in reasons:
        status = "FAIL"
        gate_result = "FAIL"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gate_result": gate_result,
        "total_cases": total,
        "medium_share_pct": medium_share,
        "large_share_pct": large_share,
        "unique_failure_types": unique_types,
        "failure_types": failure_types,
        "min_medium_share_pct": _to_float(args.min_medium_share_pct),
        "min_large_share_pct": _to_float(args.min_large_share_pct),
        "min_unique_failure_types": _to_int(args.min_unique_failure_types),
        "reasons": sorted(set(reasons)),
        "sources": {"failure_baseline_pack": args.failure_baseline_pack},
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "gate_result": gate_result, "total_cases": total}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
