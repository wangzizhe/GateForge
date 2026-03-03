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


def _delta(curr: float, prev: float) -> float:
    return round(curr - prev, 2)


def _status_transition(previous: dict, current: dict) -> str:
    return f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Weekly Freeze Diff v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- delta_accepted_models: `{trend.get('delta_accepted_models')}`",
        f"- delta_generated_mutations: `{trend.get('delta_generated_mutations')}`",
        f"- delta_reproducible_mutations: `{trend.get('delta_reproducible_mutations')}`",
        f"- delta_canonical_net_growth_models: `{trend.get('delta_canonical_net_growth_models')}`",
        f"- delta_validation_type_match_rate_pct: `{trend.get('delta_validation_type_match_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two weekly freeze manifests and produce growth/quality trend")
    parser.add_argument("--current-freeze-summary", required=True)
    parser.add_argument("--previous-freeze-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_weekly_freeze_diff_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current_freeze_summary)
    previous = _load_json(args.previous_freeze_summary)

    reasons: list[str] = []
    if not current:
        reasons.append("current_freeze_summary_missing")
    if not previous:
        reasons.append("previous_freeze_summary_missing")

    curr_accepted = _to_int(current.get("accepted_models", 0))
    prev_accepted = _to_int(previous.get("accepted_models", 0))
    curr_generated = _to_int(current.get("generated_mutations", 0))
    prev_generated = _to_int(previous.get("generated_mutations", 0))
    curr_repro = _to_int(current.get("reproducible_mutations", 0))
    prev_repro = _to_int(previous.get("reproducible_mutations", 0))
    curr_growth = _to_int(current.get("canonical_net_growth_models", 0))
    prev_growth = _to_int(previous.get("canonical_net_growth_models", 0))
    curr_type_match = _to_float(current.get("validation_type_match_rate_pct", 0.0))
    prev_type_match = _to_float(previous.get("validation_type_match_rate_pct", 0.0))

    curr_sources = current.get("sources") if isinstance(current.get("sources"), dict) else {}
    prev_sources = previous.get("sources") if isinstance(previous.get("sources"), dict) else {}
    curr_checksums = curr_sources.get("checksums_sha256") if isinstance(curr_sources.get("checksums_sha256"), dict) else {}
    prev_checksums = prev_sources.get("checksums_sha256") if isinstance(prev_sources.get("checksums_sha256"), dict) else {}
    changed_sources = sorted(
        [
            k
            for k in sorted(set(curr_checksums.keys()) | set(prev_checksums.keys()))
            if str(curr_checksums.get(k, "")) != str(prev_checksums.get(k, ""))
        ]
    )

    trend = {
        "status_transition": _status_transition(previous, current),
        "delta_accepted_models": curr_accepted - prev_accepted,
        "delta_generated_mutations": curr_generated - prev_generated,
        "delta_reproducible_mutations": curr_repro - prev_repro,
        "delta_canonical_net_growth_models": curr_growth - prev_growth,
        "delta_validation_type_match_rate_pct": _delta(curr_type_match, prev_type_match),
        "changed_sources_count": len(changed_sources),
        "changed_sources": changed_sources[:20],
    }

    alerts: list[str] = []
    if trend["status_transition"] in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("freeze_status_worsened")
    if trend["delta_accepted_models"] < 0:
        alerts.append("accepted_models_decreasing")
    if trend["delta_generated_mutations"] < 0:
        alerts.append("generated_mutations_decreasing")
    if trend["delta_reproducible_mutations"] < 0:
        alerts.append("reproducible_mutations_decreasing")
    if trend["delta_canonical_net_growth_models"] <= 0:
        alerts.append("canonical_net_growth_not_improving")
    if trend["delta_validation_type_match_rate_pct"] < 0:
        alerts.append("validation_type_match_rate_decreasing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "trend": trend,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "current_freeze_summary": args.current_freeze_summary,
            "previous_freeze_summary": args.previous_freeze_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "status_transition": trend["status_transition"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
