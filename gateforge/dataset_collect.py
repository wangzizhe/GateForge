from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _is_benchmark_summary(payload: dict) -> bool:
    return (
        isinstance(payload.get("pack_id"), str)
        and isinstance(payload.get("total_cases"), int)
        and isinstance(payload.get("cases"), list)
        and "pass_count" in payload
        and "fail_count" in payload
    )


def _is_run_summary(payload: dict) -> bool:
    return isinstance(payload.get("proposal_id"), str) and isinstance(payload.get("smoke_executed"), bool)


def _is_autopilot_summary(payload: dict) -> bool:
    return (
        isinstance(payload.get("intent_path"), str)
        and "planner_exit_code" in payload
        and "agent_run_exit_code" in payload
    )


def _classify(path: Path, payload: dict) -> str | None:
    if _is_autopilot_summary(payload):
        return "autopilot"
    if _is_run_summary(payload):
        return "run"
    if _is_benchmark_summary(payload):
        if "mutation" in str(payload.get("pack_id", "")).lower() or "mutation" in str(path).lower():
            return "mutation"
        return "benchmark"
    return None


def collect_summaries(root: str, pattern: str = "**/*.json") -> dict:
    root_path = Path(root)
    benchmark: list[str] = []
    mutation: list[str] = []
    run: list[str] = []
    autopilot: list[str] = []
    unknown: list[str] = []

    for path in sorted(root_path.glob(pattern)):
        if not path.is_file():
            continue
        payload = _load_json(path)
        if payload is None:
            continue
        kind = _classify(path, payload)
        txt = str(path)
        if kind == "benchmark":
            benchmark.append(txt)
        elif kind == "mutation":
            mutation.append(txt)
        elif kind == "run":
            run.append(txt)
        elif kind == "autopilot":
            autopilot.append(txt)
        else:
            unknown.append(txt)

    return {
        "root": str(root_path),
        "pattern": pattern,
        "benchmark_summary_paths": benchmark,
        "mutation_summary_paths": mutation,
        "run_summary_paths": run,
        "autopilot_summary_paths": autopilot,
        "unknown_json_paths": unknown,
        "counts": {
            "benchmark_summary_count": len(benchmark),
            "mutation_summary_count": len(mutation),
            "run_summary_count": len(run),
            "autopilot_summary_count": len(autopilot),
            "unknown_json_count": len(unknown),
        },
    }


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    counts = payload.get("counts", {})
    lines = [
        "# GateForge Dataset Collect Summary",
        "",
        f"- root: `{payload.get('root')}`",
        f"- pattern: `{payload.get('pattern')}`",
        f"- benchmark_summary_count: `{counts.get('benchmark_summary_count')}`",
        f"- mutation_summary_count: `{counts.get('mutation_summary_count')}`",
        f"- run_summary_count: `{counts.get('run_summary_count')}`",
        f"- autopilot_summary_count: `{counts.get('autopilot_summary_count')}`",
        f"- unknown_json_count: `{counts.get('unknown_json_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect dataset-build input summaries from artifacts tree")
    parser.add_argument("--root", default="artifacts", help="Root directory to scan")
    parser.add_argument("--pattern", default="**/*.json", help="Glob pattern under root")
    parser.add_argument("--out", default="artifacts/dataset_collect/summary.json", help="Output summary JSON")
    parser.add_argument("--report-out", default=None, help="Output markdown path")
    args = parser.parse_args()

    payload = collect_summaries(root=args.root, pattern=args.pattern)
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps(payload["counts"]))


if __name__ == "__main__":
    main()
