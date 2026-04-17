from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIRST_PASS = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_minimax_20260417_rerun" / "summary.json"
DEFAULT_RETRY = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_minimax_retry_v0_19_24" / "summary.json"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_minimax_retry_v0_19_24" / "final_report_v0_19_24.json"


def _aggregate_from_summaries(summaries: list[dict]) -> dict:
    total = len(summaries)
    passed = sum(1 for row in summaries if str(row.get("executor_status") or "").upper() == "PASS")
    by_family: dict[str, dict] = {}
    turn_shape_counts: dict[str, int] = {}

    for row in summaries:
        family = str(row.get("benchmark_family") or "unknown")
        status = str(row.get("executor_status") or "").upper()
        by_family.setdefault(family, {"total": 0, "pass": 0, "turns": []})
        by_family[family]["total"] += 1
        if status == "PASS":
            by_family[family]["pass"] += 1
        by_family[family]["turns"].append(int(row.get("n_turns") or 0))
        shape = str(row.get("turn_shape") or "unknown")
        turn_shape_counts[shape] = turn_shape_counts.get(shape, 0) + 1

    return {
        "total_cases": total,
        "pass_count": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "by_family": {
            family: {
                "total": bucket["total"],
                "pass_rate": round(bucket["pass"] / bucket["total"], 3) if bucket["total"] else 0.0,
                "avg_turns": round(sum(bucket["turns"]) / len(bucket["turns"]), 2) if bucket["turns"] else 0.0,
            }
            for family, bucket in sorted(by_family.items())
        },
        "turn_shape_counts": turn_shape_counts,
    }


def build_final_report(first_pass_summary_path: Path, retry_summary_path: Path) -> dict:
    first_pass = json.loads(first_pass_summary_path.read_text(encoding="utf-8"))
    retry = json.loads(retry_summary_path.read_text(encoding="utf-8"))

    first_rows = list(first_pass.get("summaries") or [])
    retry_rows = {str(row.get("candidate_id") or ""): row for row in retry.get("summaries") or []}

    merged: list[dict] = []
    recovered_case_ids: list[str] = []
    still_failed_case_ids: list[str] = []

    for row in first_rows:
        candidate_id = str(row.get("candidate_id") or "")
        merged_row = retry_rows.get(candidate_id, row)
        merged.append(merged_row)
        if str(row.get("executor_status") or "").upper() != "PASS":
            if str(merged_row.get("executor_status") or "").upper() == "PASS":
                recovered_case_ids.append(candidate_id)
            else:
                still_failed_case_ids.append(candidate_id)

    merged_aggregate = _aggregate_from_summaries(merged)

    return {
        "schema_version": "gateforge_minimax_final_report_v0_19_24",
        "first_pass_summary_source": str(first_pass_summary_path),
        "retry_summary_source": str(retry_summary_path),
        "first_pass_aggregate": first_pass.get("aggregate", {}),
        "retry_subset_aggregate": retry.get("aggregate", {}),
        "post_retry_aggregate": merged_aggregate,
        "initial_failed_case_count": len(retry_rows),
        "recovered_case_count": len(recovered_case_ids),
        "still_failed_case_count": len(still_failed_case_ids),
        "recovered_case_ids": recovered_case_ids,
        "still_failed_case_ids": still_failed_case_ids,
        "headline_conclusion": (
            f"Retry recovered {len(recovered_case_ids)} of {len(retry_rows)} initially failed MiniMax cases."
        ),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--first-pass", default=str(DEFAULT_FIRST_PASS))
    parser.add_argument("--retry", default=str(DEFAULT_RETRY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    report = build_final_report(Path(args.first_pass), Path(args.retry))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("MiniMax final report")
    print(f"  first_pass_rate: {report['first_pass_aggregate'].get('pass_rate')}")
    print(f"  post_retry_rate: {report['post_retry_aggregate'].get('pass_rate')}")
    print(f"  recovered_case_count: {report['recovered_case_count']}")
    print(f"  still_failed_case_count: {report['still_failed_case_count']}")
    print(f"  wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
