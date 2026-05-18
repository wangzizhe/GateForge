from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _case_id(row: dict[str, Any]) -> str:
    return str(row.get("case_id") or row.get("id") or "")


def _is_pass(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("policy_status") or row.get("verdict") or "").lower()
    return status in {"pass", "passed", "clean_pass", "warning_pass"}


def _status(row: dict[str, Any]) -> str:
    if row.get("status"):
        return str(row["status"])
    if row.get("policy_status"):
        return str(row["policy_status"])
    if row.get("verdict"):
        return str(row["verdict"])
    return "pass" if _is_pass(row) else "fail"


def load_replacements(paths: list[Path]) -> dict[str, dict[str, Any]]:
    replacements: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in load_jsonl(path):
            case_id = _case_id(row)
            if not case_id or not _is_pass(row):
                continue
            replacements[case_id] = {
                "case_id": case_id,
                "status": _status(row),
                "source": str(path),
                "tokens": int(row.get("tokens") or row.get("token_used") or 0),
                "wall_time_sec": float(row.get("wall_time_sec") or 0),
            }
    return replacements


def build_overlay(
    *,
    base_rows: list[dict[str, Any]],
    replacements: dict[str, dict[str, Any]],
    subject_key: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adjusted_rows: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    for row in base_rows:
        adjusted = dict(row)
        case_id = _case_id(row)
        original_status = str(adjusted.get(subject_key) or "")
        replacement = replacements.get(case_id)
        if replacement and original_status.lower() in {"fail", "failed"}:
            adjusted[f"{subject_key}_original"] = original_status
            adjusted[subject_key] = replacement["status"]
            adjusted["overlay_replacement"] = replacement
            applied.append(replacement)
        adjusted_rows.append(adjusted)
    missing_replacements = sorted(set(replacements) - {_case_id(row) for row in base_rows})
    summary = summarize_overlay(adjusted_rows, subject_key=subject_key)
    summary.update(
        {
            "status": "PASS" if not missing_replacements else "REVIEW",
            "applied_replacement_count": len(applied),
            "applied_replacement_case_ids": [row["case_id"] for row in applied],
            "missing_replacement_case_ids": missing_replacements,
        }
    )
    return adjusted_rows, summary


def summarize_overlay(rows: list[dict[str, Any]], *, subject_key: str) -> dict[str, Any]:
    by_bucket: dict[str, dict[str, Any]] = defaultdict(lambda: {"case_count": 0, "subject_pass": 0, "baseline_pass": 0})
    subject_pass = 0
    baseline_pass = 0
    for row in rows:
        bucket = str(row.get("bucket") or row.get("group") or "all")
        item = by_bucket[bucket]
        item["case_count"] += 1
        row_subject_pass = str(row.get(subject_key) or "").lower() not in {"fail", "failed", ""}
        row_baseline_pass = str(row.get("baseline_status") or "").lower() not in {"fail", "failed", ""}
        subject_pass += int(row_subject_pass)
        baseline_pass += int(row_baseline_pass)
        item["subject_pass"] += int(row_subject_pass)
        item["baseline_pass"] += int(row_baseline_pass)
    return {
        "case_count": len(rows),
        "subject_key": subject_key,
        "subject_pass": subject_pass,
        "baseline_pass": baseline_pass,
        "by_bucket": dict(sorted(by_bucket.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an adjusted evaluation table from replacement result rows.")
    parser.add_argument("--base-results", type=Path, required=True)
    parser.add_argument("--replacement-results", type=Path, action="append", default=[])
    parser.add_argument("--subject-key", default="subject_status")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    base_rows = load_jsonl(args.base_results)
    replacements = load_replacements(list(args.replacement_results or []))
    adjusted_rows, summary = build_overlay(
        base_rows=base_rows,
        replacements=replacements,
        subject_key=str(args.subject_key),
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out_dir / "adjusted_results.jsonl", adjusted_rows)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
