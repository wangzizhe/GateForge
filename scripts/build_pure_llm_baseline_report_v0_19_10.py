"""Build the v0.19.10 pure-LLM baseline report."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_JSONL = REPO_ROOT / "artifacts" / "benchmark_v0_19_5" / "admitted_cases.jsonl"
SUMMARY_JSON = REPO_ROOT / "artifacts" / "benchmark_trajectory_v0_19_10" / "summary.json"
OUT_DIR = REPO_ROOT / "artifacts" / "pure_llm_baseline_v0_19_10"
AUDIT_PATTERNS = {
    "removed_runtime_flag": "disable-bounded-residual-repairs",
    "removed_overdetermined_repair": "_repair_overdetermined_added_binding_equation",
    "removed_legacy_siunits_guard": "_rewrite_legacy_msl_siunits_patch",
    "removed_overdetermined_label": "overdetermined_structural_balance_repair",
    "removed_legacy_guard_label": "legacy_msl_siunits_patch_guard",
}
AUDIT_PATHS = [
    REPO_ROOT / "gateforge" / "agent_modelica_live_executor_v1.py",
    REPO_ROOT / "scripts" / "run_semantic_reasoning_trajectory_v0_19_9.py",
    REPO_ROOT / "scripts" / "build_semantic_reasoning_report_v0_19_9.py",
]


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


def _classify(summary: dict) -> str:
    if str(summary.get("executor_status") or summary.get("status") or "") != "PASS":
        return "unresolved"
    turns = int(summary.get("n_turns") or 0)
    if turns <= 1:
        return "llm_solved_single_turn"
    return "llm_solved_multi_turn"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _contamination_audit() -> dict:
    results = {}
    leaked = []
    for label, pattern in AUDIT_PATTERNS.items():
        matches = []
        for path in AUDIT_PATHS:
            text = path.read_text(encoding="utf-8")
            if pattern in text:
                matches.append(str(path.relative_to(REPO_ROOT)))
        present = bool(matches)
        results[label] = {"pattern": pattern, "present": present, "matches": matches}
        if present:
            leaked.append(label)
    return {
        "paths": [str(path.relative_to(REPO_ROOT)) for path in AUDIT_PATHS],
        "checks": results,
        "contamination_detected": bool(leaked),
        "leaked_checks": leaked,
    }


def build_report(benchmark_path: Path = BENCHMARK_JSONL, summary_path: Path = SUMMARY_JSON) -> tuple[dict, list[dict]]:
    cases = _index(_load_jsonl(benchmark_path), "candidate_id")
    summaries = _index(_load_json(summary_path).get("summaries") or [], "candidate_id")
    records = []
    for cid in sorted(cases):
        case = cases[cid]
        summary = summaries.get(cid, {})
        classification = _classify(summary)
        records.append(
            {
                "candidate_id": cid,
                "benchmark_family": str(case.get("benchmark_family") or ""),
                "failure_type": str(case.get("failure_type") or ""),
                "classification": classification,
                "executor_status": str(summary.get("executor_status") or summary.get("status") or ""),
                "n_turns": int(summary.get("n_turns") or 0),
                "termination": str(summary.get("termination") or summary.get("status") or ""),
            }
        )

    by_family = {}
    for record in records:
        family = record["benchmark_family"] or "unknown"
        group = by_family.setdefault(
            family,
            {"total_cases": 0, "llm_solved_single_turn": 0, "llm_solved_multi_turn": 0, "unresolved": 0},
        )
        group["total_cases"] += 1
        group[record["classification"]] += 1

    counts = Counter(record["classification"] for record in records)
    audit = _contamination_audit()
    report = {
        "version": "v0.19.10",
        "benchmark": _display_path(benchmark_path),
        "trajectory_summary": _display_path(summary_path),
        "n_cases": len(records),
        "classification_counts": {
            "llm_solved_single_turn": counts.get("llm_solved_single_turn", 0),
            "llm_solved_multi_turn": counts.get("llm_solved_multi_turn", 0),
            "unresolved": counts.get("unresolved", 0),
        },
        "by_family": dict(sorted(by_family.items())),
        "prompt_runtime_contamination_audit": audit,
        "conclusion": (
            "v0.19.10 removes executor-side bounded residual repairs and reports the frozen 56-case "
            "benchmark as a pure-LLM baseline, split only into single-turn solved, multi-turn solved, "
            "and unresolved cases."
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
