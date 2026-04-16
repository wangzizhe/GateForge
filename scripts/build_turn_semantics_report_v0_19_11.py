"""Inspect turn semantics in the v0.19.10 pure-LLM baseline."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY_JSON = REPO_ROOT / "artifacts" / "benchmark_trajectory_v0_19_10" / "summary.json"
OUT_DIR = REPO_ROOT / "artifacts" / "turn_semantics_report_v0_19_11"
TARGET_FAMILIES = [
    "component_modifier_name_error",
    "connection_endpoint_typo",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_turn_shape(summary: dict) -> str:
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


def build_report(summary_path: Path = SUMMARY_JSON) -> tuple[dict, list[dict]]:
    rows = _load_json(summary_path).get("summaries") or []
    records = []
    for row in rows:
        family = str(row.get("benchmark_family") or "")
        if family not in TARGET_FAMILIES:
            continue
        records.append(
            {
                "candidate_id": str(row.get("candidate_id") or ""),
                "benchmark_family": family,
                "n_turns": int(row.get("n_turns") or 0),
                "observed_error_sequence": list(row.get("observed_error_sequence") or []),
                "turn_shape": classify_turn_shape(row),
            }
        )

    by_family = {}
    for family in TARGET_FAMILIES:
        family_rows = [record for record in records if record["benchmark_family"] == family]
        counts = Counter(record["turn_shape"] for record in family_rows)
        by_family[family] = {
            "total_cases": len(family_rows),
            "avg_turns": (
                sum(record["n_turns"] for record in family_rows) / len(family_rows)
                if family_rows
                else 0.0
            ),
            "turn_shape_counts": dict(sorted(counts.items())),
            "sample_case_ids": [record["candidate_id"] for record in family_rows[:3]],
        }

    report = {
        "version": "v0.19.11",
        "source_summary": str(summary_path.relative_to(REPO_ROOT)),
        "target_families": list(TARGET_FAMILIES),
        "by_family": by_family,
        "conclusion": (
            "The v0.19.10 simple surface-error families should be interpreted via turn shape: "
            "`single_fix_closure` means one failing validation followed by one successful "
            "post-fix validation, not true multi-repair reasoning."
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
