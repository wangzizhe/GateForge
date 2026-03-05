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
        "# GateForge Agent Modelica MVP Execution Summary v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- three_round_records: `{payload.get('three_round_records')}`",
        f"- latest_ab_delta_success_at_k_pct: `{(payload.get('retrieval_ab') or {}).get('delta_success_at_k_pct')}`",
        f"- latest_ab_delta_regression_count: `{(payload.get('retrieval_ab') or {}).get('delta_regression_count')}`",
        f"- challenge_delta_success_at_k_pct: `{(payload.get('challenge') or {}).get('delta_success_at_k_pct')}`",
        f"- challenge_delta_regression_count: `{(payload.get('challenge') or {}).get('delta_regression_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _num(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one-page MVP execution summary from key artifact packs")
    parser.add_argument(
        "--three-round-summary",
        default="artifacts/agent_modelica_mvp_before_after_v1_rounds/summary.json",
    )
    parser.add_argument(
        "--top2-summary",
        default="artifacts/agent_modelica_top2_regression_challenge_v1/top2_summary.json",
    )
    parser.add_argument(
        "--retrieval-ab-summary",
        default="artifacts/agent_modelica_retrieval_ab_v1/ab_summary.json",
    )
    parser.add_argument(
        "--challenge-compare",
        default="artifacts/agent_modelica_top2_regression_challenge_v1/compare.json",
    )
    parser.add_argument("--out", default="artifacts/agent_modelica_mvp_exec_summary_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    three_round = _load_json(args.three_round_summary)
    top2 = _load_json(args.top2_summary)
    retrieval_ab = _load_json(args.retrieval_ab_summary)
    challenge = _load_json(args.challenge_compare)

    three_rows = three_round.get("rows") if isinstance(three_round.get("rows"), list) else []
    before_top2 = top2.get("before_top2") if isinstance(top2.get("before_top2"), list) else []
    after_top2 = top2.get("after_top2") if isinstance(top2.get("after_top2"), list) else []
    ab_delta = retrieval_ab.get("delta_on_minus_off") if isinstance(retrieval_ab.get("delta_on_minus_off"), dict) else {}
    ch_delta = challenge.get("delta") if isinstance(challenge.get("delta"), dict) else {}

    reasons: list[str] = []
    if not three_rows:
        reasons.append("missing_three_round_records")
    if not isinstance(ab_delta.get("success_at_k_pct"), (int, float)):
        reasons.append("missing_retrieval_ab_delta_success")
    if not isinstance(ch_delta.get("success_at_k_pct"), (int, float)):
        reasons.append("missing_challenge_delta_success")

    status = "PASS" if not reasons else "NEEDS_REVIEW"
    payload = {
        "schema_version": "agent_modelica_mvp_exec_summary_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "three_round_records": len(three_rows),
        "top2": {
            "before_count": len(before_top2),
            "after_count": len(after_top2),
            "before": before_top2[:2],
            "after": after_top2[:2],
        },
        "retrieval_ab": {
            "delta_success_at_k_pct": _num(ab_delta.get("success_at_k_pct")),
            "delta_regression_count": _num(ab_delta.get("regression_count")),
            "delta_median_time_to_pass_sec": _num(ab_delta.get("median_time_to_pass_sec")),
            "delta_mean_retrieved_example_count": _num(ab_delta.get("mean_retrieved_example_count")),
        },
        "challenge": {
            "delta_success_at_k_pct": _num(ch_delta.get("success_at_k_pct")),
            "delta_regression_count": _num(ch_delta.get("regression_count")),
            "delta_physics_fail_count": _num(ch_delta.get("physics_fail_count")),
        },
        "sources": {
            "three_round_summary": args.three_round_summary,
            "top2_summary": args.top2_summary,
            "retrieval_ab_summary": args.retrieval_ab_summary,
            "challenge_compare": args.challenge_compare,
        },
        "reasons": reasons,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "three_round_records": payload.get("three_round_records")}))


if __name__ == "__main__":
    main()
