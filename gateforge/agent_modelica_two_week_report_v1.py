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
        "# GateForge Agent Modelica Two Week Report v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- week1_tag: `{payload.get('week1_tag')}`",
        f"- week2_tag: `{payload.get('week2_tag')}`",
        f"- decision: `{payload.get('decision')}`",
        "",
        "## Delta",
        "",
    ]
    delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    for key in [
        "success_at_k_pct",
        "median_time_to_pass_sec",
        "median_repair_rounds",
        "regression_count",
        "physics_fail_count",
    ]:
        lines.append(f"- {key}: `{delta.get(key)}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _d(w2: dict, w1: dict, key: str) -> float | None:
    a = w2.get(key)
    b = w1.get(key)
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    return round(float(a) - float(b), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed-format two-week comparison report")
    parser.add_argument("--week1-summary", required=True)
    parser.add_argument("--week2-summary", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_two_week_report_v1/report.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    w1 = _load_json(args.week1_summary)
    w2 = _load_json(args.week2_summary)
    d = _load_json(args.decision)

    payload = {
        "schema_version": "agent_modelica_two_week_report_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "week1_tag": w1.get("week_tag"),
        "week2_tag": w2.get("week_tag"),
        "decision": d.get("decision"),
        "week1": {
            "success_at_k_pct": w1.get("success_at_k_pct"),
            "median_time_to_pass_sec": w1.get("median_time_to_pass_sec"),
            "median_repair_rounds": w1.get("median_repair_rounds"),
            "regression_count": w1.get("regression_count"),
            "physics_fail_count": w1.get("physics_fail_count"),
        },
        "week2": {
            "success_at_k_pct": w2.get("success_at_k_pct"),
            "median_time_to_pass_sec": w2.get("median_time_to_pass_sec"),
            "median_repair_rounds": w2.get("median_repair_rounds"),
            "regression_count": w2.get("regression_count"),
            "physics_fail_count": w2.get("physics_fail_count"),
        },
        "delta": {
            "success_at_k_pct": _d(w2, w1, "success_at_k_pct"),
            "median_time_to_pass_sec": _d(w2, w1, "median_time_to_pass_sec"),
            "median_repair_rounds": _d(w2, w1, "median_repair_rounds"),
            "regression_count": _d(w2, w1, "regression_count"),
            "physics_fail_count": _d(w2, w1, "physics_fail_count"),
        },
        "sources": {
            "week1_summary": args.week1_summary,
            "week2_summary": args.week2_summary,
            "decision": args.decision,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
