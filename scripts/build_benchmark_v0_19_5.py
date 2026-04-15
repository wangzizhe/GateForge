"""
Build the v0.19.5 hardened benchmark by carrying the v0.19.4 anchor cases and
adding newly admitted hardened mutation cases.

Outputs:
  artifacts/benchmark_v0_19_5/admitted_cases.jsonl
  artifacts/benchmark_v0_19_5/summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANCHOR_JSONL = REPO_ROOT / "artifacts" / "benchmark_v0_19_4" / "admitted_cases.jsonl"
HARDENED_JSONL = REPO_ROOT / "artifacts" / "hardened_mutations_v0_19_5" / "candidates.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_v0_19_5"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _normalise(case: dict, source: str) -> dict:
    merged = dict(case)
    candidate_id = str(merged.get("candidate_id") or merged.get("task_id") or "")
    merged["candidate_id"] = candidate_id
    merged["task_id"] = str(merged.get("task_id") or candidate_id)
    merged["benchmark_version"] = "v0.19.5"
    merged["benchmark_source"] = source
    merged.setdefault("admission_status", "PASS")
    merged.setdefault("backend", "openmodelica_docker")
    merged.setdefault("planner_backend", "gemini")
    return merged


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    anchor = [_normalise(case, "v0.19.4_anchor") for case in _load_jsonl(ANCHOR_JSONL)]
    hardened = [_normalise(case, "v0.19.5_hardened") for case in _load_jsonl(HARDENED_JSONL)]
    cases = anchor + hardened

    seen = set()
    duplicates = []
    for case in cases:
        cid = case["candidate_id"]
        if cid in seen:
            duplicates.append(cid)
        seen.add(cid)
    if duplicates:
        raise SystemExit(f"duplicate candidate ids: {duplicates}")

    out_jsonl = OUT_DIR / "admitted_cases.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")

    by_family: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_difficulty_prior: dict[str, int] = {}
    for case in cases:
        family = str(case.get("benchmark_family") or case.get("mutation_family") or "unknown")
        by_family[family] = by_family.get(family, 0) + 1
        source = str(case.get("benchmark_source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        prior = str(case.get("difficulty_prior") or "anchor")
        by_difficulty_prior[prior] = by_difficulty_prior.get(prior, 0) + 1

    summary = {
        "benchmark_version": "v0.19.5",
        "total_cases": len(cases),
        "anchor_cases": len(anchor),
        "hardened_cases": len(hardened),
        "target_min_cases": 50,
        "target_met": len(cases) >= 50,
        "by_source": by_source,
        "by_family": by_family,
        "by_difficulty_prior": by_difficulty_prior,
        "output": str(out_jsonl),
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("=== v0.19.5 Benchmark ===")
    print(f"  anchor_cases: {len(anchor)}")
    print(f"  hardened_cases: {len(hardened)}")
    print(f"  total_cases: {len(cases)}")
    print(f"  target_met: {summary['target_met']}")
    print(f"  admitted_cases: {out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
