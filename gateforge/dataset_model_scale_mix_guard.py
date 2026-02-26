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


def _pct(part: int, total: int) -> float:
    return round((part / total) * 100.0, 2) if total > 0 else 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Model Scale Mix Guard",
        "",
        f"- status: `{payload.get('status')}`",
        f"- medium_ratio_pct: `{payload.get('medium_ratio_pct')}`",
        f"- large_ratio_pct: `{payload.get('large_ratio_pct')}`",
        "",
        "## Mix",
        "",
    ]
    mix = payload.get("mix") if isinstance(payload.get("mix"), dict) else {}
    for s in SCALES:
        lines.append(f"- {s}: `{mix.get(s, 0)}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard against over-concentration in small-scale failure data")
    parser.add_argument("--failure-corpus-registry-summary", required=True)
    parser.add_argument("--failure-supply-plan", default=None)
    parser.add_argument("--min-medium-ratio-pct", type=float, default=20.0)
    parser.add_argument("--min-large-ratio-pct", type=float, default=12.0)
    parser.add_argument("--out", default="artifacts/dataset_model_scale_mix_guard/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.failure_corpus_registry_summary)
    supply = _load_json(args.failure_supply_plan)

    reasons: list[str] = []
    if not registry:
        reasons.append("registry_missing")

    counts = registry.get("model_scale_counts") if isinstance(registry.get("model_scale_counts"), dict) else {}
    mix = {s: _to_int(counts.get(s, 0)) for s in SCALES}
    total = sum(mix.values())

    medium_ratio = _pct(mix["medium"], total)
    large_ratio = _pct(mix["large"], total)

    if medium_ratio < float(args.min_medium_ratio_pct):
        reasons.append("medium_ratio_below_threshold")
    if large_ratio < float(args.min_large_ratio_pct):
        reasons.append("large_ratio_below_threshold")

    if supply:
        weekly = _to_int(supply.get("weekly_supply_target", 0))
        if weekly < 6:
            reasons.append("weekly_supply_target_low")

    status = "PASS"
    if reasons:
        status = "NEEDS_REVIEW"
    if "registry_missing" in reasons:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mix": mix,
        "total_cases": total,
        "medium_ratio_pct": medium_ratio,
        "large_ratio_pct": large_ratio,
        "min_medium_ratio_pct": float(args.min_medium_ratio_pct),
        "min_large_ratio_pct": float(args.min_large_ratio_pct),
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_corpus_registry_summary": args.failure_corpus_registry_summary,
            "failure_supply_plan": args.failure_supply_plan,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "medium_ratio_pct": medium_ratio, "large_ratio_pct": large_ratio}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
