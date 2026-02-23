from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Medium Benchmark Dashboard",
        "",
        f"- bundle_status: `{payload.get('bundle_status')}`",
        f"- pack_id: `{payload.get('pack_id')}`",
        f"- pass_rate: `{payload.get('pass_rate')}`",
        f"- mismatch_case_count: `{payload.get('mismatch_case_count')}`",
        f"- latest_pass_rate: `{payload.get('latest_pass_rate')}`",
        f"- avg_pass_rate: `{payload.get('avg_pass_rate')}`",
        f"- trend_delta_pass_rate: `{payload.get('trend_delta_pass_rate')}`",
        f"- advisor_decision: `{payload.get('advisor_decision')}`",
        f"- advisor_profile: `{payload.get('advisor_profile')}`",
        "",
        "## Result Flags",
        "",
    ]
    flags = payload.get("result_flags", {})
    if isinstance(flags, dict):
        for k in sorted(flags):
            lines.append(f"- {k}: `{flags[k]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate medium benchmark artifacts into a dashboard summary")
    parser.add_argument("--summary", default="artifacts/benchmark_medium_v1/summary.json", help="medium benchmark summary")
    parser.add_argument("--analysis", default="artifacts/benchmark_medium_v1/analysis.json", help="medium benchmark analysis")
    parser.add_argument("--history", default="artifacts/benchmark_medium_v1/history_summary.json", help="medium benchmark history")
    parser.add_argument("--trend", default="artifacts/benchmark_medium_v1/history_trend.json", help="medium benchmark trend")
    parser.add_argument("--advisor", default="artifacts/benchmark_medium_v1/advisor.json", help="medium benchmark advisor")
    parser.add_argument("--out", default="artifacts/benchmark_medium_v1/dashboard.json", help="dashboard JSON output")
    parser.add_argument("--report-out", default=None, help="dashboard markdown output")
    args = parser.parse_args()

    summary = _load_json(args.summary)
    analysis = _load_json(args.analysis)
    history = _load_json(args.history)
    trend_payload = _load_json(args.trend)
    advisor = _load_json(args.advisor)
    trend = trend_payload.get("trend", {}) if isinstance(trend_payload.get("trend"), dict) else {}
    advice = advisor.get("advice", {}) if isinstance(advisor.get("advice"), dict) else {}

    flags = {
        "summary_present": "PASS" if isinstance(summary.get("pack_id"), str) else "FAIL",
        "analysis_present": "PASS" if isinstance(analysis.get("mismatch_case_count"), int) else "FAIL",
        "history_present": "PASS" if isinstance(history.get("total_records"), int) else "FAIL",
        "trend_present": "PASS" if isinstance(trend.get("delta_pass_rate"), (float, int)) else "FAIL",
        "advisor_present": "PASS" if isinstance(advice.get("decision"), str) else "FAIL",
    }
    bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_status": bundle_status,
        "pack_id": summary.get("pack_id"),
        "pass_rate": summary.get("pass_rate"),
        "mismatch_case_count": summary.get("mismatch_case_count"),
        "latest_pass_rate": history.get("latest_pass_rate"),
        "avg_pass_rate": history.get("avg_pass_rate"),
        "history_total_records": history.get("total_records"),
        "trend_delta_pass_rate": trend.get("delta_pass_rate"),
        "trend_delta_mismatch_case_total": trend.get("delta_mismatch_case_total"),
        "advisor_decision": advice.get("decision"),
        "advisor_profile": advice.get("suggested_profile"),
        "advisor_reasons_count": len(advice.get("reasons") or []),
        "paths": {
            "summary": args.summary,
            "analysis": args.analysis,
            "history": args.history,
            "trend": args.trend,
            "advisor": args.advisor,
        },
        "result_flags": flags,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"bundle_status": bundle_status, "pack_id": payload.get("pack_id")}))
    if bundle_status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
