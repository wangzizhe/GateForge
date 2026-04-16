"""Run the v0.19.11 overdetermined structural benchmark."""
from __future__ import annotations

import json
from pathlib import Path

from run_benchmark_trajectory_v0_19_5 import _aggregate, _load_cases, _run_case, _summarise

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_JSONL = REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_11" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "overdetermined_trajectory_v0_19_11"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(CANDIDATES_JSONL))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    raw_root = out_root / "raw"
    raw_root.mkdir(exist_ok=True)

    cases = _load_cases(Path(args.benchmark))
    print(f"Loaded {len(cases)} overdetermined cases.\n")

    summaries = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        print(f"[{i}/{len(cases)}] Running {cid}")
        payload = _run_case(case, raw_root / f"{cid}.json")
        summary = _summarise(case, payload)
        summary["overdetermined_relation_id"] = str(case.get("overdetermined_relation_id") or "")
        summaries.append(summary)
        status = summary.get("executor_status") or summary.get("status")
        print(f"  -> status={status} turns={summary.get('n_turns', '?')} termination={summary.get('termination', '?')}")
        for turn, err in enumerate(summary.get("observed_error_sequence", []), 1):
            print(f"     turn {turn}: {err}")

    report = {
        "version": "v0.19.11",
        "family": "overdetermined_structural_family",
        "n_cases": len(summaries),
        "summaries": summaries,
    }
    report["aggregate"] = _aggregate(summaries)
    (out_root / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    aggregate = report["aggregate"]
    print("\n=== Aggregate ===")
    print(f"  pass_rate: {aggregate['pass_rate']:.3f} ({aggregate['pass_count']}/{aggregate['total_cases']})")
    print(f"Results written to {out_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
