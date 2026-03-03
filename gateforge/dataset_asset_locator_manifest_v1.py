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


def _count_files_under(root: Path, suffix: str) -> int:
    if not root.exists() or not root.is_dir():
        return 0
    return len([p for p in root.rglob(f"*{suffix}") if p.is_file()])


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Asset Locator Manifest v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- model_root_count: `{payload.get('model_root_count')}`",
        f"- mutant_root_count: `{payload.get('mutant_root_count')}`",
        f"- total_model_files: `{payload.get('total_model_files')}`",
        f"- total_mutant_files: `{payload.get('total_mutant_files')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a locator manifest for model and mutant artifacts")
    parser.add_argument("--executable-registry", required=True)
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--out", default="artifacts/dataset_asset_locator_manifest_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.executable_registry)
    mutation_manifest = _load_json(args.mutation_manifest)
    reasons: list[str] = []
    if not registry:
        reasons.append("executable_registry_missing")
    if not mutation_manifest:
        reasons.append("mutation_manifest_missing")

    model_rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    mutation_rows = mutation_manifest.get("mutations") if isinstance(mutation_manifest.get("mutations"), list) else []

    model_roots: dict[str, int] = {}
    mutant_roots: dict[str, int] = {}
    for row in model_rows:
        if not isinstance(row, dict):
            continue
        source_path = str(row.get("source_path") or "")
        if not source_path:
            continue
        parent = str(Path(source_path).parent)
        model_roots[parent] = model_roots.get(parent, 0) + 1
    for row in mutation_rows:
        if not isinstance(row, dict):
            continue
        mut_path = str(row.get("mutated_model_path") or "")
        if not mut_path:
            continue
        parent = str(Path(mut_path).parent)
        mutant_roots[parent] = mutant_roots.get(parent, 0) + 1

    model_root_rows = sorted(model_roots.items(), key=lambda kv: (-kv[1], kv[0]))
    mutant_root_rows = sorted(mutant_roots.items(), key=lambda kv: (-kv[1], kv[0]))

    model_root_details: list[dict] = []
    total_model_files = 0
    for root, ref_count in model_root_rows[:50]:
        p = Path(root)
        mo_count = _count_files_under(p, ".mo")
        total_model_files += mo_count
        model_root_details.append(
            {
                "root": root,
                "referenced_models": ref_count,
                "mo_files_detected": mo_count,
            }
        )

    mutant_root_details: list[dict] = []
    total_mutant_files = 0
    for root, ref_count in mutant_root_rows[:50]:
        p = Path(root)
        mo_count = _count_files_under(p, ".mo")
        total_mutant_files += mo_count
        mutant_root_details.append(
            {
                "root": root,
                "referenced_mutants": ref_count,
                "mo_files_detected": mo_count,
            }
        )

    alerts: list[str] = []
    if not model_root_rows:
        alerts.append("no_model_roots_detected")
    if not mutant_root_rows:
        alerts.append("no_mutant_roots_detected")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "model_root_count": len(model_root_rows),
        "mutant_root_count": len(mutant_root_rows),
        "total_model_files": total_model_files,
        "total_mutant_files": total_mutant_files,
        "model_roots": model_root_details,
        "mutant_roots": mutant_root_details,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "executable_registry": args.executable_registry,
            "mutation_manifest": args.mutation_manifest,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "model_root_count": len(model_root_rows), "mutant_root_count": len(mutant_root_rows)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
