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


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _safe_delta(after: float, before: float, ndigits: int = 4) -> float:
    return round(after - before, ndigits)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    lines = [
        "# GateForge Policy Patch Replay Evaluator",
        "",
        f"- status: `{payload.get('status')}`",
        f"- recommendation: `{payload.get('recommendation')}`",
        f"- evaluation_score: `{payload.get('evaluation_score')}`",
        f"- delta_detection_rate: `{delta.get('detection_rate')}`",
        f"- delta_false_positive_rate: `{delta.get('false_positive_rate')}`",
        f"- delta_regression_rate: `{delta.get('regression_rate')}`",
        f"- delta_review_load: `{delta.get('review_load')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons")
    if isinstance(reasons, list) and reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate policy patch by replaying before/after benchmark signals")
    parser.add_argument("--before-benchmark", required=True)
    parser.add_argument("--after-benchmark", required=True)
    parser.add_argument("--before-snapshot", default=None)
    parser.add_argument("--after-snapshot", default=None)
    parser.add_argument("--patch-advisor", default=None)
    parser.add_argument("--patch-apply-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_policy_patch_replay_evaluator/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    before_b = _load_json(args.before_benchmark)
    after_b = _load_json(args.after_benchmark)
    before_s = _load_json(args.before_snapshot)
    after_s = _load_json(args.after_snapshot)
    advisor = _load_json(args.patch_advisor)
    apply_summary = _load_json(args.patch_apply_summary)

    before_detection = _to_float(before_b.get("detection_rate_after", before_b.get("detection_rate", 0.0)))
    after_detection = _to_float(after_b.get("detection_rate_after", after_b.get("detection_rate", 0.0)))
    before_fp = _to_float(before_b.get("false_positive_rate_after", before_b.get("false_positive_rate", 0.0)))
    after_fp = _to_float(after_b.get("false_positive_rate_after", after_b.get("false_positive_rate", 0.0)))
    before_reg = _to_float(before_b.get("regression_rate_after", before_b.get("regression_rate", 0.0)))
    after_reg = _to_float(after_b.get("regression_rate_after", after_b.get("regression_rate", 0.0)))

    before_review_load = len(before_s.get("risks") or []) if isinstance(before_s.get("risks"), list) else 0
    after_review_load = len(after_s.get("risks") or []) if isinstance(after_s.get("risks"), list) else 0

    delta = {
        "detection_rate": _safe_delta(after_detection, before_detection),
        "false_positive_rate": _safe_delta(after_fp, before_fp),
        "regression_rate": _safe_delta(after_reg, before_reg),
        "review_load": _to_int(after_review_load - before_review_load),
    }

    reasons: list[str] = []
    score = 0

    if delta["detection_rate"] >= 0.02:
        score += 3
    elif delta["detection_rate"] < 0:
        score -= 3
        reasons.append("detection_rate_regressed")

    if delta["false_positive_rate"] <= -0.01:
        score += 2
    elif delta["false_positive_rate"] > 0.02:
        score -= 3
        reasons.append("false_positive_rate_worsened")

    if delta["regression_rate"] <= -0.02:
        score += 3
    elif delta["regression_rate"] > 0.02:
        score -= 4
        reasons.append("regression_rate_worsened")

    if delta["review_load"] < 0:
        score += 1
    elif delta["review_load"] > 1:
        score -= 1
        reasons.append("review_load_increased")

    apply_status = str(apply_summary.get("final_status") or "")
    if apply_status == "FAIL":
        score -= 3
        reasons.append("patch_apply_failed")
    elif apply_status == "PASS":
        score += 1

    suggested = str((advisor.get("advice") or {}).get("suggested_action") or "")
    if suggested == "keep" and score < 0:
        reasons.append("advisor_keep_mismatch_with_replay")

    if score >= 4:
        status = "PASS"
        recommendation = "ADOPT_PATCH"
    elif score >= 0:
        status = "NEEDS_REVIEW"
        recommendation = "LIMITED_ROLLOUT"
    else:
        status = "NEEDS_REVIEW"
        recommendation = "ROLLBACK_OR_REVISE"

    if not reasons and status != "PASS":
        reasons.append("mixed_signals_manual_review")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "recommendation": recommendation,
        "evaluation_score": score,
        "delta": delta,
        "before": {
            "detection_rate": before_detection,
            "false_positive_rate": before_fp,
            "regression_rate": before_reg,
            "review_load": before_review_load,
        },
        "after": {
            "detection_rate": after_detection,
            "false_positive_rate": after_fp,
            "regression_rate": after_reg,
            "review_load": after_review_load,
        },
        "reasons": sorted(set(reasons)),
        "sources": {
            "before_benchmark": args.before_benchmark,
            "after_benchmark": args.after_benchmark,
            "before_snapshot": args.before_snapshot,
            "after_snapshot": args.after_snapshot,
            "patch_advisor": args.patch_advisor,
            "patch_apply_summary": args.patch_apply_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "recommendation": recommendation, "evaluation_score": score}))


if __name__ == "__main__":
    main()
