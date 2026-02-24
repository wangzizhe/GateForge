from __future__ import annotations

import argparse
import json
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Metrics",
        "",
        f"- pack_id: `{payload.get('pack_id')}`",
        f"- pack_version: `{payload.get('pack_version')}`",
        f"- backend: `{payload.get('backend')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        f"- gate_pass_rate: `{payload.get('gate_pass_rate')}`",
        f"- expected_vs_actual_match_rate: `{payload.get('expected_vs_actual_match_rate')}`",
        "",
        "## Failure Type Distribution",
        "",
    ]
    dist = payload.get("failure_type_distribution", {})
    if isinstance(dist, dict) and dist:
        for key in sorted(dist.keys()):
            lines.append(f"- {key}: `{dist[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _compute(manifest: dict, summary: dict) -> dict:
    manifest_cases = manifest.get("cases", [])
    summary_cases = summary.get("cases", [])
    expected_by_name = {}
    actual_by_name = {}
    for row in manifest_cases if isinstance(manifest_cases, list) else []:
        if isinstance(row, dict):
            expected_by_name[str(row.get("name"))] = row.get("expected") or {}
    for row in summary_cases if isinstance(summary_cases, list) else []:
        if isinstance(row, dict):
            actual_by_name[str(row.get("name"))] = row

    matched = 0
    total = 0
    for name, expected in expected_by_name.items():
        actual = actual_by_name.get(name) or {}
        total += 1
        if (
            actual.get("failure_type") == expected.get("failure_type")
            and actual.get("result") == "PASS"
        ):
            matched += 1

    failure_dist: dict[str, int] = {}
    for row in summary_cases if isinstance(summary_cases, list) else []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("failure_type") or "unknown")
        failure_dist[key] = failure_dist.get(key, 0) + 1

    total_cases = int(summary.get("total_cases", 0) or 0)
    pass_count = int(summary.get("pass_count", 0) or 0)
    return {
        "pack_id": manifest.get("pack_id"),
        "pack_version": manifest.get("pack_version"),
        "backend": manifest.get("backend"),
        "total_cases": total_cases,
        "gate_pass_rate": round((pass_count / max(1, total_cases)), 4),
        "expected_vs_actual_match_rate": round((matched / max(1, total)), 4),
        "failure_type_distribution": failure_dist,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute mutation benchmark metrics from manifest + summary")
    parser.add_argument("--manifest", required=True, help="Mutation manifest JSON path")
    parser.add_argument("--summary", required=True, help="Benchmark summary JSON path")
    parser.add_argument("--out", default="artifacts/mutation_pack/metrics.json", help="Metrics JSON output path")
    parser.add_argument("--report-out", default=None, help="Metrics markdown output path")
    args = parser.parse_args()

    payload = _compute(_load_json(args.manifest), _load_json(args.summary))
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "pack_id": payload.get("pack_id"),
                "pack_version": payload.get("pack_version"),
                "total_cases": payload.get("total_cases"),
                "expected_vs_actual_match_rate": payload.get("expected_vs_actual_match_rate"),
            }
        )
    )


if __name__ == "__main__":
    main()
