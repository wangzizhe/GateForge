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


def _append_jsonl(path: str, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_jsonl(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _safe_delta(cur: float | int | None, prev: float | int | None) -> float | None:
    if not isinstance(cur, (int, float)):
        return None
    if not isinstance(prev, (int, float)):
        return None
    return round(float(cur) - float(prev), 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    layered = payload.get("layered_pass_rate_pct_by_scale", {})
    lines = [
        "# GateForge Agent Modelica Weekly Metrics Page v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- week_tag: `{payload.get('week_tag')}`",
        f"- baseline_status: `{payload.get('baseline_status')}`",
        f"- success_at_k_pct: `{payload.get('success_at_k_pct')}`",
        f"- median_time_to_pass_sec: `{payload.get('median_time_to_pass_sec')}`",
        f"- median_repair_rounds: `{payload.get('median_repair_rounds')}`",
        f"- regression_count: `{payload.get('regression_count')}`",
        f"- physics_fail_count: `{payload.get('physics_fail_count')}`",
        f"- history_records: `{payload.get('history_records')}`",
        "",
        "## Layered Pass Rate",
        "",
    ]
    if isinstance(layered, dict) and layered:
        for scale in sorted(layered.keys()):
            lines.append(f"- {scale}: `{layered.get(scale)}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Weekly Delta", ""])
    delta = payload.get("delta_vs_previous", {})
    if isinstance(delta, dict) and delta:
        for key in [
            "success_at_k_pct",
            "median_time_to_pass_sec",
            "median_repair_rounds",
            "regression_count",
            "physics_fail_count",
        ]:
            lines.append(f"- delta_{key}: `{delta.get(key)}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Top Fail Reasons", ""])
    top_fail = payload.get("top_fail_reasons", {})
    if isinstance(top_fail, dict) and top_fail:
        for key, count in sorted(top_fail.items(), key=lambda kv: (-int(kv[1]), kv[0]))[:8]:
            lines.append(f"- {key}: `{count}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one-page weekly metrics for agent modelica baseline")
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--week-tag", default=datetime.now(timezone.utc).strftime("%G-W%V"))
    parser.add_argument("--ledger", default="artifacts/agent_modelica_weekly_metrics_v1/history.jsonl")
    parser.add_argument("--out", default="artifacts/agent_modelica_weekly_metrics_v1/page.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    baseline = _load_json(args.baseline_summary)
    reasons: list[str] = []

    required_fields = [
        "success_at_k_pct",
        "median_time_to_pass_sec",
        "median_repair_rounds",
        "regression_count",
        "physics_fail_count",
        "layered_pass_rate_pct_by_scale",
        "top_fail_reasons",
        "top_fail_reasons_by_scale",
    ]
    for key in required_fields:
        if key not in baseline:
            reasons.append(f"baseline_missing_field:{key}")

    baseline_status = str(baseline.get("status") or "FAIL")
    record = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "week_tag": args.week_tag,
        "baseline_status": baseline_status,
        "success_at_k_pct": baseline.get("success_at_k_pct"),
        "median_time_to_pass_sec": baseline.get("median_time_to_pass_sec"),
        "median_repair_rounds": baseline.get("median_repair_rounds"),
        "regression_count": baseline.get("regression_count"),
        "physics_fail_count": baseline.get("physics_fail_count"),
        "layered_pass_rate_pct_by_scale": baseline.get("layered_pass_rate_pct_by_scale", {}),
        "top_fail_reasons": baseline.get("top_fail_reasons", {}),
        "top_fail_reasons_by_scale": baseline.get("top_fail_reasons_by_scale", {}),
        "source": args.baseline_summary,
    }
    _append_jsonl(args.ledger, record)
    history = _load_jsonl(args.ledger)

    previous = history[-2] if len(history) >= 2 else {}
    delta_payload = {
        "success_at_k_pct": _safe_delta(record.get("success_at_k_pct"), previous.get("success_at_k_pct")),
        "median_time_to_pass_sec": _safe_delta(
            record.get("median_time_to_pass_sec"),
            previous.get("median_time_to_pass_sec"),
        ),
        "median_repair_rounds": _safe_delta(record.get("median_repair_rounds"), previous.get("median_repair_rounds")),
        "regression_count": _safe_delta(record.get("regression_count"), previous.get("regression_count")),
        "physics_fail_count": _safe_delta(record.get("physics_fail_count"), previous.get("physics_fail_count")),
    }

    status = baseline_status if baseline_status in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
    if reasons:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "week_tag": args.week_tag,
        "baseline_status": baseline_status,
        "success_at_k_pct": record.get("success_at_k_pct"),
        "median_time_to_pass_sec": record.get("median_time_to_pass_sec"),
        "median_repair_rounds": record.get("median_repair_rounds"),
        "regression_count": record.get("regression_count"),
        "physics_fail_count": record.get("physics_fail_count"),
        "layered_pass_rate_pct_by_scale": record.get("layered_pass_rate_pct_by_scale"),
        "top_fail_reasons": record.get("top_fail_reasons"),
        "top_fail_reasons_by_scale": record.get("top_fail_reasons_by_scale"),
        "history_records": len(history),
        "delta_vs_previous": delta_payload,
        "reasons": reasons,
        "sources": {
            "baseline_summary": args.baseline_summary,
            "ledger": args.ledger,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "week_tag": args.week_tag,
                "success_at_k_pct": payload.get("success_at_k_pct"),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
