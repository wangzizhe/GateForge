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
        return int(round(v))
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    steps = payload.get("repro_steps") if isinstance(payload.get("repro_steps"), list) else []
    lines = [
        "# GateForge Moat Repro Runbook v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- readiness: `{payload.get('readiness')}`",
        "",
        "## Expected Signals",
        "",
    ]
    for key, value in (payload.get("expected_signals") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Repro Steps", ""])
    for i, step in enumerate(steps, start=1):
        lines.append(f"{i}. `{step}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build concise externally reproducible moat evidence runbook")
    parser.add_argument("--moat-scorecard-baseline-summary", required=True)
    parser.add_argument("--model-asset-inventory-report-summary", required=True)
    parser.add_argument("--failure-distribution-baseline-freeze-summary", required=True)
    parser.add_argument("--gateforge-vs-plain-ci-benchmark-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_moat_repro_runbook_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    scorecard = _load_json(args.moat_scorecard_baseline_summary)
    inventory = _load_json(args.model_asset_inventory_report_summary)
    freeze = _load_json(args.failure_distribution_baseline_freeze_summary)
    compare = _load_json(args.gateforge_vs_plain_ci_benchmark_summary)

    reasons: list[str] = []
    if not scorecard:
        reasons.append("moat_scorecard_baseline_summary_missing")
    if not inventory:
        reasons.append("model_asset_inventory_report_summary_missing")
    if not freeze:
        reasons.append("failure_distribution_baseline_freeze_summary_missing")
    if not compare:
        reasons.append("gateforge_vs_plain_ci_benchmark_summary_missing")

    indicators = scorecard.get("indicators") if isinstance(scorecard.get("indicators"), dict) else {}
    expected_signals = {
        "real_model_count": _to_int(indicators.get("real_model_count", inventory.get("total_models", 0))),
        "reproducible_mutation_count": _to_int(indicators.get("reproducible_mutation_count", 0)),
        "failure_distribution_stability_score": _to_float(
            (freeze.get("locked_metrics") or {}).get("failure_distribution_stability_score", indicators.get("failure_distribution_stability_score", 0.0))
        ),
        "gateforge_vs_plain_ci_advantage_score": _to_int(compare.get("advantage_score", 0)),
        "baseline_id": scorecard.get("baseline_id"),
        "freeze_id": freeze.get("freeze_id"),
    }

    repro_steps = [
        "bash scripts/demo_dataset_model_asset_inventory_report_v1.sh",
        "bash scripts/demo_dataset_moat_scorecard_baseline_v1.sh",
        "bash scripts/demo_dataset_failure_distribution_baseline_freeze_v1.sh",
        "bash scripts/demo_dataset_gateforge_vs_plain_ci_benchmark_v1.sh",
    ]

    readiness = "READY"
    status = "PASS"
    if reasons:
        readiness = "BLOCKED"
        status = "FAIL"
    elif (
        expected_signals["real_model_count"] < 1
        or expected_signals["reproducible_mutation_count"] < 1
        or expected_signals["gateforge_vs_plain_ci_advantage_score"] <= 0
    ):
        readiness = "NEEDS_EVIDENCE"
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "readiness": readiness,
        "expected_signals": expected_signals,
        "repro_steps": repro_steps,
        "sources": {
            "moat_scorecard_baseline_summary": args.moat_scorecard_baseline_summary,
            "model_asset_inventory_report_summary": args.model_asset_inventory_report_summary,
            "failure_distribution_baseline_freeze_summary": args.failure_distribution_baseline_freeze_summary,
            "gateforge_vs_plain_ci_benchmark_summary": args.gateforge_vs_plain_ci_benchmark_summary,
        },
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "readiness": readiness}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
