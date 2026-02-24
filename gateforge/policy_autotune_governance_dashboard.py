from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Policy Auto-Tune Governance Dashboard",
        "",
        f"- bundle_status: `{payload.get('bundle_status')}`",
        f"- latest_effectiveness_decision: `{payload.get('latest_effectiveness_decision')}`",
        f"- improvement_rate: `{payload.get('improvement_rate')}`",
        f"- regression_rate: `{payload.get('regression_rate')}`",
        f"- trend_status: `{payload.get('trend_status')}`",
        f"- trend_alerts_count: `{payload.get('trend_alerts_count')}`",
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
    parser = argparse.ArgumentParser(description="Aggregate policy autotune governance artifacts into dashboard")
    parser.add_argument("--flow-summary", default="artifacts/policy_autotune_governance_demo/flow_summary.json")
    parser.add_argument("--effectiveness", default="artifacts/policy_autotune_governance_demo/effectiveness.json")
    parser.add_argument("--history", default="artifacts/policy_autotune_governance_history_demo/summary.json")
    parser.add_argument("--trend", default="artifacts/policy_autotune_governance_history_demo/trend.json")
    parser.add_argument("--out", default="artifacts/policy_autotune_governance_history_demo/dashboard.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    flow = _load_json(args.flow_summary)
    eff = _load_json(args.effectiveness)
    history = _load_json(args.history)
    trend = _load_json(args.trend)

    trend_payload = trend.get("trend") if isinstance(trend.get("trend"), dict) else {}

    flags = {
        "flow_summary_present": "PASS" if isinstance(flow.get("advisor_profile"), str) else "FAIL",
        "effectiveness_present": "PASS" if eff.get("decision") in {"IMPROVED", "UNCHANGED", "REGRESSED"} else "FAIL",
        "history_present": "PASS" if isinstance(history.get("total_records"), int) else "FAIL",
        "trend_present": "PASS" if trend.get("status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    }
    bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bundle_status": bundle_status,
        "advisor_profile": flow.get("advisor_profile"),
        "latest_effectiveness_decision": eff.get("decision"),
        "delta_apply_score": eff.get("delta_apply_score"),
        "delta_compare_score": eff.get("delta_compare_score"),
        "improvement_rate": history.get("improvement_rate"),
        "regression_rate": history.get("regression_rate"),
        "history_alerts": history.get("alerts", []),
        "trend_status": trend.get("status"),
        "trend_alerts": trend_payload.get("alerts", []),
        "trend_alerts_count": len(trend_payload.get("alerts", []) or []),
        "paths": {
            "flow_summary": args.flow_summary,
            "effectiveness": args.effectiveness,
            "history": args.history,
            "trend": args.trend,
        },
        "result_flags": flags,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"bundle_status": bundle_status, "latest_effectiveness_decision": eff.get("decision")}))
    if bundle_status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
