from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    checks = payload.get("checks", {})
    lines = [
        "# GateForge Dataset Quality Gate",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        f"- failure_type_coverage: `{payload.get('failure_type_coverage')}`",
        f"- oracle_match_rate: `{payload.get('oracle_match_rate')}`",
        f"- replay_stable_rate: `{payload.get('replay_stable_rate')}`",
        f"- duplicate_rate: `{payload.get('duplicate_rate')}`",
        "",
        "## Checks",
        "",
    ]
    for key in sorted(checks.keys()):
        lines.append(f"- {key}: `{checks[key]}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate dataset quality gates before freeze")
    parser.add_argument("--build-summary", required=True, help="dataset_build summary.json")
    parser.add_argument("--quality", required=True, help="dataset_build quality_report.json")
    parser.add_argument("--distribution", required=True, help="dataset_build distribution.json")
    parser.add_argument("--out", default="artifacts/dataset_build/quality_gate.json")
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--min-total-cases", type=int, default=100)
    parser.add_argument("--min-failure-type-coverage", type=int, default=4)
    parser.add_argument("--min-oracle-match-rate", type=float, default=0.7)
    parser.add_argument("--min-replay-stable-rate", type=float, default=0.95)
    parser.add_argument("--max-duplicate-rate", type=float, default=0.05)
    args = parser.parse_args()

    build_summary = _load_json(args.build_summary)
    quality = _load_json(args.quality)
    distribution = _load_json(args.distribution)

    total = int(build_summary.get("total_cases", 0) or 0)
    deduped = int(build_summary.get("deduplicated_cases", 0) or 0)
    dropped = int(build_summary.get("dropped_duplicate_cases", 0) or 0)
    duplicate_rate = (dropped / total) if total > 0 else 0.0

    failure_map = distribution.get("actual_failure_type", {})
    if not isinstance(failure_map, dict):
        failure_map = {}
    failure_coverage = sum(1 for k, v in failure_map.items() if k != "none" and int(v or 0) > 0)

    oracle_match_rate = float(quality.get("oracle_match_rate", 0.0) or 0.0)
    replay_stable_rate = float(quality.get("replay_stable_rate", 0.0) or 0.0)

    checks = {
        "min_total_cases": "PASS" if total >= int(args.min_total_cases) else "FAIL",
        "min_failure_type_coverage": "PASS"
        if failure_coverage >= int(args.min_failure_type_coverage)
        else "FAIL",
        "min_oracle_match_rate": "PASS"
        if oracle_match_rate >= float(args.min_oracle_match_rate)
        else "FAIL",
        "min_replay_stable_rate": "PASS"
        if replay_stable_rate >= float(args.min_replay_stable_rate)
        else "FAIL",
        "max_duplicate_rate": "PASS" if duplicate_rate <= float(args.max_duplicate_rate) else "FAIL",
    }
    status = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"

    payload = {
        "status": status,
        "total_cases": total,
        "deduplicated_cases": deduped,
        "dropped_duplicate_cases": dropped,
        "duplicate_rate": round(duplicate_rate, 4),
        "failure_type_coverage": failure_coverage,
        "oracle_match_rate": round(oracle_match_rate, 4),
        "replay_stable_rate": round(replay_stable_rate, 4),
        "checks": checks,
        "inputs": {
            "build_summary": args.build_summary,
            "quality": args.quality,
            "distribution": args.distribution,
        },
    }
    _write_json(args.out, payload)
    report_out = args.report_out
    if not report_out:
        out = Path(args.out)
        report_out = str(out.with_suffix(".md")) if out.suffix == ".json" else f"{args.out}.md"
    _write_markdown(report_out, payload)
    print(json.dumps({"status": status, "checks": checks}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
