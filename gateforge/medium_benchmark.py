from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .core import run_pipeline
from .proposal import load_proposal


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)


def _load_pack(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Pack file must be a JSON object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Pack file must define a non-empty 'cases' list")
    return payload


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Medium Benchmark Report",
        "",
        f"- proposal_id: `{summary.get('proposal_id')}`",
        f"- pack_id: `{summary['pack_id']}`",
        f"- total_cases: `{summary['total_cases']}`",
        f"- pass_count: `{summary['pass_count']}`",
        f"- fail_count: `{summary['fail_count']}`",
        f"- pass_rate: `{summary['pass_rate']}`",
        "",
        "## Failure Type Distribution",
        "",
    ]
    dist = summary.get("failure_type_distribution", {})
    if isinstance(dist, dict) and dist:
        for key in sorted(dist.keys()):
            lines.append(f"- {key}: `{dist[key]}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Mismatch Cases", ""])
    mismatch_cases = summary.get("mismatch_cases", [])
    if mismatch_cases:
        for c in mismatch_cases:
            lines.append(f"- `{c['name']}`")
            for m in c.get("mismatches", []):
                lines.append(f"  - `{m}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _compare_expected(evidence: dict, expected: dict) -> list[str]:
    mismatches: list[str] = []
    for k, v in expected.items():
        if evidence.get(k) != v:
            mismatches.append(f"{k}:expected={v},actual={evidence.get(k)}")
    return mismatches


def main() -> None:
    parser = argparse.ArgumentParser(description="Run medium benchmark pack and validate expected outcomes")
    parser.add_argument("--pack", default="benchmarks/medium_pack_v1.json", help="Path to medium benchmark pack JSON")
    parser.add_argument("--out-dir", default="artifacts/benchmark_medium_v1", help="Per-case outputs")
    parser.add_argument(
        "--summary-out",
        default="artifacts/benchmark_medium_v1/summary.json",
        help="Where to write benchmark summary JSON",
    )
    parser.add_argument(
        "--report-out",
        default="artifacts/benchmark_medium_v1/summary.md",
        help="Where to write benchmark summary markdown",
    )
    parser.add_argument(
        "--proposal",
        default=None,
        help="Optional proposal JSON path; proposal_id is propagated and backend mismatch is treated as failure",
    )
    args = parser.parse_args()

    pack = _load_pack(args.pack)
    pack_id = pack.get("pack_id", Path(args.pack).stem)
    cases = pack["cases"]
    proposal_id = None
    expected_backend = None
    if args.proposal:
        proposal = load_proposal(args.proposal)
        proposal_id = proposal.get("proposal_id")
        expected_backend = proposal.get("backend")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    case_results: list[dict] = []
    failure_type_distribution: dict[str, int] = {}
    for case in cases:
        name = case["name"]
        backend = case["backend"]
        script = case.get("script")
        expected = case.get("expected", {})
        slug = _slug(name)
        json_path = out_dir / f"{slug}.json"
        md_path = out_dir / f"{slug}.md"

        evidence = run_pipeline(
            backend=backend,
            out_path=str(json_path),
            report_path=str(md_path),
            script_path=script,
            proposal_id=proposal_id,
        )
        mismatches = _compare_expected(evidence, expected)
        if expected_backend is not None and backend != expected_backend:
            mismatches.append(f"proposal_backend_mismatch:expected={expected_backend},actual={backend}")
        failure_type = str(evidence.get("failure_type") or "none")
        failure_type_distribution[failure_type] = failure_type_distribution.get(failure_type, 0) + 1
        case_results.append(
            {
                "name": name,
                "proposal_id": evidence.get("proposal_id"),
                "backend": backend,
                "script": script,
                "result": "PASS" if not mismatches else "FAIL",
                "failure_type": failure_type,
                "mismatches": mismatches,
                "json_path": str(json_path),
                "report_path": str(md_path),
            }
        )

    fail_count = sum(1 for c in case_results if c["result"] == "FAIL")
    total_cases = len(case_results)
    pass_count = total_cases - fail_count
    pass_rate = round((pass_count / total_cases) if total_cases else 0.0, 4)
    mismatch_cases = [c for c in case_results if c["mismatches"]]
    summary = {
        "proposal_id": proposal_id,
        "pack_id": pack_id,
        "total_cases": total_cases,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pass_rate": pass_rate,
        "failure_type_distribution": failure_type_distribution,
        "mismatch_case_count": len(mismatch_cases),
        "mismatch_cases": [{"name": c["name"], "mismatches": c["mismatches"]} for c in mismatch_cases],
        "cases": case_results,
    }
    _write_json(args.summary_out, summary)
    _write_markdown(args.report_out, summary)
    print(
        json.dumps(
            {
                "pack_id": pack_id,
                "total_cases": total_cases,
                "pass_rate": pass_rate,
                "fail_count": fail_count,
            }
        )
    )
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
