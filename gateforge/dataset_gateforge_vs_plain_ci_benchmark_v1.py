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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _extract_metrics(payload: dict) -> dict:
    return {
        "blocked_critical_count": _to_int(payload.get("blocked_critical_count", 0)),
        "escaped_critical_count": _to_int(payload.get("escaped_critical_count", 0)),
        "false_positive_rate": _to_float(payload.get("false_positive_rate", 0.0)),
        "needs_review_count": _to_int(payload.get("needs_review_count", 0)),
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    d = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    lines = [
        "# GateForge vs Plain CI Benchmark v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- verdict: `{payload.get('verdict')}`",
        f"- advantage_score: `{payload.get('advantage_score')}`",
        f"- delta_blocked_critical_count: `{d.get('blocked_critical_count')}`",
        f"- delta_escaped_critical_count: `{d.get('escaped_critical_count')}`",
        f"- delta_false_positive_rate: `{d.get('false_positive_rate')}`",
        f"- delta_needs_review_count: `{d.get('needs_review_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare GateForge governance outcomes versus plain CI outcomes")
    parser.add_argument("--gateforge-summary", required=True)
    parser.add_argument("--plain-ci-summary", required=True)
    parser.add_argument("--max-fp-regression", type=float, default=0.03)
    parser.add_argument("--out", default="artifacts/dataset_gateforge_vs_plain_ci_benchmark_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    gateforge = _load_json(args.gateforge_summary)
    plain_ci = _load_json(args.plain_ci_summary)

    reasons: list[str] = []
    if not gateforge:
        reasons.append("gateforge_summary_missing")
    if not plain_ci:
        reasons.append("plain_ci_summary_missing")

    gf = _extract_metrics(gateforge)
    pc = _extract_metrics(plain_ci)

    delta = {
        "blocked_critical_count": gf["blocked_critical_count"] - pc["blocked_critical_count"],
        "escaped_critical_count": gf["escaped_critical_count"] - pc["escaped_critical_count"],
        "false_positive_rate": round(gf["false_positive_rate"] - pc["false_positive_rate"], 4),
        "needs_review_count": gf["needs_review_count"] - pc["needs_review_count"],
    }

    score = 0
    if delta["blocked_critical_count"] > 0:
        score += 3
    elif delta["blocked_critical_count"] < 0:
        score -= 3

    if delta["escaped_critical_count"] < 0:
        score += 4
    elif delta["escaped_critical_count"] > 0:
        score -= 4

    if delta["false_positive_rate"] <= 0.0:
        score += 2
    elif delta["false_positive_rate"] > float(args.max_fp_regression):
        score -= 3
        reasons.append("false_positive_regression_high")

    if delta["needs_review_count"] > 0:
        score += 1

    if delta["blocked_critical_count"] <= 0:
        reasons.append("no_critical_block_advantage")
    if delta["escaped_critical_count"] >= 0:
        reasons.append("no_critical_escape_reduction")

    verdict = "GATEFORGE_ADVANTAGE"
    if score <= 0:
        verdict = "INCONCLUSIVE"
    if score < -2:
        verdict = "PLAIN_CI_BETTER"

    status = "PASS"
    if "gateforge_summary_missing" in reasons or "plain_ci_summary_missing" in reasons:
        status = "FAIL"
    elif verdict != "GATEFORGE_ADVANTAGE":
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "verdict": verdict,
        "advantage_score": score,
        "gateforge_metrics": gf,
        "plain_ci_metrics": pc,
        "delta": delta,
        "reasons": sorted(set(reasons)),
        "sources": {
            "gateforge_summary": args.gateforge_summary,
            "plain_ci_summary": args.plain_ci_summary,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "verdict": verdict, "advantage_score": score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
