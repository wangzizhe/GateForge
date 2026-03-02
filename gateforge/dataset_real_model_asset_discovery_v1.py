from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or default


def _extract_complexity(path: Path) -> dict:
    text = _load_text(path)
    lines = text.splitlines()
    line_count = len(lines)
    equation_count = len(re.findall(r"\bequation\b", text))
    model_block_count = len(re.findall(r"^\s*model\s+", text, flags=re.MULTILINE))
    algorithm_count = len(re.findall(r"\balgorithm\b", text))
    connect_count = len(re.findall(r"\bconnect\s*\(", text))
    complexity_score = int(line_count + equation_count * 4 + model_block_count * 8 + algorithm_count * 3 + connect_count * 2)
    return {
        "line_count": line_count,
        "equation_count": equation_count,
        "model_block_count": model_block_count,
        "algorithm_count": algorithm_count,
        "connect_count": connect_count,
        "complexity_score": complexity_score,
    }


def _infer_scale(complexity_score: int, medium_threshold: int, large_threshold: int) -> str:
    if complexity_score >= int(large_threshold):
        return "large"
    if complexity_score >= int(medium_threshold):
        return "medium"
    return "small"


def _collect_model_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".mo":
            out.append(p)
    return sorted(out)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Asset Discovery v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_candidates: `{payload.get('total_candidates')}`",
        f"- medium_candidates: `{(payload.get('scale_counts') or {}).get('medium', 0)}`",
        f"- large_candidates: `{(payload.get('scale_counts') or {}).get('large', 0)}`",
        f"- discovered_roots: `{len(payload.get('checked_roots') or [])}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Modelica assets from local/private roots and emit intake candidate catalog")
    parser.add_argument("--model-root", action="append", default=[])
    parser.add_argument("--source-name", default="private_modelica_asset_pool")
    parser.add_argument("--source-domain", default="private_modelica")
    parser.add_argument("--source-url-prefix", default="local://")
    parser.add_argument("--source-repo", default="private")
    parser.add_argument("--source-commit", default="workspace")
    parser.add_argument("--license-tag", default="Proprietary-Internal")
    parser.add_argument("--version-hint", default="workspace")
    parser.add_argument("--om-version", default="openmodelica-1.25.5")
    parser.add_argument("--min-medium-complexity-score", type=int, default=80)
    parser.add_argument("--min-large-complexity-score", type=int, default=140)
    parser.add_argument("--catalog-out", default="artifacts/dataset_real_model_asset_discovery_v1/candidate_catalog.json")
    parser.add_argument("--out", default="artifacts/dataset_real_model_asset_discovery_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    roots = [Path(x) for x in args.model_root] if args.model_root else [Path("assets_private/modelica"), Path("examples_private/modelica")]

    reasons: list[str] = []
    checked_roots: list[str] = []
    rows: list[dict] = []

    for root in roots:
        checked_roots.append(str(root))
        if not root.exists():
            reasons.append(f"root_missing:{root}")
            continue
        for p in _collect_model_files(root):
            complexity = _extract_complexity(p)
            score = int(complexity.get("complexity_score", 0))
            scale = _infer_scale(score, int(args.min_medium_complexity_score), int(args.min_large_complexity_score))
            checksum = _sha256(p)
            rel = str(p)
            model_id = f"mdl_{_slug(p.stem, default='model')}_{checksum[:8]}"
            rows.append(
                {
                    "candidate_id": model_id,
                    "model_id": model_id,
                    "name": p.stem,
                    "local_path": rel,
                    "source_url": f"{args.source_url_prefix}{rel}",
                    "source_repo": str(args.source_repo),
                    "source_commit": str(args.source_commit),
                    "domain": str(args.source_domain),
                    "version_hint": str(args.version_hint),
                    "license": str(args.license_tag),
                    "scale_hint": scale,
                    "expected_scale": scale,
                    "checksum_sha256": checksum,
                    "line_count": int(complexity.get("line_count", 0)),
                    "equation_count": int(complexity.get("equation_count", 0)),
                    "model_block_count": int(complexity.get("model_block_count", 0)),
                    "algorithm_count": int(complexity.get("algorithm_count", 0)),
                    "complexity_score": score,
                    "repro_command": f"omc {rel}",
                    "notes": "auto_discovered",
                }
            )

    dedup: dict[str, dict] = {}
    for row in rows:
        dedup[str(row.get("model_id") or "")] = row
    rows = sorted(dedup.values(), key=lambda x: str(x.get("model_id") or ""))

    scale_counts = {
        "small": len([x for x in rows if str(x.get("scale_hint") or "") == "small"]),
        "medium": len([x for x in rows if str(x.get("scale_hint") or "") == "medium"]),
        "large": len([x for x in rows if str(x.get("scale_hint") or "") == "large"]),
    }

    alerts: list[str] = []
    if not rows:
        alerts.append("no_modelica_candidates_discovered")
    if scale_counts["medium"] == 0:
        alerts.append("medium_candidates_missing")
    if scale_counts["large"] == 0:
        alerts.append("large_candidates_missing")

    status = "PASS"
    if not rows:
        status = "NEEDS_REVIEW"
    elif alerts:
        status = "NEEDS_REVIEW"

    catalog = {
        "schema_version": "real_model_candidate_catalog_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_name": str(args.source_name),
        "candidates": rows,
    }
    _write_json(args.catalog_out, catalog)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_candidates": len(rows),
        "scale_counts": scale_counts,
        "checked_roots": checked_roots,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "catalog_out": args.catalog_out,
        "sources": {
            "source_name": args.source_name,
            "source_domain": args.source_domain,
            "license_tag": args.license_tag,
            "om_version": args.om_version,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_candidates": len(rows), "large_candidates": scale_counts['large']}))


if __name__ == "__main__":
    main()
