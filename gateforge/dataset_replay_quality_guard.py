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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Replay Quality Guard",
        "",
        f"- status: `{payload.get('status')}`",
        f"- confidence_level: `{payload.get('confidence_level')}`",
        f"- sample_size_before: `{payload.get('sample_size_before')}`",
        f"- sample_size_after: `{payload.get('sample_size_after')}`",
        f"- min_required_samples: `{payload.get('min_required_samples')}`",
        f"- delta_magnitude_score: `{payload.get('delta_magnitude_score')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard replay evaluator quality by sample-size and stability checks")
    parser.add_argument("--replay-evaluator", required=True)
    parser.add_argument("--before-benchmark", default=None)
    parser.add_argument("--after-benchmark", default=None)
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--max-delta-instability", type=float, default=0.35)
    parser.add_argument("--out", default="artifacts/dataset_replay_quality_guard/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    replay = _load_json(args.replay_evaluator)
    before_b = _load_json(args.before_benchmark)
    after_b = _load_json(args.after_benchmark)

    replay_delta = replay.get("delta") if isinstance(replay.get("delta"), dict) else {}
    delta_detection = abs(_to_float(replay_delta.get("detection_rate", 0.0)))
    delta_fp = abs(_to_float(replay_delta.get("false_positive_rate", 0.0)))
    delta_reg = abs(_to_float(replay_delta.get("regression_rate", 0.0)))
    delta_review = abs(_to_float(replay_delta.get("review_load", 0.0)))
    delta_magnitude_score = round(delta_detection + delta_fp + delta_reg + min(0.2, delta_review * 0.05), 4)

    sample_size_before = _to_int(before_b.get("total_cases_after", before_b.get("total_cases", 0)))
    sample_size_after = _to_int(after_b.get("total_cases_after", after_b.get("total_cases", 0)))

    reasons: list[str] = []
    if not replay:
        reasons.append("replay_summary_missing")
    if not isinstance(replay_delta, dict) or not replay_delta:
        reasons.append("replay_delta_missing")
    if sample_size_before < int(args.min_samples):
        reasons.append("sample_size_before_insufficient")
    if sample_size_after < int(args.min_samples):
        reasons.append("sample_size_after_insufficient")
    if delta_magnitude_score > float(args.max_delta_instability):
        reasons.append("delta_instability_high")

    if "replay_summary_missing" in reasons or "replay_delta_missing" in reasons:
        status = "FAIL"
        confidence_level = "low"
    elif reasons:
        status = "NEEDS_REVIEW"
        confidence_level = "medium"
    else:
        status = "PASS"
        confidence_level = "high"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "confidence_level": confidence_level,
        "min_required_samples": int(args.min_samples),
        "sample_size_before": sample_size_before,
        "sample_size_after": sample_size_after,
        "delta_magnitude_score": delta_magnitude_score,
        "max_delta_instability": float(args.max_delta_instability),
        "reasons": reasons,
        "sources": {
            "replay_evaluator": args.replay_evaluator,
            "before_benchmark": args.before_benchmark,
            "after_benchmark": args.after_benchmark,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "confidence_level": confidence_level}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
