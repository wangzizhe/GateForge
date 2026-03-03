from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict | list:
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


def _slug(v: object, *, default: str = "x") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or default


def _extract_sources(raw: dict | list) -> list[dict]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        rows = raw.get("sources")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _count_mo_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return len([p for p in path.rglob("*.mo") if p.is_file()])


def _resolve_root(source: dict, cache_root: Path) -> Path | None:
    mode = str(source.get("mode") or "").strip().lower()
    if mode == "local":
        local_path = str(source.get("local_path") or "").strip()
        if not local_path:
            return None
        root = Path(local_path)
        return root if root.exists() else None

    source_id = _slug(source.get("source_id"), default="")
    if not source_id:
        return None
    root = cache_root / source_id
    return root if root.exists() else None


def _candidate_package_roots(source: dict, root: Path) -> list[str]:
    base_roots = source.get("package_roots") if isinstance(source.get("package_roots"), list) else []
    rows: list[str] = []
    for rel in base_roots:
        rel_text = str(rel or "").strip().strip("/")
        if not rel_text:
            continue
        rows.append(rel_text)
        base = root / rel_text
        if not base.exists() or not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir():
                rows.append(str(child.relative_to(root)).replace("\\", "/"))
    if not rows:
        for child in sorted(root.iterdir()):
            if child.is_dir():
                rows.append(str(child.relative_to(root)).replace("\\", "/"))
    dedup: dict[str, str] = {}
    for r in rows:
        dedup[r] = r
    return sorted(dedup.values())


def _make_shard_source(*, base: dict, root: Path, rel_path: str) -> dict:
    source_id = _slug(base.get("source_id"), default="source")
    shard_id = f"{source_id}_shard_{_slug(rel_path, default='pkg')}"
    scale_hint = str(base.get("scale_hint") or "medium").strip().lower()
    if scale_hint not in {"small", "medium", "large"}:
        scale_hint = "medium"
    return {
        "source_id": shard_id,
        "mode": "local",
        "local_path": str(root),
        "license": str(base.get("license") or base.get("license_tag") or "BSD-3-Clause"),
        "scale_hint": scale_hint,
        "package_roots": [rel_path],
        "origin_source_id": str(base.get("source_id") or ""),
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Source Manifest Expander v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- base_sources: `{payload.get('base_sources')}`",
        f"- expanded_sources: `{payload.get('expanded_sources')}`",
        f"- added_sources_count: `{payload.get('added_sources_count')}`",
        f"- scanned_sources: `{payload.get('scanned_sources')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand Modelica source manifest with local package shards to scale real-model intake")
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--source-cache-root", default="assets_private/modelica_sources")
    parser.add_argument("--max-shards-per-source", type=int, default=6)
    parser.add_argument("--min-mo-files-per-shard", type=int, default=8)
    parser.add_argument("--out", default="artifacts/dataset_modelica_source_manifest_expander_v1/expanded_manifest.json")
    parser.add_argument("--summary-out", default="artifacts/dataset_modelica_source_manifest_expander_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    raw = _load_json(args.source_manifest)
    base_sources = _extract_sources(raw)

    reasons: list[str] = []
    alerts: list[str] = []
    if not base_sources:
        reasons.append("source_manifest_empty")

    cache_root = Path(args.source_cache_root)
    expanded_sources = list(base_sources)
    scanned_sources = 0
    added_sources: list[dict] = []
    scanned_details: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for src in base_sources:
        src_id = str(src.get("source_id") or "")
        root = _resolve_root(src, cache_root)
        if root is None:
            scanned_details.append({"source_id": src_id, "status": "SKIPPED", "reason": "source_root_unavailable"})
            continue
        scanned_sources += 1
        candidate_roots = _candidate_package_roots(src, root)
        added_for_source = 0
        for rel in candidate_roots:
            if added_for_source >= int(args.max_shards_per_source):
                break
            abs_path = root / rel
            mo_count = _count_mo_files(abs_path)
            if mo_count < int(args.min_mo_files_per_shard):
                continue
            key = (str(root), rel)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            shard = _make_shard_source(base=src, root=root, rel_path=rel)
            expanded_sources.append(shard)
            added_sources.append(
                {
                    "origin_source_id": src_id,
                    "source_id": shard.get("source_id"),
                    "local_path": str(root),
                    "package_root": rel,
                    "mo_file_count": mo_count,
                }
            )
            added_for_source += 1
        scanned_details.append(
            {
                "source_id": src_id,
                "status": "PASS",
                "root": str(root),
                "candidate_package_roots": len(candidate_roots),
                "added_shards": added_for_source,
            }
        )

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif not added_sources:
        status = "NEEDS_REVIEW"
        alerts.append("no_shards_added")

    expanded_manifest = {
        "schema_version": "modelica_open_source_seed_sources_v1_expanded",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_manifest_path": args.source_manifest,
        "source_cache_root": args.source_cache_root,
        "sources": expanded_sources,
    }
    _write_json(args.out, expanded_manifest)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "base_sources": len(base_sources),
        "expanded_sources": len(expanded_sources),
        "added_sources_count": len(added_sources),
        "scanned_sources": scanned_sources,
        "added_sources": added_sources,
        "scanned_details": scanned_details,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "artifacts": {
            "expanded_manifest": args.out,
        },
        "sources": {
            "source_manifest": args.source_manifest,
        },
    }

    _write_json(args.summary_out, summary)
    _write_markdown(args.report_out or _default_md_path(args.summary_out), summary)
    print(json.dumps({"status": status, "base_sources": len(base_sources), "added_sources_count": len(added_sources)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
