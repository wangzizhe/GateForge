from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


RULES: list[tuple[str, str, tuple[str, ...], float]] = [
    ("timeout", "timeout_flag", ("timed out", "timeoutexpired", "timeout"), 0.96),
    (
        "model_check_error",
        "model_check_patterns",
        (
            "model check",
            "check model",
            "type mismatch",
            "structural singular",
            "initialization failed",
            "assertion level",
        ),
        0.86,
    ),
    (
        "simulate_error",
        "simulate_patterns",
        (
            "simulation failed",
            "error in simulation",
            "solver failed",
            "integration failed",
            "nan",
            "diverg",
            "failed to solve",
            "step size too small",
        ),
        0.84,
    ),
    (
        "semantic_regression",
        "semantic_patterns",
        (
            "semantic regression",
            "kpi regression",
            "behavior drift",
            "deviation",
            "performance drop",
        ),
        0.74,
    ),
    (
        "infra_error",
        "infra_patterns",
        (
            "module not found",
            "permission denied",
            "no such file",
            "traceback",
            "connection reset",
        ),
        0.8,
    ),
]


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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _extract_manifest_map(manifest: dict) -> dict[str, str]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue
        expected = _slug(row.get("expected_failure_type"), default="")
        out[mutation_id] = expected
    return out


def _extract_raw_rows(raw: dict) -> list[dict]:
    rows = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_attempts(row: dict) -> list[dict]:
    attempts = row.get("attempts") if isinstance(row.get("attempts"), list) else []
    parsed = [x for x in attempts if isinstance(x, dict)]
    if parsed:
        return parsed
    if any(key in row for key in ("final_return_code", "timed_out", "stdout", "stderr", "exception")):
        return [
            {
                "return_code": row.get("final_return_code"),
                "timed_out": bool(row.get("timed_out", False)),
                "stdout": str(row.get("stdout") or ""),
                "stderr": str(row.get("stderr") or ""),
                "exception": str(row.get("exception") or ""),
            }
        ]
    return []


def _attempt_text(attempt: dict) -> str:
    pieces = [
        str(attempt.get("exception") or ""),
        str(attempt.get("stderr") or ""),
        str(attempt.get("stdout") or ""),
    ]
    return " ".join(pieces).lower()


def _infer_attempt_label(attempt: dict) -> tuple[str, str, float]:
    timed_out = bool(attempt.get("timed_out", False))
    rc = attempt.get("return_code")
    text = _attempt_text(attempt)

    if timed_out:
        return "timeout", "timeout_flag", 0.97

    if "timeoutexpired" in text:
        return "timeout", "timeout_exception", 0.95

    if rc is None and str(attempt.get("exception") or "").strip():
        return "infra_error", "missing_return_code_with_exception", 0.86

    for label, rule_name, patterns, score in RULES:
        for pat in patterns:
            if re.search(re.escape(pat), text):
                boosted = score
                if isinstance(rc, int) and rc != 0:
                    boosted = min(0.97, score + 0.06)
                return label, rule_name, round(boosted, 4)

    if isinstance(rc, int) and rc != 0:
        return "simulate_error", "nonzero_exit_default", 0.7

    if isinstance(rc, int) and rc == 0:
        return "no_failure_signal", "zero_exit_default", 0.6

    return "unknown", "unknown_default", 0.45


def _majority(labels: list[str]) -> tuple[str, float]:
    if not labels:
        return "unknown", 0.0
    c = Counter(labels)
    winner, count = c.most_common(1)[0]
    return str(winner), round(count / len(labels), 4)


def _apply_calibration(labels: list[str], calibrated_label: str) -> list[str]:
    if not labels:
        return [calibrated_label]
    out: list[str] = []
    for label in labels:
        if label in {"unknown", "no_failure_signal"}:
            out.append(calibrated_label)
        else:
            out.append(label)
    return out


