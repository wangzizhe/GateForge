from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _case_id(row: dict[str, Any]) -> str:
    return str(row.get("case_id") or row.get("id") or "")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _is_fail(value: Any) -> bool:
    return str(value or "").lower() in {"fail", "failed", "error", "timeout", "no_final"}


def failure_stage(log_text: str) -> str:
    lower = log_text.lower()
    if "too few equations" in lower or "under-determined" in lower or "underdetermined" in lower:
        return "model_check_underdetermined"
    if "too many equations" in lower or "over-determined" in lower or "overdetermined" in lower:
        return "model_check_overdetermined"
    if "failed to build model" in lower or "error:" in lower:
        return "build_or_model_check"
    if "simulation execution failed" in lower or "assertion" in lower:
        return "simulate"
    return "unknown"


def classify_failure(
    *,
    pairwise_row: dict[str, Any],
    external_row: dict[str, Any],
    workspace: Path,
    subject_key: str,
) -> dict[str, Any]:
    case_id = _case_id(pairwise_row)
    initial = workspace / "initial.mo"
    final = workspace / "final.mo"
    final_eval = workspace / "final_eval.omc.txt"
    log_text = _read_text(final_eval)
    stage = failure_stage(log_text)
    has_final = final.exists() or bool(external_row.get("final_model"))
    changed = bool(initial.exists() and final.exists() and _read_text(initial) != _read_text(final))
    timed_out = bool(external_row.get("timed_out") or external_row.get("external_timed_out"))
    subject_failed = _is_fail(pairwise_row.get(subject_key))
    if subject_failed:
        label = "shared_failure"
    elif not has_final:
        label = "no_final_timeout" if timed_out else "no_final"
    elif not changed and stage == "model_check_underdetermined":
        label = "unchanged_underdetermined"
    elif not changed and stage == "simulate":
        label = "unchanged_simulation_failure"
    elif timed_out and changed:
        label = "timeout_after_partial_change"
    elif timed_out:
        label = "timeout_no_progress"
    elif changed:
        label = "changed_still_failed"
    else:
        label = "unchanged_failure"
    return {
        "case_id": case_id,
        "bucket": str(pairwise_row.get("bucket") or pairwise_row.get("group") or "all"),
        "taxonomy": label,
        "failure_stage": stage,
        "subject_status": str(pairwise_row.get(subject_key) or ""),
        "external_status": str(pairwise_row.get("external_status") or ""),
        "has_final": has_final,
        "changed_final": changed,
        "timed_out": timed_out,
    }


def build_taxonomy(
    *,
    pairwise_rows: list[dict[str, Any]],
    external_rows: list[dict[str, Any]],
    workspace_root: Path,
    subject_key: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    external_by_case = {_case_id(row): row for row in external_rows}
    taxonomy_rows: list[dict[str, Any]] = []
    for row in pairwise_rows:
        if not _is_fail(row.get("external_status")):
            continue
        case_id = _case_id(row)
        taxonomy_rows.append(
            classify_failure(
                pairwise_row=row,
                external_row=external_by_case.get(case_id, {}),
                workspace=workspace_root / case_id,
                subject_key=subject_key,
            )
        )
    taxonomy_counts = Counter(row["taxonomy"] for row in taxonomy_rows)
    bucket_counts = Counter(row["bucket"] for row in taxonomy_rows)
    summary = {
        "status": "PASS",
        "failure_count": len(taxonomy_rows),
        "failure_by_bucket": dict(sorted(bucket_counts.items())),
        "taxonomy_counts": dict(sorted(taxonomy_counts.items())),
        "shared_failure_case_ids": [
            row["case_id"] for row in taxonomy_rows if row["taxonomy"] == "shared_failure"
        ],
    }
    return taxonomy_rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify external-agent failure artifacts.")
    parser.add_argument("--pairwise-results", type=Path, required=True)
    parser.add_argument("--external-results", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--subject-key", default="subject_status")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    taxonomy_rows, summary = build_taxonomy(
        pairwise_rows=load_jsonl(args.pairwise_results),
        external_rows=load_jsonl(args.external_results),
        workspace_root=args.workspace_root,
        subject_key=str(args.subject_key),
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "case_taxonomy.json").write_text(
        json.dumps(taxonomy_rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
