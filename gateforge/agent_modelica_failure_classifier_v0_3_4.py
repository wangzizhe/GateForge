from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_failure_classifier_v0_3_4"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_failure_classifier_v0_3_4"
FAILURE_BUCKETS = (
    "infra_interruption",
    "budget_stop",
    "verifier_reject",
    "patch_invalid",
    "search_oscillation",
    "unresolved_search",
)
PLANNER_PATHS = {"llm_planner_assisted", "rule_then_llm"}
INFRA_HINTS = (
    "not logged in",
    "/login",
    "session",
    "quota",
    "limit",
    "rate limit",
    "connection reset",
    "broken pipe",
    "timed out waiting for mcp",
    "transport",
    "network",
    "mcp",
)
BUDGET_HINTS = (
    "budget_exhausted",
    "budget exhausted",
    "time budget",
    "round budget",
    "max rounds",
    "timeout",
    "timed out",
)
OSCILLATION_HINTS = (
    "oscillation",
    "oscillating",
    "retry loop",
    "looping",
    "repeatedly",
    "same failure repeated",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _rows(payload: dict) -> list[dict]:
    for key in ("results", "records", "tasks", "cases"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _text_blob(row: dict) -> str:
    parts = (
        _norm(row.get("infra_failure_reason")),
        _norm(row.get("output_text")),
        _norm(row.get("error")),
        _norm(row.get("executor_status")),
        _norm(row.get("task_status")),
        _norm(row.get("dominant_stage_subtype")),
    )
    return " | ".join(part for part in parts if part).lower()


def _match_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _resolution_path(row: dict) -> str:
    path = _norm(row.get("resolution_path"))
    if path:
        return path
    attribution = row.get("resolution_attribution")
    if isinstance(attribution, dict):
        return _norm(attribution.get("resolution_path"))
    return ""


def classify_failure_row(row: dict) -> dict:
    success = bool(row.get("success"))
    text = _text_blob(row)
    resolution_path = _resolution_path(row)
    planner_invoked = bool(row.get("planner_invoked"))
    planner_decisive = bool(row.get("planner_decisive"))
    rounds_used = int(row.get("rounds_used") or row.get("agent_rounds") or 0)
    omc_tool_call_count = int(row.get("omc_tool_call_count") or 0)
    check_model_pass = row.get("check_model_pass")
    simulate_pass = row.get("simulate_pass")
    infra_failure = bool(row.get("infra_failure"))
    budget_exhausted = bool(row.get("budget_exhausted"))

    if success:
        return {
            "failure_bucket": "success",
            "bucket_confidence": 1.0,
            "bucket_reasons": ["row_marked_success"],
        }

    if infra_failure or _match_any(text, INFRA_HINTS):
        reasons = ["infra_failure_flag"] if infra_failure else []
        if _match_any(text, INFRA_HINTS):
            reasons.append("infra_hint_text")
        return {
            "failure_bucket": "infra_interruption",
            "bucket_confidence": 0.95 if infra_failure else 0.85,
            "bucket_reasons": reasons,
        }

    if budget_exhausted or _match_any(text, BUDGET_HINTS):
        reasons = ["budget_exhausted_flag"] if budget_exhausted else []
        if _match_any(text, BUDGET_HINTS):
            reasons.append("budget_hint_text")
        return {
            "failure_bucket": "budget_stop",
            "bucket_confidence": 0.95 if budget_exhausted else 0.8,
            "bucket_reasons": reasons,
        }

    if _match_any(text, OSCILLATION_HINTS):
        return {
            "failure_bucket": "search_oscillation",
            "bucket_confidence": 0.9,
            "bucket_reasons": ["oscillation_hint_text"],
        }

    if check_model_pass is True and simulate_pass is False:
        return {
            "failure_bucket": "verifier_reject",
            "bucket_confidence": 0.9,
            "bucket_reasons": ["check_model_pass_true", "simulate_pass_false"],
        }

    if any(
        (
            resolution_path in PLANNER_PATHS,
            planner_invoked,
            planner_decisive,
            rounds_used > 0,
            omc_tool_call_count > 0,
        )
    ):
        reasons: list[str] = []
        if resolution_path in PLANNER_PATHS:
            reasons.append(f"resolution_path:{resolution_path}")
        if planner_invoked:
            reasons.append("planner_invoked_true")
        if planner_decisive:
            reasons.append("planner_decisive_true")
        if rounds_used > 0:
            reasons.append("agent_rounds_present")
        if omc_tool_call_count > 0:
            reasons.append("omc_tool_calls_present")
        if check_model_pass is False:
            reasons.append("check_model_pass_false")
        return {
            "failure_bucket": "patch_invalid" if check_model_pass is False or resolution_path in PLANNER_PATHS else "unresolved_search",
            "bucket_confidence": 0.8 if check_model_pass is False or resolution_path in PLANNER_PATHS else 0.7,
            "bucket_reasons": reasons,
        }

    return {
        "failure_bucket": "unresolved_search",
        "bucket_confidence": 0.6,
        "bucket_reasons": ["default_unresolved_fallback"],
    }


def build_failure_classifier(
    *,
    input_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(input_path)
    input_rows = _rows(payload)
    classified_rows: list[dict] = []
    failure_counts = {bucket: 0 for bucket in FAILURE_BUCKETS}
    success_count = 0
    planner_invoked_failures = 0
    attribution_missing_count = 0
    structured_terminal_failures = 0

    for row in input_rows:
        item_id = _item_id(row)
        classification = classify_failure_row(row)
        bucket = _norm(classification.get("failure_bucket"))
        success = bucket == "success"
        planner_invoked = bool(row.get("planner_invoked"))
        resolution_path = _resolution_path(row)
        attribution_missing = not any(
            (
                resolution_path,
                planner_invoked,
                int(row.get("rounds_used") or row.get("agent_rounds") or 0) > 0,
                int(row.get("omc_tool_call_count") or 0) > 0,
            )
        )

        if success:
            success_count += 1
        else:
            failure_counts[bucket] = int(failure_counts.get(bucket) or 0) + 1
            if planner_invoked:
                planner_invoked_failures += 1
            if attribution_missing:
                attribution_missing_count += 1
            if bucket in {"verifier_reject", "patch_invalid"}:
                structured_terminal_failures += 1

        classified_rows.append(
            {
                **row,
                "item_id": item_id,
                "resolution_path": resolution_path,
                "failure_bucket": bucket,
                "failure_bucket_confidence": float(classification.get("bucket_confidence") or 0.0),
                "failure_bucket_reasons": list(classification.get("bucket_reasons") or []),
                "attribution_missing": bool(attribution_missing),
            }
        )

    failure_total = sum(failure_counts.values())
    payload_out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if input_rows else "FAIL",
        "input_path": str(Path(input_path).resolve()) if Path(input_path).exists() else str(input_path),
        "metrics": {
            "row_count": len(input_rows),
            "success_count": success_count,
            "failure_count": failure_total,
            "failure_bucket_counts": failure_counts,
            "planner_invoked_failure_count": planner_invoked_failures,
            "planner_invoked_failure_rate_pct": round((planner_invoked_failures / failure_total) * 100.0, 2) if failure_total else 0.0,
            "attribution_missing_count": attribution_missing_count,
            "attribution_missing_rate_pct": round((attribution_missing_count / failure_total) * 100.0, 2) if failure_total else 0.0,
            "structured_terminal_failure_count": structured_terminal_failures,
            "structured_terminal_failure_rate_pct": round((structured_terminal_failures / failure_total) * 100.0, 2) if failure_total else 0.0,
        },
        "rows": classified_rows,
        "notes": [
            "Dedicated failure-classifier layer for v0.3.4; keep diagnostic_ir and resolution_attribution responsibilities separate.",
            "Bucket heuristics are intentionally conservative and prefer unresolved_search when stronger terminal evidence is absent.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload_out)
    _write_text(out_root / "summary.md", render_markdown(payload_out))
    return payload_out


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lines = [
        "# Agent Modelica Failure Classifier v0.3.4",
        "",
        f"- status: `{payload.get('status')}`",
        f"- row_count: `{metrics.get('row_count')}`",
        f"- failure_count: `{metrics.get('failure_count')}`",
        f"- planner_invoked_failure_rate_pct: `{metrics.get('planner_invoked_failure_rate_pct')}`",
        f"- attribution_missing_rate_pct: `{metrics.get('attribution_missing_rate_pct')}`",
        f"- structured_terminal_failure_rate_pct: `{metrics.get('structured_terminal_failure_rate_pct')}`",
        f"- failure_bucket_counts: `{json.dumps(metrics.get('failure_bucket_counts') or {}, sort_keys=True)}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify GateForge or external-agent failures into dedicated v0.3.4 buckets.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_failure_classifier(input_path=str(args.input), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "failure_count": payload.get("metrics", {}).get("failure_count")}))


if __name__ == "__main__":
    main()
