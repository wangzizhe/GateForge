from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_") or "model"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _complexity(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    line_count = len(lines)
    equation_count = len(re.findall(r"\bequation\b", text))
    model_block_count = len(re.findall(r"^\s*model\s+", text, flags=re.MULTILINE))
    algorithm_count = len(re.findall(r"\balgorithm\b", text))
    complexity_score = int(line_count + equation_count * 4 + model_block_count * 8 + algorithm_count * 3)
    return {
        "line_count": line_count,
        "equation_count": equation_count,
        "model_block_count": model_block_count,
        "algorithm_count": algorithm_count,
        "complexity_score": complexity_score,
    }


def _scale_hint(path: Path) -> str:
    text = str(path).lower()
    stem = path.stem.lower()
    if "large" in text or "large" in stem:
        return "large"
    if "medium" in text or "medium" in stem:
        return "medium"
    return "small"


def _collect_files(model_root: Path) -> list[Path]:
    out: list[Path] = []
    for p in model_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".mo", ".mos"}:
            out.append(p)
    return sorted(out)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Library Registry v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_assets: `{payload.get('total_assets')}`",
        f"- model_assets_count: `{payload.get('model_assets_count')}`",
        f"- script_assets_count: `{payload.get('script_assets_count')}`",
        f"- medium_assets_count: `{(payload.get('scale_counts') or {}).get('medium', 0)}`",
        f"- large_assets_count: `{(payload.get('scale_counts') or {}).get('large', 0)}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Modelica library registry with checksum, complexity, and reproducibility metadata")
    parser.add_argument("--model-root", action="append", default=[])
    parser.add_argument("--source-name", default="gateforge_local_examples")
    parser.add_argument("--license-tag", default="UNKNOWN")
    parser.add_argument("--om-version", default="openmodelica-1.25.5")
    parser.add_argument("--registry-out", default="artifacts/dataset_modelica_library_registry_v1/registry.json")
    parser.add_argument("--out", default="artifacts/dataset_modelica_library_registry_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    roots = [Path(x) for x in args.model_root] if args.model_root else [Path("examples/openmodelica")]

    reasons: list[str] = []
    rows: list[dict] = []

    for root in roots:
        if not root.exists():
            reasons.append(f"model_root_missing:{root}")
            continue
        for path in _collect_files(root):
            checksum = _sha256(path)
            rel_path = str(path)
            asset_type = "model_source" if path.suffix.lower() == ".mo" else "model_script"
            scale = _scale_hint(path)
            stem = _slug(path.stem)
            model_id = f"mdl_{stem}_{checksum[:8]}"
            rows.append(
                {
                    "model_id": model_id,
                    "asset_type": asset_type,
                    "source_path": rel_path,
                    "source_name": str(args.source_name),
                    "license_tag": str(args.license_tag),
                    "checksum_sha256": checksum,
                    "suggested_scale": scale,
                    "complexity": _complexity(path),
                    "reproducibility": {
                        "om_version": str(args.om_version),
                        "repro_command": f"omc {rel_path}",
                    },
                }
            )

    dedup: dict[str, dict] = {}
    for row in rows:
        dedup[str(row.get("model_id") or "")] = row
    rows = sorted(dedup.values(), key=lambda x: str(x.get("model_id") or ""))

    model_assets_count = len([x for x in rows if x.get("asset_type") == "model_source"])
    script_assets_count = len([x for x in rows if x.get("asset_type") == "model_script"])
    scale_counts = {
        "small": len([x for x in rows if x.get("suggested_scale") == "small"]),
        "medium": len([x for x in rows if x.get("suggested_scale") == "medium"]),
        "large": len([x for x in rows if x.get("suggested_scale") == "large"]),
    }

    if not rows:
        reasons.append("no_modelica_assets_discovered")
    if scale_counts["medium"] == 0:
        reasons.append("medium_scale_assets_missing")
    if scale_counts["large"] == 0:
        reasons.append("large_scale_assets_missing")

    status = "PASS"
    if "no_modelica_assets_discovered" in reasons:
        status = "FAIL"
    elif reasons:
        status = "NEEDS_REVIEW"

    registry = {
        "schema_version": "modelica_library_registry_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "models": rows,
    }
    _write_json(args.registry_out, registry)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "registry_path": args.registry_out,
        "schema_version": "modelica_library_registry_v1",
        "total_assets": len(rows),
        "model_assets_count": model_assets_count,
        "script_assets_count": script_assets_count,
        "scale_counts": scale_counts,
        "reasons": sorted(set(reasons)),
        "sources": {"model_roots": [str(x) for x in roots]},
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_assets": len(rows)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
