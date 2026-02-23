from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _normalize_key(mismatch: str) -> str:
    if ":" not in mismatch:
        return mismatch
    return mismatch.split(":", 1)[0]


def _recommendations(counter: Counter[str]) -> list[dict]:
    recs: list[dict] = []
    for key, count in counter.most_common():
        if key == "failure_type":
            msg = "Check failure taxonomy mapping and parser robustness first."
            prio = "P0"
        elif key in {"gate", "status"}:
            msg = "Check gate decision logic and status normalization."
            prio = "P0"
        elif key in {"check_ok", "simulate_ok"}:
            msg = "Check OpenModelica log signal extraction for check/simulate flags."
            prio = "P1"
        elif key.startswith("proposal_"):
            msg = "Check proposal/benchmark backend and model-script alignment."
            prio = "P1"
        else:
            msg = "Inspect evidence schema drift and expected-field configuration."
            prio = "P2"
        recs.append(
            {
                "mismatch_key": key,
                "count": count,
                "priority": prio,
                "recommendation": msg,
            }
        )
    return recs


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Medium Benchmark Analysis",
        "",
        f"- pack_id: `{payload.get('pack_id')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        f"- mismatch_case_count: `{payload.get('mismatch_case_count')}`",
        "",
        "## Mismatch Keys",
        "",
    ]
    keys = payload.get("mismatch_key_counts", {})
    if isinstance(keys, dict) and keys:
        for key in sorted(keys):
            lines.append(f"- {key}: `{keys[key]}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Recommendations", ""])
    recs = payload.get("recommendations", [])
    if isinstance(recs, list) and recs:
        for row in recs:
            lines.append(
                f"- `{row.get('priority')}` `{row.get('mismatch_key')}` ({row.get('count')}): {row.get('recommendation')}"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze medium benchmark mismatches and rank debugging priorities")
    parser.add_argument(
        "--summary",
        default="artifacts/benchmark_medium_v1/summary.json",
        help="medium_benchmark summary JSON",
    )
    parser.add_argument(
        "--out",
        default="artifacts/benchmark_medium_v1/analysis.json",
        help="analysis JSON output path",
    )
    parser.add_argument("--report-out", default=None, help="analysis markdown output path")
    args = parser.parse_args()

    summary = _load_json(args.summary)
    mismatch_cases = summary.get("mismatch_cases", [])
    key_counter: Counter[str] = Counter()
    case_map: dict[str, list[str]] = defaultdict(list)
    for case in mismatch_cases if isinstance(mismatch_cases, list) else []:
        name = str(case.get("name") or "unknown_case")
        mismatches = case.get("mismatches", [])
        if not isinstance(mismatches, list):
            continue
        for mismatch in mismatches:
            key = _normalize_key(str(mismatch))
            key_counter[key] += 1
            case_map[key].append(name)

    payload = {
        "pack_id": summary.get("pack_id"),
        "total_cases": summary.get("total_cases"),
        "mismatch_case_count": summary.get("mismatch_case_count"),
        "mismatch_key_counts": dict(key_counter),
        "mismatch_key_case_examples": {k: sorted(set(v))[:5] for k, v in case_map.items()},
        "recommendations": _recommendations(key_counter),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"mismatch_case_count": payload["mismatch_case_count"], "top_keys": list(key_counter.keys())[:3]}))


if __name__ == "__main__":
    main()
