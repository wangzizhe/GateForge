from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_diagnostic_quality_v0 import evaluate_diagnostic_quality_v0


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


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    thresholds = payload.get("thresholds") if isinstance(payload.get("thresholds"), dict) else {}
    lines = [
        "# Agent Modelica L3 Diagnostic Gate v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- gate_result: `{payload.get('gate_result')}`",
        f"- parse_coverage_pct: `{payload.get('parse_coverage_pct')}`",
        f"- canonical_type_match_rate_pct: `{payload.get('canonical_type_match_rate_pct')}`",
        f"- stage_match_rate_pct: `{payload.get('stage_match_rate_pct')}`",
        f"- low_confidence_rate_pct: `{payload.get('low_confidence_rate_pct')}`",
        "",
        "## Thresholds",
        "",
        f"- min_parse_coverage_pct: `{thresholds.get('min_parse_coverage_pct')}`",
        f"- min_canonical_type_match_rate_pct: `{thresholds.get('min_canonical_type_match_rate_pct')}`",
        f"- min_stage_match_rate_pct: `{thresholds.get('min_stage_match_rate_pct')}`",
        f"- max_low_confidence_rate_pct: `{thresholds.get('max_low_confidence_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def evaluate_l3_diagnostic_gate_v0(
    quality_summary: dict,
    *,
    min_parse_coverage_pct: float = 95.0,
    min_canonical_type_match_rate_pct: float = 70.0,
    min_stage_match_rate_pct: float = 70.0,
    max_low_confidence_rate_pct: float = 30.0,
) -> dict:
    parse_coverage = _to_float(quality_summary.get("parse_coverage_pct"), 0.0)
    type_match = _to_float(quality_summary.get("canonical_type_match_rate_pct"), _to_float(quality_summary.get("type_match_rate_pct"), 0.0))
    stage_match = _to_float(quality_summary.get("stage_match_rate_pct"), 0.0)
    low_conf_rate = _to_float(quality_summary.get("low_confidence_rate_pct"), 0.0)
    total_attempts = int(quality_summary.get("total_attempts") or 0)

    reasons: list[str] = []
    gate_result = "PASS"

    if total_attempts <= 0:
        gate_result = "FAIL"
        reasons.append("diagnostic_attempts_missing")
    if parse_coverage < float(min_parse_coverage_pct):
        gate_result = "FAIL"
        reasons.append("parse_coverage_below_threshold")
    if type_match < float(min_canonical_type_match_rate_pct):
        gate_result = "FAIL"
        reasons.append("canonical_type_match_rate_below_threshold")
    if stage_match < float(min_stage_match_rate_pct):
        gate_result = "FAIL"
        reasons.append("stage_match_rate_below_threshold")

    if gate_result == "PASS" and low_conf_rate > float(max_low_confidence_rate_pct):
        gate_result = "NEEDS_REVIEW"
        reasons.append("low_confidence_rate_above_threshold")

    status = "PASS"
    if gate_result == "FAIL":
        status = "FAIL"
    elif gate_result == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"

    return {
        "schema_version": "agent_modelica_l3_diagnostic_gate_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gate_result": gate_result,
        "parse_coverage_pct": parse_coverage,
        "canonical_type_match_rate_pct": type_match,
        # Backward-compatible alias.
        "type_match_rate_pct": type_match,
        "stage_match_rate_pct": stage_match,
        "low_confidence_rate_pct": low_conf_rate,
        "total_attempts": total_attempts,
        "reasons": sorted(set(reasons)),
        "thresholds": {
            "min_parse_coverage_pct": float(min_parse_coverage_pct),
            "min_canonical_type_match_rate_pct": float(min_canonical_type_match_rate_pct),
            "min_stage_match_rate_pct": float(min_stage_match_rate_pct),
            "max_low_confidence_rate_pct": float(max_low_confidence_rate_pct),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="L3 diagnostic gate for release/CI")
    parser.add_argument("--run-results", default="")
    parser.add_argument("--taskset", default="")
    parser.add_argument("--diagnostic-quality-summary", default="")
    parser.add_argument("--low-confidence-threshold", type=float, default=0.65)
    parser.add_argument("--min-parse-coverage-pct", type=float, default=95.0)
    parser.add_argument("--min-canonical-type-match-rate-pct", type=float, default=70.0)
    parser.add_argument("--min-stage-match-rate-pct", type=float, default=70.0)
    parser.add_argument("--max-low-confidence-rate-pct", type=float, default=30.0)
    parser.add_argument("--out", default="artifacts/agent_modelica_l3_diagnostic_gate_v0/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    quality_summary = _load_json(args.diagnostic_quality_summary)
    if not quality_summary:
        run_results = _load_json(args.run_results)
        taskset = _load_json(args.taskset)
        quality_summary = evaluate_diagnostic_quality_v0(
            run_results_payload=run_results,
            taskset_payload=taskset,
            low_confidence_threshold=float(args.low_confidence_threshold),
        )

    summary = evaluate_l3_diagnostic_gate_v0(
        quality_summary,
        min_parse_coverage_pct=float(args.min_parse_coverage_pct),
        min_canonical_type_match_rate_pct=float(args.min_canonical_type_match_rate_pct),
        min_stage_match_rate_pct=float(args.min_stage_match_rate_pct),
        max_low_confidence_rate_pct=float(args.max_low_confidence_rate_pct),
    )
    summary["sources"] = {
        "run_results": str(args.run_results or ""),
        "taskset": str(args.taskset or ""),
        "diagnostic_quality_summary": str(args.diagnostic_quality_summary or ""),
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "gate_result": summary.get("gate_result"),
                "parse_coverage_pct": summary.get("parse_coverage_pct"),
                "canonical_type_match_rate_pct": summary.get("canonical_type_match_rate_pct"),
                "stage_match_rate_pct": summary.get("stage_match_rate_pct"),
                "low_confidence_rate_pct": summary.get("low_confidence_rate_pct"),
            }
        )
    )
    if str(summary.get("status") or "") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
