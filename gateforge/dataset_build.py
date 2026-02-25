from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path

from .dataset_adapters import (
    adapt_benchmark_summary,
    adapt_mutation_benchmark_summary,
    adapt_run_summary,
    validate_cases,
)


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _expand_paths(explicit: list[str], patterns: list[str]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for p in explicit:
        path = str(Path(p))
        if path not in seen:
            resolved.append(path)
            seen.add(path)
    for pattern in patterns:
        for path_txt in sorted(glob.glob(pattern)):
            path = Path(path_txt)
            if not path.exists() or not path.is_file():
                continue
            p = str(path)
            if p in seen:
                continue
            resolved.append(p)
            seen.add(p)
    return resolved


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: str, rows: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _write_markdown(path: str, summary: dict, distribution: dict, quality: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Dataset Build Summary",
        "",
        f"- total_cases: `{summary.get('total_cases')}`",
        f"- deduplicated_cases: `{summary.get('deduplicated_cases')}`",
        f"- dropped_duplicate_cases: `{summary.get('dropped_duplicate_cases')}`",
        f"- oracle_match_rate: `{quality.get('oracle_match_rate')}`",
        f"- replay_stable_rate: `{quality.get('replay_stable_rate')}`",
        "",
        "## Source Distribution",
        "",
    ]
    src = distribution.get("source", {})
    if src:
        for k in sorted(src.keys()):
            lines.append(f"- {k}: `{src[k]}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Decision Distribution", ""])
    dec = distribution.get("actual_decision", {})
    if dec:
        for k in sorted(dec.keys()):
            lines.append(f"- {k}: `{dec[k]}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Failure Type Distribution", ""])
    ft = distribution.get("actual_failure_type", {})
    if ft:
        for k in sorted(ft.keys()):
            lines.append(f"- {k}: `{ft[k]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _distribution(cases: list[dict]) -> dict:
    source = Counter()
    decision = Counter()
    failure_type = Counter()
    stage = Counter()
    root_cause = Counter()
    trigger = Counter()
    severity = Counter()
    determinism = Counter()
    for row in cases:
        source[str(row.get("source") or "unknown")] += 1
        decision[str(row.get("actual_decision") or "unknown")] += 1
        failure_type[str(row.get("actual_failure_type") or "unknown")] += 1
        stage[str(row.get("actual_stage") or "unknown")] += 1
        factors = row.get("factors", {}) if isinstance(row.get("factors"), dict) else {}
        root_cause[str(factors.get("root_cause") or "unknown")] += 1
        trigger[str(factors.get("trigger") or "unknown")] += 1
        severity[str(factors.get("severity") or "unknown")] += 1
        determinism[str(factors.get("determinism") or "unknown")] += 1
    return {
        "source": dict(source),
        "actual_decision": dict(decision),
        "actual_failure_type": dict(failure_type),
        "actual_stage": dict(stage),
        "factors.root_cause": dict(root_cause),
        "factors.trigger": dict(trigger),
        "factors.severity": dict(severity),
        "factors.determinism": dict(determinism),
    }


def _quality_report(cases: list[dict]) -> dict:
    total = len(cases)
    if total == 0:
        return {
            "total_cases": 0,
            "oracle_match_rate": 0.0,
            "replay_stable_rate": 0.0,
            "decision_non_pass_rate": 0.0,
            "failure_case_rate": 0.0,
        }
    oracle_match = sum(1 for c in cases if bool(c.get("oracle_match")))
    replay_stable = sum(1 for c in cases if bool(c.get("replay_stable")))
    non_pass = sum(1 for c in cases if c.get("actual_decision") in {"FAIL", "NEEDS_REVIEW"})
    failure_cases = sum(1 for c in cases if c.get("actual_failure_type") != "none")
    return {
        "total_cases": total,
        "oracle_match_rate": round(oracle_match / total, 4),
        "replay_stable_rate": round(replay_stable / total, 4),
        "decision_non_pass_rate": round(non_pass / total, 4),
        "failure_case_rate": round(failure_cases / total, 4),
    }


def _deduplicate(cases: list[dict]) -> tuple[list[dict], int]:
    kept: list[dict] = []
    seen: set[str] = set()
    dropped = 0
    for case in cases:
        cid = str(case.get("case_id") or "")
        if cid in seen:
            dropped += 1
            continue
        seen.add(cid)
        kept.append(case)
    return kept, dropped


def main() -> None:
    parser = argparse.ArgumentParser(description="Build unified dataset_case assets from GateForge summaries")
    parser.add_argument("--benchmark-summary", action="append", default=[], help="benchmark summary JSON (repeatable)")
    parser.add_argument(
        "--benchmark-summary-glob",
        action="append",
        default=[],
        help="Glob pattern for benchmark summary JSON (repeatable, e.g. 'artifacts/benchmark*/summary.json')",
    )
    parser.add_argument("--mutation-summary", action="append", default=[], help="mutation benchmark summary JSON (repeatable)")
    parser.add_argument(
        "--mutation-summary-glob",
        action="append",
        default=[],
        help="Glob pattern for mutation summary JSON (repeatable)",
    )
    parser.add_argument("--run-summary", action="append", default=[], help="run summary JSON (repeatable)")
    parser.add_argument(
        "--run-summary-glob",
        action="append",
        default=[],
        help="Glob pattern for run summary JSON (repeatable)",
    )
    parser.add_argument("--autopilot-summary", action="append", default=[], help="autopilot summary JSON (repeatable)")
    parser.add_argument(
        "--autopilot-summary-glob",
        action="append",
        default=[],
        help="Glob pattern for autopilot summary JSON (repeatable)",
    )
    parser.add_argument(
        "--collect-summary",
        action="append",
        default=[],
        help="dataset_collect summary JSON path; discovered inputs are merged (repeatable)",
    )
    parser.add_argument("--out-dir", default="artifacts/dataset_build", help="Output directory")
    args = parser.parse_args()

    benchmark_inputs = _expand_paths(args.benchmark_summary, args.benchmark_summary_glob)
    mutation_inputs = _expand_paths(args.mutation_summary, args.mutation_summary_glob)
    run_inputs = _expand_paths(args.run_summary, args.run_summary_glob)
    autopilot_inputs = _expand_paths(args.autopilot_summary, args.autopilot_summary_glob)

    for collect_path in args.collect_summary:
        collect_payload = _load_json(collect_path)
        benchmark_inputs = _expand_paths(
            benchmark_inputs + (collect_payload.get("benchmark_summary_paths") or []),
            [],
        )
        mutation_inputs = _expand_paths(
            mutation_inputs + (collect_payload.get("mutation_summary_paths") or []),
            [],
        )
        run_inputs = _expand_paths(
            run_inputs + (collect_payload.get("run_summary_paths") or []),
            [],
        )
        autopilot_inputs = _expand_paths(
            autopilot_inputs + (collect_payload.get("autopilot_summary_paths") or []),
            [],
        )

    cases: list[dict] = []
    for path in benchmark_inputs:
        cases.extend(adapt_benchmark_summary(_load_json(path)))
    for path in mutation_inputs:
        cases.extend(adapt_mutation_benchmark_summary(_load_json(path)))
    for path in run_inputs:
        cases.append(adapt_run_summary(_load_json(path), source="run"))
    for path in autopilot_inputs:
        cases.append(adapt_run_summary(_load_json(path), source="autopilot"))

    validate_cases(cases)
    deduped, dropped = _deduplicate(cases)
    distribution = _distribution(deduped)
    quality = _quality_report(deduped)
    summary = {
        "total_cases": len(cases),
        "deduplicated_cases": len(deduped),
        "dropped_duplicate_cases": dropped,
        "inputs": {
            "benchmark_summary_count": len(benchmark_inputs),
            "mutation_summary_count": len(mutation_inputs),
            "run_summary_count": len(run_inputs),
            "autopilot_summary_count": len(autopilot_inputs),
            "benchmark_summary_paths": benchmark_inputs,
            "mutation_summary_paths": mutation_inputs,
            "run_summary_paths": run_inputs,
            "autopilot_summary_paths": autopilot_inputs,
            "collect_summary_paths": args.collect_summary,
        },
        "outputs": {
            "dataset_jsonl": str(Path(args.out_dir) / "dataset_cases.jsonl"),
            "distribution_json": str(Path(args.out_dir) / "distribution.json"),
            "quality_json": str(Path(args.out_dir) / "quality_report.json"),
        },
    }

    _write_jsonl(str(Path(args.out_dir) / "dataset_cases.jsonl"), deduped)
    _write_json(str(Path(args.out_dir) / "distribution.json"), distribution)
    _write_json(str(Path(args.out_dir) / "quality_report.json"), quality)
    _write_json(str(Path(args.out_dir) / "summary.json"), summary)
    _write_markdown(str(Path(args.out_dir) / "summary.md"), summary, distribution, quality)
    print(json.dumps({"total_cases": summary["total_cases"], "deduplicated_cases": summary["deduplicated_cases"]}))


if __name__ == "__main__":
    main()
