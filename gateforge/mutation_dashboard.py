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
        "# GateForge Mutation Dashboard",
        "",
        f"- bundle_status: `{payload.get('bundle_status')}`",
        f"- latest_pack_id: `{payload.get('latest_pack_id')}`",
        f"- latest_match_rate: `{payload.get('latest_match_rate')}`",
        f"- latest_gate_pass_rate: `{payload.get('latest_gate_pass_rate')}`",
        f"- compare_decision: `{payload.get('compare_decision')}`",
        "",
        "## Result Flags",
        "",
    ]
    flags = payload.get("result_flags", {})
    if isinstance(flags, dict):
        for key in sorted(flags):
            lines.append(f"- {key}: `{flags[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate mutation metrics/history/compare into dashboard summary")
    parser.add_argument("--metrics", required=True, help="Mutation metrics JSON")
    parser.add_argument("--history", required=True, help="Mutation history summary JSON")
    parser.add_argument("--trend", required=True, help="Mutation history trend JSON")
    parser.add_argument("--compare", required=True, help="Mutation pack compare summary JSON")
    parser.add_argument("--out", default="artifacts/mutation_dashboard/summary.json", help="Dashboard JSON output")
    parser.add_argument("--report-out", default=None, help="Dashboard markdown output")
    args = parser.parse_args()

    metrics = _load_json(args.metrics)
    history = _load_json(args.history)
    trend = _load_json(args.trend)
    compare = _load_json(args.compare)
    trend_payload = trend.get("trend", {}) if isinstance(trend.get("trend"), dict) else {}

    flags = {
        "metrics_has_match_rate": "PASS" if isinstance(metrics.get("expected_vs_actual_match_rate"), float) else "FAIL",
        "history_has_records": "PASS" if int(history.get("total_records", 0) or 0) >= 1 else "FAIL",
        "trend_status_present": "PASS" if trend.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
        "compare_decision_present": "PASS" if compare.get("decision") in {"PASS", "FAIL"} else "FAIL",
    }
    bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_status": bundle_status,
        "latest_pack_id": metrics.get("pack_id"),
        "latest_pack_version": metrics.get("pack_version"),
        "latest_match_rate": metrics.get("expected_vs_actual_match_rate"),
        "latest_gate_pass_rate": metrics.get("gate_pass_rate"),
        "history_total_records": history.get("total_records"),
        "trend_status": trend.get("status"),
        "trend_delta_match_rate": trend_payload.get("delta_match_rate"),
        "trend_delta_gate_pass_rate": trend_payload.get("delta_gate_pass_rate"),
        "compare_decision": compare.get("decision"),
        "compare_delta_match_rate": compare.get("delta_match_rate"),
        "result_flags": flags,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"bundle_status": bundle_status, "latest_pack_id": payload.get("latest_pack_id")}))
    if bundle_status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