def _confidence(
    majority_ratio: float,
    calibrated_label: str,
    expected_label: str,
    note: str,
    attempt_conf_mean: float,
) -> float:
    score = majority_ratio * 0.55 + attempt_conf_mean * 0.45
    if expected_label and calibrated_label == expected_label:
        score += 0.15
    if calibrated_label in {"unknown", "no_failure_signal"}:
        score -= 0.2
    if note.startswith("fallback"):
        score -= 0.07
    return round(_clamp(score), 4)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Label Calibrator v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_observations: `{payload.get('total_observations')}`",
        f"- labeled_observations: `{payload.get('labeled_observations')}`",
        f"- low_confidence_count: `{payload.get('low_confidence_count')}`",
        f"- expected_match_ratio_pct: `{payload.get('expected_match_ratio_pct')}`",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    lines.append("## Alerts")
    lines.append("")
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate raw mutation replay observations into canonical failure labels")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--raw-observations", required=True)
    parser.add_argument("--min-confidence", type=float, default=0.65)
    parser.add_argument("--max-expected-mismatch-ratio-pct", type=float, default=25.0)
    parser.add_argument(
        "--replay-observations-out",
        default="artifacts/dataset_failure_label_calibrator_v1/replay_observations.json",
    )
    parser.add_argument("--out", default="artifacts/dataset_failure_label_calibrator_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    raw = _load_json(args.raw_observations)
    manifest_map = _extract_manifest_map(manifest)
    rows = _extract_raw_rows(raw)

    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not raw:
        reasons.append("raw_observations_missing")
    if manifest and not manifest_map:
        reasons.append("mutation_manifest_empty")
    if raw and not rows:
        reasons.append("raw_observations_empty")

    replay_rows: list[dict] = []
    low_confidence_count = 0
    labeled_count = 0
    expected_count = 0
    expected_match = 0
    expected_mismatch = 0
    auto_override_count = 0

    label_counts: dict[str, int] = {}
    note_counts: dict[str, int] = {}

    for row in rows:
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue
        target_model_id = str(row.get("target_model_id") or "")
        target_scale = _slug(row.get("target_scale"), default="")
        expected_label = manifest_map.get(mutation_id, "")

        attempts = _extract_attempts(row)
        inferred_labels: list[str] = []
        rule_ids: list[str] = []
        conf_values: list[float] = []
        for attempt in attempts:
            label, rule_name, conf = _infer_attempt_label(attempt)
            inferred_labels.append(label)
            rule_ids.append(rule_name)
            conf_values.append(conf)

        majority_label, majority_ratio = _majority(inferred_labels if inferred_labels else ["unknown"])
        calibrated_label = majority_label
        note = "majority_rule"

        if calibrated_label in {"unknown", "no_failure_signal"} and expected_label:
            calibrated_label = expected_label
            note = "fallback_expected_label"
            auto_override_count += 1
        elif expected_label and calibrated_label != expected_label and majority_ratio < 0.67:
            calibrated_label = expected_label
            note = "fallback_expected_label_low_majority"
            auto_override_count += 1

        observed_labels = _apply_calibration(inferred_labels, calibrated_label)
        calibrated_majority, calibrated_ratio = _majority(observed_labels)

        attempt_conf_mean = round(sum(conf_values) / len(conf_values), 4) if conf_values else 0.45
        conf = _confidence(calibrated_ratio, calibrated_majority, expected_label, note, attempt_conf_mean)
        if conf < float(args.min_confidence):
            low_confidence_count += 1

        if calibrated_majority not in {"unknown", "no_failure_signal"}:
            labeled_count += 1
        label_counts[calibrated_majority] = label_counts.get(calibrated_majority, 0) + 1
        note_counts[note] = note_counts.get(note, 0) + 1

        match_expected: bool | None = None
        if expected_label:
            expected_count += 1
            match_expected = calibrated_majority == expected_label
            if match_expected:
                expected_match += 1
            else:
                expected_mismatch += 1

        replay_rows.append(
            {
                "mutation_id": mutation_id,
                "target_model_id": target_model_id,
                "target_scale": target_scale,
                "observed_failure_types": observed_labels,
                "observed_failure_type": calibrated_majority,
                "observed_majority_ratio": calibrated_ratio,
                "observed_failure_confidence": conf,
                "calibration_note": note,
                "calibration_rules": sorted(set(rule_ids)),
                "expected_failure_type": expected_label,
                "label_match_expected": match_expected,
                "attempt_count": len(attempts),
                "source_raw_observations": args.raw_observations,
            }
        )

    expected_match_ratio_pct = round((expected_match / expected_count) * 100.0, 2) if expected_count > 0 else 0.0
    expected_mismatch_ratio_pct = round((expected_mismatch / expected_count) * 100.0, 2) if expected_count > 0 else 0.0
    unknown_count = label_counts.get("unknown", 0) + label_counts.get("no_failure_signal", 0)

    alerts: list[str] = []
    if low_confidence_count > 0:
        alerts.append("low_confidence_labels_present")
    if unknown_count > 0:
        alerts.append("unresolved_labels_present")
    if expected_count > 0 and expected_mismatch_ratio_pct > float(args.max_expected_mismatch_ratio_pct):
        alerts.append("expected_label_mismatch_ratio_high")

    status = "PASS"
    if "mutation_manifest_missing" in reasons or "raw_observations_missing" in reasons:
        status = "FAIL"
    elif alerts or "mutation_manifest_empty" in reasons or "raw_observations_empty" in reasons:
        status = "NEEDS_REVIEW"

    replay_payload = {
        "schema_version": "replay_observations_calibrated_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "observations": replay_rows,
    }
    _write_json(args.replay_observations_out, replay_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_observations": len(replay_rows),
        "labeled_observations": labeled_count,
        "low_confidence_count": low_confidence_count,
        "unknown_or_no_signal_count": unknown_count,
        "expected_labeled_count": expected_count,
        "expected_match_count": expected_match,
        "expected_mismatch_count": expected_mismatch,
        "expected_match_ratio_pct": expected_match_ratio_pct,
        "expected_mismatch_ratio_pct": expected_mismatch_ratio_pct,
        "auto_override_count": auto_override_count,
        "calibrated_replay_observations_path": args.replay_observations_out,
        "label_distribution": label_counts,
        "calibration_note_distribution": note_counts,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "raw_observations": args.raw_observations,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)

    print(
        json.dumps(
            {
                "status": status,
                "total_observations": len(replay_rows),
                "expected_match_ratio_pct": expected_match_ratio_pct,
                "low_confidence_count": low_confidence_count,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
