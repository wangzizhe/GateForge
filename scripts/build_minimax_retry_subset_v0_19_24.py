from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK = REPO_ROOT / "artifacts" / "benchmark_gf_v1" / "admitted_cases.jsonl"
DEFAULT_BASELINE_SUMMARY = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_minimax_20260417_rerun" / "summary.json"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "benchmark_gf_v1" / "minimax_retry_subset_v0_19_24.jsonl"


def build_retry_subset(benchmark_path: Path, baseline_summary_path: Path) -> list[dict]:
    baseline = json.loads(baseline_summary_path.read_text(encoding="utf-8"))
    failed_ids = {
        str(row.get("candidate_id") or "")
        for row in baseline.get("summaries", [])
        if str(row.get("executor_status") or "").upper() != "PASS"
    }
    subset: list[dict] = []
    with benchmark_path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if str(row.get("candidate_id") or "") in failed_ids:
                subset.append(row)
    return subset


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--baseline-summary", default=str(DEFAULT_BASELINE_SUMMARY))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    subset = build_retry_subset(Path(args.benchmark), Path(args.baseline_summary))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in subset:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"retry_subset_cases: {len(subset)}")
    print(f"wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
