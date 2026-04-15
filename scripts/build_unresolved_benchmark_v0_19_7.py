"""
Build a focused v0.19.7 benchmark from the unresolved v0.19.5 cases.

Inputs:
  artifacts/benchmark_v0_19_5/admitted_cases.jsonl
  artifacts/constraint_residual_profile_v0_19_6/unresolved_cases.jsonl

Outputs:
  artifacts/benchmark_unresolved_v0_19_7/admitted_cases.jsonl
  artifacts/benchmark_unresolved_v0_19_7/summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_JSONL = REPO_ROOT / "artifacts" / "benchmark_v0_19_5" / "admitted_cases.jsonl"
UNRESOLVED_JSONL = REPO_ROOT / "artifacts" / "constraint_residual_profile_v0_19_6" / "unresolved_cases.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_unresolved_v0_19_7"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases_by_id = {str(case.get("candidate_id") or ""): case for case in _load_jsonl(BENCHMARK_JSONL)}
    unresolved = _load_jsonl(UNRESOLVED_JSONL)
    selected = []
    missing = []
    for row in unresolved:
        cid = str(row.get("candidate_id") or "")
        case = cases_by_id.get(cid)
        if not case:
            missing.append(cid)
            continue
        merged = dict(case)
        merged["benchmark_version"] = "v0.19.7"
        merged["benchmark_source"] = "v0.19.5_unresolved_focus"
        merged["v0_19_6_final_residual_class"] = str(row.get("final_residual_class") or "")
        merged["v0_19_6_recommended_strategy"] = str(
            (row.get("recommended_next_strategy") or {}).get("strategy_id") or ""
        )
        selected.append(merged)

    if missing:
        raise SystemExit(f"missing unresolved ids in benchmark: {missing}")

    out_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as handle:
        for case in selected:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    summary = {
        "benchmark_version": "v0.19.7",
        "total_cases": len(selected),
        "case_ids": [case["candidate_id"] for case in selected],
        "by_residual_class": {},
        "output": str(out_jsonl),
    }
    for case in selected:
        residual = str(case.get("v0_19_6_final_residual_class") or "unknown")
        summary["by_residual_class"][residual] = summary["by_residual_class"].get(residual, 0) + 1
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("=== v0.19.7 unresolved benchmark ===")
    print(f"  cases: {len(selected)}")
    for key, value in sorted(summary["by_residual_class"].items()):
        print(f"  {key}: {value}")
    print(f"  admitted_cases: {out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
