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


def _build_advice(taxonomy: dict, benchmark: dict, ladder: dict) -> tuple[dict, dict, str]:
    missing_failure_types_count = len(taxonomy.get("missing_failure_types") or [])
    missing_model_scales_count = len(taxonomy.get("missing_model_scales") or [])
    drift_score = _to_float(benchmark.get("distribution_drift_score", 0.0))
    false_positive_rate_after = _to_float(benchmark.get("false_positive_rate_after", 0.0))
    regression_rate_after = _to_float(benchmark.get("regression_rate_after", 0.0))
    detection_rate_after = _to_float(benchmark.get("detection_rate_after", 0.0))
    large_ready = bool(ladder.get("large_ready")) if ladder else False

    signals = {
        "missing_failure_types_count": missing_failure_types_count,
        "missing_model_scales_count": missing_model_scales_count,
        "distribution_drift_score": drift_score,
        "false_positive_rate_after": false_positive_rate_after,
        "regression_rate_after": regression_rate_after,
        "detection_rate_after": detection_rate_after,
        "large_ready": large_ready,
    }

    reasons: list[str] = []
    score = 0
    if missing_failure_types_count > 0:
        reasons.append("failure_type_coverage_gap")
        score += 2
    if missing_model_scales_count > 0:
        reasons.append("model_scale_coverage_gap")
        score += 2
    if drift_score > 0.35:
        reasons.append("failure_distribution_drift_high")
        score += 2
    if false_positive_rate_after > 0.08:
        reasons.append("false_positive_rate_high")
        score += 2
    if regression_rate_after > 0.15:
        reasons.append("regression_rate_high")
        score += 3
    if detection_rate_after < 0.8:
        reasons.append("detection_rate_low")
        score += 1
    if not large_ready:
        reasons.append("large_scale_not_ready")
        score += 1

    if score >= 6:
        suggested_profile = "dataset_strict"
        suggested_action = "tighten_thresholds_and_require_large_review"
        confidence = 0.87
    elif score >= 3:
        suggested_profile = "dataset_default"
        suggested_action = "targeted_threshold_patch"
        confidence = 0.76
    else:
        suggested_profile = "dataset_default"
        suggested_action = "keep"
        confidence = 0.64

    threshold_patch = {
        "required_min_failure_type_coverage": 5,
        "max_false_positive_rate": 0.08 if score < 6 else 0.06,
        "max_regression_rate": 0.15 if score < 6 else 0.1,
        "min_detection_rate": 0.8 if score < 6 else 0.85,
        "require_large_model_human_review": (not large_ready) or score >= 6,
    }

    status = "PASS" if suggested_action == "keep" else "NEEDS_REVIEW"
    advice = {
        "suggested_policy_profile": suggested_profile,
        "suggested_action": suggested_action,
        "confidence": round(confidence, 2),
        "reasons": sorted(set(reasons)) if reasons else ["signals_stable"],
        "threshold_patch": threshold_patch,
        "dry_run": True,
    }
    return advice, signals, status


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = payload.get("advice") if isinstance(payload.get("advice"), dict) else {}
    lines = [
        "# GateForge Failure Policy Patch Advisor",
        "",
        f"- status: `{payload.get('status')}`",
        f"- suggested_policy_profile: `{advice.get('suggested_policy_profile')}`",
        f"- suggested_action: `{advice.get('suggested_action')}`",
        f"- confidence: `{advice.get('confidence')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = advice.get("reasons") or []
    if isinstance(reasons, list) and reasons:
        for r in reasons:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Threshold Patch", ""])
    patch = advice.get("threshold_patch") if isinstance(advice.get("threshold_patch"), dict) else {}
    for key in sorted(patch):
        lines.append(f"- {key}: `{patch[key]}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Suggest dataset policy patch based on failure evidence")
    parser.add_argument("--failure-taxonomy-coverage", required=True)
    parser.add_argument("--failure-distribution-benchmark", required=True)
    parser.add_argument("--model-scale-ladder", default=None)
    parser.add_argument("--out", default="artifacts/dataset_failure_policy_patch_advisor/advisor.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    taxonomy = _load_json(args.failure_taxonomy_coverage)
    benchmark = _load_json(args.failure_distribution_benchmark)
    ladder = _load_json(args.model_scale_ladder)

    advice, signals, status = _build_advice(taxonomy, benchmark, ladder)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "advice": advice,
        "signals": signals,
        "sources": {
            "failure_taxonomy_coverage": args.failure_taxonomy_coverage,
            "failure_distribution_benchmark": args.failure_distribution_benchmark,
            "model_scale_ladder": args.model_scale_ladder,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "suggested_action": advice.get("suggested_action"),
                "confidence": advice.get("confidence"),
            }
        )
    )


if __name__ == "__main__":
    main()
