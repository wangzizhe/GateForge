from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_slug(value: object, *, default: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text.replace("-", "_").replace(" ", "_")


def _extract_cases(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        rows = payload.get("cases")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _distribution(cases: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in cases:
        k = _to_slug(row.get(key))
        out[k] = out.get(k, 0) + 1
    return out


def _normalize_dist(counts: dict[str, int]) -> dict[str, float]:
    total = sum(max(0, int(v)) for v in counts.values())
    if total <= 0:
        return {}
    return {k: round(max(0, int(v)) / total, 6) for k, v in counts.items()}


def _l1_distribution_drift(before: dict[str, int], after: dict[str, int]) -> float:
    pb = _normalize_dist(before)
    pa = _normalize_dist(after)
    keys = set(pb.keys()) | set(pa.keys())
    return round(sum(abs(pa.get(k, 0.0) - pb.get(k, 0.0)) for k in keys) / 2.0, 6)


def _bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "y"}:
            return True
        if v in {"false", "0", "no", "n"}:
            return False
    return default


def _rates(cases: list[dict]) -> dict[str, float]:
    total = len(cases)
    if total == 0:
        return {
            "detection_rate": 0.0,
            "false_positive_rate": 0.0,
            "regression_rate": 0.0,
        }
    detected = len([x for x in cases if _bool(x.get("detected"), default=False)])
    false_positive = len([x for x in cases if _bool(x.get("false_positive"), default=False)])
    regressed = len([x for x in cases if _bool(x.get("regressed"), default=False)])
    return {
        "detection_rate": round(detected / total, 4),
        "false_positive_rate": round(false_positive / total, 4),
        "regression_rate": round(regressed / total, 4),
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    delta = payload.get("delta", {}) if isinstance(payload.get("delta"), dict) else {}
    lines = [
        "# GateForge Failure Distribution Benchmark",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_cases_before: `{payload.get('total_cases_before')}`",
        f"- total_cases_after: `{payload.get('total_cases_after')}`",
        f"- detection_rate_after: `{payload.get('detection_rate_after')}`",
        f"- false_positive_rate_after: `{payload.get('false_positive_rate_after')}`",
        f"- regression_rate_after: `{payload.get('regression_rate_after')}`",
        f"- distribution_drift_score: `{payload.get('distribution_drift_score')}`",
        f"- delta_detection_rate: `{delta.get('detection_rate')}`",
        f"- delta_false_positive_rate: `{delta.get('false_positive_rate')}`",
        f"- delta_regression_rate: `{delta.get('regression_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare failure distribution benchmark before/after")
    parser.add_argument("--before", required=True, help="Before benchmark JSON path")
    parser.add_argument("--after", required=True, help="After benchmark JSON path")
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_benchmark/summary.json")
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--max-detection-drop", type=float, default=0.05)
    parser.add_argument("--max-false-positive-increase", type=float, default=0.05)
    parser.add_argument("--max-regression-rate", type=float, default=0.15)
    parser.add_argument("--max-distribution-drift", type=float, default=0.35)
    args = parser.parse_args()

    before_cases = _extract_cases(_load_json(args.before))
    after_cases = _extract_cases(_load_json(args.after))

    before_rates = _rates(before_cases)
    after_rates = _rates(after_cases)
    detection_delta = round(after_rates["detection_rate"] - before_rates["detection_rate"], 4)
    false_positive_delta = round(after_rates["false_positive_rate"] - before_rates["false_positive_rate"], 4)
    regression_delta = round(after_rates["regression_rate"] - before_rates["regression_rate"], 4)

    before_failure_type_dist = _distribution(before_cases, "failure_type")
    after_failure_type_dist = _distribution(after_cases, "failure_type")
    before_scale_dist = _distribution(before_cases, "model_scale")
    after_scale_dist = _distribution(after_cases, "model_scale")

    failure_type_drift = _l1_distribution_drift(before_failure_type_dist, after_failure_type_dist)
    scale_drift = _l1_distribution_drift(before_scale_dist, after_scale_dist)
    distribution_drift_score = round((failure_type_drift * 0.7) + (scale_drift * 0.3), 6)

    alerts: list[str] = []
    if len(after_cases) == 0:
        alerts.append("benchmark_after_empty")
    if detection_delta < -abs(float(args.max_detection_drop)):
        alerts.append("detection_rate_drop_exceeds_threshold")
    if false_positive_delta > abs(float(args.max_false_positive_increase)):
        alerts.append("false_positive_rate_increase_exceeds_threshold")
    if after_rates["regression_rate"] > abs(float(args.max_regression_rate)):
        alerts.append("regression_rate_exceeds_threshold")
    if distribution_drift_score > abs(float(args.max_distribution_drift)):
        alerts.append("distribution_drift_exceeds_threshold")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    if "benchmark_after_empty" in alerts:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "before_path": args.before,
        "after_path": args.after,
        "total_cases_before": len(before_cases),
        "total_cases_after": len(after_cases),
        "detection_rate_before": before_rates["detection_rate"],
        "detection_rate_after": after_rates["detection_rate"],
        "false_positive_rate_before": before_rates["false_positive_rate"],
        "false_positive_rate_after": after_rates["false_positive_rate"],
        "regression_rate_before": before_rates["regression_rate"],
        "regression_rate_after": after_rates["regression_rate"],
        "delta": {
            "detection_rate": detection_delta,
            "false_positive_rate": false_positive_delta,
            "regression_rate": regression_delta,
        },
        "distribution": {
            "failure_type_before": before_failure_type_dist,
            "failure_type_after": after_failure_type_dist,
            "model_scale_before": before_scale_dist,
            "model_scale_after": after_scale_dist,
            "failure_type_drift": failure_type_drift,
            "model_scale_drift": scale_drift,
        },
        "distribution_drift_score": distribution_drift_score,
        "alerts": alerts,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "distribution_drift_score": distribution_drift_score}))
    if payload.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
