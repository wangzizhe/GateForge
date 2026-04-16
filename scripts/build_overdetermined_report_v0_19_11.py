"""Build the v0.19.11 overdetermined structural benchmark report."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_JSONL = REPO_ROOT / "artifacts" / "overdetermined_mutations_v0_19_11" / "admitted_cases.jsonl"
SUMMARY_JSON = REPO_ROOT / "artifacts" / "overdetermined_trajectory_v0_19_11" / "summary.json"
TURN_SEMANTICS_JSON = REPO_ROOT / "artifacts" / "turn_semantics_report_v0_19_11" / "summary.json"
OUT_DIR = REPO_ROOT / "artifacts" / "overdetermined_report_v0_19_11"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _index(rows: list[dict], key: str) -> dict[str, dict]:
    indexed = {}
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            indexed[value] = dict(row)
    return indexed


def classify_resolution_shape(summary: dict) -> str:
    status = str(summary.get("executor_status") or summary.get("status") or "")
    if status != "PASS":
        return "unresolved"

    sequence = [str(item) for item in (summary.get("observed_error_sequence") or [])]
    non_none = [item for item in sequence if item and item != "none"]
    turns = int(summary.get("n_turns") or 0)
    if turns == 2 and len(non_none) == 1 and sequence[-1:] == ["none"]:
        return "single_fix_closure"
    if sequence[-1:] == ["none"] and len(non_none) >= 2:
        return "requires_multiple_llm_repairs"
    return "other_pass_shape"


def build_report(benchmark_path: Path = BENCHMARK_JSONL, summary_path: Path = SUMMARY_JSON) -> tuple[dict, list[dict]]:
    cases = _index(_load_jsonl(benchmark_path), "candidate_id")
    summaries = _index(_load_json(summary_path).get("summaries") or [], "candidate_id")
    turn_semantics = _load_json(TURN_SEMANTICS_JSON) if TURN_SEMANTICS_JSON.exists() else {}

    records = []
    for cid in sorted(cases):
        case = cases[cid]
        summary = summaries.get(cid, {})
        records.append(
            {
                "candidate_id": cid,
                "overdetermined_relation_id": str(case.get("overdetermined_relation_id") or ""),
                "redundant_relation_equation": str(case.get("redundant_relation_equation") or ""),
                "executor_status": str(summary.get("executor_status") or summary.get("status") or ""),
                "n_turns": int(summary.get("n_turns") or 0),
                "observed_error_sequence": list(summary.get("observed_error_sequence") or []),
                "resolution_shape": classify_resolution_shape(summary),
            }
        )

    counts = Counter(record["resolution_shape"] for record in records)
    pass_count = sum(1 for record in records if record["executor_status"] == "PASS")
    unresolved_ids = [record["candidate_id"] for record in records if record["executor_status"] != "PASS"]
    report = {
        "version": "v0.19.11",
        "family": "overdetermined_structural_family",
        "n_cases": len(records),
        "pass_count": pass_count,
        "pass_rate": pass_count / len(records) if records else 0.0,
        "avg_turns": sum(record["n_turns"] for record in records) / len(records) if records else 0.0,
        "resolution_shape_counts": dict(sorted(counts.items())),
        "unresolved_case_ids": unresolved_ids,
        "turn_semantics_anchor": turn_semantics.get("by_family") or {},
        "conclusion": (
            "v0.19.11 isolates the pure-LLM overdetermined structural family and reports its repair "
            "shape separately from the v0.19.10 single-fix-closure anchor families."
        ),
    }
    return report, records


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report, records = build_report()
    (OUT_DIR / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "cases.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
