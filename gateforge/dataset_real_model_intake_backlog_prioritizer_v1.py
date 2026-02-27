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


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _extract_ledger_records(ledger: dict) -> list[dict]:
    rows = ledger.get("records") if isinstance(ledger.get("records"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Intake Backlog Prioritizer v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- backlog_item_count: `{payload.get('backlog_item_count')}`",
        f"- p0_count: `{payload.get('p0_count')}`",
        f"- p1_count: `{payload.get('p1_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prioritize actionable backlog from intake rejections and execution gaps")
    parser.add_argument("--real-model-intake-ledger", required=True)
    parser.add_argument("--real-model-license-compliance-summary", required=True)
    parser.add_argument("--real-model-failure-yield-summary", required=True)
    parser.add_argument("--mutation-execution-matrix-summary", required=True)
    parser.add_argument("--backlog-out", default="artifacts/dataset_real_model_intake_backlog_prioritizer_v1/backlog.json")
    parser.add_argument("--out", default="artifacts/dataset_real_model_intake_backlog_prioritizer_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    ledger = _load_json(args.real_model_intake_ledger)
    license_summary = _load_json(args.real_model_license_compliance_summary)
    yield_summary = _load_json(args.real_model_failure_yield_summary)
    matrix_summary = _load_json(args.mutation_execution_matrix_summary)

    reasons: list[str] = []
    if not ledger:
        reasons.append("real_model_intake_ledger_missing")
    if not license_summary:
        reasons.append("real_model_license_compliance_summary_missing")
    if not yield_summary:
        reasons.append("real_model_failure_yield_summary_missing")
    if not matrix_summary:
        reasons.append("mutation_execution_matrix_summary_missing")

    backlog: list[dict] = []
    records = _extract_ledger_records(ledger)
    for row in records:
        if str(row.get("decision") or "") != "REJECT":
            continue
        model_id = str(row.get("model_id") or "unknown")
        for r in row.get("reasons") if isinstance(row.get("reasons"), list) else []:
            reason = str(r)
            priority = "P1"
            if reason in {"license_not_allowed", "source_missing", "local_path_not_found"}:
                priority = "P0"
            backlog.append(
                {
                    "item_id": f"backlog.intake.{model_id}.{reason}",
                    "item_type": "intake_rejection_repair",
                    "model_id": model_id,
                    "reason": reason,
                    "priority": priority,
                }
            )

    matrix_missing = matrix_summary.get("missing_cells") if isinstance(matrix_summary.get("missing_cells"), list) else []
    for i, row in enumerate(matrix_missing, start=1):
        backlog.append(
            {
                "item_id": f"backlog.matrix.{i:03d}",
                "item_type": "execution_gap_fill",
                "model_scale": str(row.get("model_scale") or "unknown"),
                "failure_type": str(row.get("failure_type") or "unknown"),
                "missing_mutations": int(row.get("missing_mutations", 0) or 0),
                "priority": "P0" if str(row.get("model_scale") or "") == "large" else "P1",
            }
        )

    if "disallowed_license_detected" in (license_summary.get("alerts") or []):
        backlog.append(
            {
                "item_id": "backlog.license.policy.001",
                "item_type": "license_policy_remediation",
                "priority": "P0",
                "reason": "disallowed_license_detected",
            }
        )

    if "yield_per_accepted_model_below_threshold" in (yield_summary.get("alerts") or []):
        backlog.append(
            {
                "item_id": "backlog.yield.boost.001",
                "item_type": "yield_boost_campaign",
                "priority": "P0",
                "reason": "yield_per_accepted_model_below_threshold",
            }
        )

    backlog = sorted(backlog, key=lambda x: (str(x.get("priority") or "P9"), str(x.get("item_id") or "")))
    p0 = len([x for x in backlog if x.get("priority") == "P0"])
    p1 = len([x for x in backlog if x.get("priority") == "P1"])

    alerts: list[str] = []
    if p0 > 0:
        alerts.append("p0_backlog_present")
    if len(backlog) == 0:
        alerts.append("no_backlog_items_generated")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    backlog_payload = {
        "schema_version": "real_model_intake_backlog_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "items": backlog,
    }
    _write_json(args.backlog_out, backlog_payload)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "backlog_item_count": len(backlog),
        "p0_count": p0,
        "p1_count": p1,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "backlog_path": args.backlog_out,
        "sources": {
            "real_model_intake_ledger": args.real_model_intake_ledger,
            "real_model_license_compliance_summary": args.real_model_license_compliance_summary,
            "real_model_failure_yield_summary": args.real_model_failure_yield_summary,
            "mutation_execution_matrix_summary": args.mutation_execution_matrix_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "backlog_item_count": len(backlog), "p0_count": p0}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
