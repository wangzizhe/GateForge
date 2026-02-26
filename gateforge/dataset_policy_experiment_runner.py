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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _build_experiments(replay: dict, guard: dict, advisor: dict, moat: dict) -> list[dict]:
    replay_score = _to_int(replay.get("evaluation_score", 0))
    replay_delta = replay.get("delta") if isinstance(replay.get("delta"), dict) else {}
    delta_detection = _to_float(replay_delta.get("detection_rate", 0.0))
    delta_regression = _to_float(replay_delta.get("regression_rate", 0.0))
    delta_fp = _to_float(replay_delta.get("false_positive_rate", 0.0))

    guard_conf = str(guard.get("confidence_level") or "medium")
    guard_status = str(guard.get("status") or "NEEDS_REVIEW")
    confidence_bonus = {"high": 10, "medium": 4, "low": -8}.get(guard_conf, 0)
    if guard_status == "FAIL":
        confidence_bonus -= 8

    moat_score = _to_float(((moat.get("metrics") or {}).get("moat_score") if isinstance(moat.get("metrics"), dict) else 0.0))
    moat_bonus = 6 if moat_score >= 70 else (2 if moat_score >= 55 else -4)

    advisor_action = str(((advisor.get("advice") or {}).get("suggested_action") if isinstance(advisor.get("advice"), dict) else "") or "")
    advisor_bonus = 5 if advisor_action in {"tighten", "keep"} else 1

    base = 50 + replay_score * 3 + confidence_bonus + moat_bonus + advisor_bonus

    variants = [
        {
            "experiment_id": "policy_exp.conservative",
            "profile": "conservative",
            "policy_intensity": "low",
            "rollout": "10_percent_shadow",
            "safety_buffer": "strict",
            "score_bias": 6,
            "risk_penalty": 3,
        },
        {
            "experiment_id": "policy_exp.balanced",
            "profile": "balanced",
            "policy_intensity": "medium",
            "rollout": "30_percent_canary",
            "safety_buffer": "standard",
            "score_bias": 10,
            "risk_penalty": 8,
        },
        {
            "experiment_id": "policy_exp.aggressive",
            "profile": "aggressive",
            "policy_intensity": "high",
            "rollout": "60_percent_canary",
            "safety_buffer": "relaxed",
            "score_bias": 12,
            "risk_penalty": 15,
        },
    ]

    rows: list[dict] = []
    for item in variants:
        expected_detection_delta = round(delta_detection + (0.01 if item["profile"] != "conservative" else 0.005), 4)
        expected_regression_delta = round(delta_regression + (0.01 if item["profile"] == "aggressive" else 0.0), 4)
        expected_fp_delta = round(delta_fp + (0.005 if item["profile"] == "aggressive" else 0.0), 4)

        risk_score = _clamp(
            35
            + item["risk_penalty"]
            + (10 if expected_regression_delta > 0.02 else 0)
            + (7 if expected_fp_delta > 0.015 else 0)
            - (8 if guard_conf == "high" else 0)
        )

        experiment_score = _clamp(base + item["score_bias"] - (risk_score * 0.45))
        rows.append(
            {
                "experiment_id": item["experiment_id"],
                "profile": item["profile"],
                "policy_intensity": item["policy_intensity"],
                "rollout": item["rollout"],
                "safety_buffer": item["safety_buffer"],
                "expected_delta": {
                    "detection_rate": expected_detection_delta,
                    "false_positive_rate": expected_fp_delta,
                    "regression_rate": expected_regression_delta,
                },
                "risk_score": round(risk_score, 2),
                "experiment_score": round(experiment_score, 2),
            }
        )

    rows.sort(key=lambda x: (-_to_float(x.get("experiment_score", 0.0)), _to_float(x.get("risk_score", 100.0))))
    return rows


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Policy Experiment Runner",
        "",
        f"- status: `{payload.get('status')}`",
        f"- recommendation: `{payload.get('recommendation')}`",
        f"- recommended_experiment_id: `{payload.get('recommended_experiment_id')}`",
        f"- confidence_level: `{payload.get('confidence_level')}`",
        "",
        "## Experiment Ranking",
        "",
    ]

    experiments = payload.get("experiments") if isinstance(payload.get("experiments"), list) else []
    if experiments:
        for row in experiments:
            lines.append(
                f"- `{row.get('experiment_id')}` profile=`{row.get('profile')}` score=`{row.get('experiment_score')}` risk=`{row.get('risk_score')}`"
            )
    else:
        lines.append("- `none`")

    lines.extend(["", "## Reasons", ""])
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")

    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate policy experiment matrix from replay and governance signals")
    parser.add_argument("--policy-patch-replay-evaluator", required=True)
    parser.add_argument("--replay-quality-guard", default=None)
    parser.add_argument("--failure-policy-patch-advisor", default=None)
    parser.add_argument("--moat-trend-snapshot", default=None)
    parser.add_argument("--out", default="artifacts/dataset_policy_experiment_runner/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    replay = _load_json(args.policy_patch_replay_evaluator)
    guard = _load_json(args.replay_quality_guard)
    advisor = _load_json(args.failure_policy_patch_advisor)
    moat = _load_json(args.moat_trend_snapshot)

    reasons: list[str] = []
    if not replay:
        reasons.append("replay_evaluator_missing")

    experiments = _build_experiments(replay, guard, advisor, moat) if replay else []
    recommended = experiments[0] if experiments else {}

    guard_status = str(guard.get("status") or "NEEDS_REVIEW")
    confidence_level = str(guard.get("confidence_level") or "medium")

    status = "PASS"
    recommendation = "RUN_RECOMMENDED"

    if not replay:
        status = "FAIL"
        recommendation = "BLOCKED"
    else:
        top_score = _to_float(recommended.get("experiment_score", 0.0))
        top_risk = _to_float(recommended.get("risk_score", 100.0))
        if guard_status == "FAIL":
            reasons.append("replay_quality_guard_failed")
            status = "NEEDS_REVIEW"
            recommendation = "RUN_CONSERVATIVE_ONLY"
        elif top_score < 45:
            reasons.append("experiment_scores_too_low")
            status = "NEEDS_REVIEW"
            recommendation = "REVISE_PATCH_FIRST"
        elif top_risk > 62:
            reasons.append("recommended_risk_high")
            status = "NEEDS_REVIEW"
            recommendation = "LIMITED_ROLLOUT"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "recommendation": recommendation,
        "recommended_experiment_id": recommended.get("experiment_id"),
        "confidence_level": confidence_level,
        "experiments": experiments,
        "reasons": sorted(set(reasons)),
        "sources": {
            "policy_patch_replay_evaluator": args.policy_patch_replay_evaluator,
            "replay_quality_guard": args.replay_quality_guard,
            "failure_policy_patch_advisor": args.failure_policy_patch_advisor,
            "moat_trend_snapshot": args.moat_trend_snapshot,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "recommendation": recommendation, "recommended_experiment_id": payload["recommended_experiment_id"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
