from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Artifact Inventory v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- existing_mutant_files: `{payload.get('existing_mutant_files')}`",
        f"- missing_mutant_files: `{payload.get('missing_mutant_files')}`",
        f"- execution_coverage_ratio: `{payload.get('execution_coverage_ratio')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _top_root(path: Path) -> str:
    if path.is_absolute():
        parts = path.parts[:4]
    else:
        parts = path.parts[:3]
    return str(Path(*parts)) if parts else "."


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory mutation artifact files and execution coverage from manifest + observations")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", default=None)
    parser.add_argument("--out", default="artifacts/dataset_mutation_artifact_inventory_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    raw = _load_json(args.mutation_raw_observations)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")

    mutations = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    total = len([m for m in mutations if isinstance(m, dict)])
    existing_files = 0
    missing_files = 0
    missing_examples: list[str] = []
    by_failure_type: dict[str, int] = {}
    by_scale: dict[str, int] = {}
    root_counts: dict[str, int] = {}

    for row in mutations:
        if not isinstance(row, dict):
            continue
        mut_path = str(row.get("mutated_model_path") or "")
        p = Path(mut_path)
        if p.exists() and p.is_file():
            existing_files += 1
            root = _top_root(p)
            root_counts[root] = root_counts.get(root, 0) + 1
        else:
            missing_files += 1
            if len(missing_examples) < 10:
                missing_examples.append(mut_path)
        failure_type = str(row.get("expected_failure_type") or "unknown")
        by_failure_type[failure_type] = by_failure_type.get(failure_type, 0) + 1
        scale = str(row.get("target_scale") or "unknown")
        by_scale[scale] = by_scale.get(scale, 0) + 1

    obs = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    executed_count = len(
        [
            o
            for o in obs
            if isinstance(o, dict) and str(o.get("execution_status") or "") in {"EXECUTED", "PASS", "FAIL", "NEEDS_REVIEW"}
        ]
    )
    execution_coverage_ratio = round(executed_count / max(1, total), 4)
    existing_file_ratio = round(existing_files / max(1, total), 4)

    top_roots = sorted(root_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    alerts: list[str] = []
    if missing_files > 0:
        alerts.append("mutation_artifact_files_missing")
    if execution_coverage_ratio < 0.9 and total > 0:
        alerts.append("execution_coverage_ratio_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": total,
        "existing_mutant_files": existing_files,
        "missing_mutant_files": missing_files,
        "existing_file_ratio": existing_file_ratio,
        "execution_coverage_ratio": execution_coverage_ratio,
        "executed_count": executed_count,
        "by_failure_type": by_failure_type,
        "by_scale": by_scale,
        "artifact_roots_top": [{"root": k, "count": v} for k, v in top_roots],
        "missing_file_examples": missing_examples,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "mutation_raw_observations": args.mutation_raw_observations,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_mutations": total, "existing_mutant_files": existing_files}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
