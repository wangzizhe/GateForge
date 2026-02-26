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


def _clamp(v: float, lo: float = 0.0, hi: float = 2.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 4)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Signal Calibrator",
        "",
        f"- status: `{payload.get('status')}`",
        f"- calibration_mode: `{payload.get('calibration_mode')}`",
        "",
        "## Weights",
        "",
    ]
    w = payload.get("weights") if isinstance(payload.get("weights"), dict) else {}
    for k in ["detection_weight", "false_positive_weight", "regression_weight", "drift_weight"]:
        lines.append(f"- {k}: `{w.get(k)}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate failure signal weights from benchmark/replay trend")
    parser.add_argument("--failure-distribution-benchmark", required=True)
    parser.add_argument("--policy-patch-replay-evaluator", default=None)
    parser.add_argument("--out", default="artifacts/dataset_failure_signal_calibrator/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    benchmark = _load_json(args.failure_distribution_benchmark)
    replay = _load_json(args.policy_patch_replay_evaluator)

    reasons: list[str] = []
    if not benchmark:
        reasons.append("benchmark_missing")

    drift = _to_float(benchmark.get("distribution_drift_score", 0.0))
    fp = _to_float(benchmark.get("false_positive_rate_after", benchmark.get("false_positive_rate", 0.0)))
    reg = _to_float(benchmark.get("regression_rate_after", benchmark.get("regression_rate", 0.0)))

    replay_delta = replay.get("delta") if isinstance(replay.get("delta"), dict) else {}
    detection_delta = _to_float(replay_delta.get("detection_rate", 0.0))

    detection_weight = _clamp(1.0 + (0.2 if detection_delta < 0 else -0.05 if detection_delta > 0.03 else 0.0))
    fp_weight = _clamp(1.0 + (0.4 if fp > 0.08 else 0.1 if fp > 0.04 else -0.05))
    reg_weight = _clamp(1.0 + (0.45 if reg > 0.14 else 0.15 if reg > 0.08 else -0.05))
    drift_weight = _clamp(1.0 + (0.35 if drift > 0.30 else 0.1 if drift > 0.2 else -0.05))

    mode = "balanced"
    if reg_weight >= 1.3 or fp_weight >= 1.3:
        mode = "strict"
    elif detection_weight <= 0.95 and drift_weight <= 1.0:
        mode = "relaxed"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif mode != "balanced":
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "calibration_mode": mode,
        "weights": {
            "detection_weight": _round(detection_weight),
            "false_positive_weight": _round(fp_weight),
            "regression_weight": _round(reg_weight),
            "drift_weight": _round(drift_weight),
        },
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_distribution_benchmark": args.failure_distribution_benchmark,
            "policy_patch_replay_evaluator": args.policy_patch_replay_evaluator,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "calibration_mode": mode}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
