from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _complexity(path: Path) -> dict:
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


def _infer_scale(score: int, *, medium_threshold: int, large_threshold: int) -> str:
    if score >= int(large_threshold):
        return "large"
    if score >= int(medium_threshold):
        return "medium"
    return "small"


def _scale_rank(scale: str) -> int:
    s = str(scale or "").strip().lower()
    if s == "large":
        return 3
    if s == "medium":
        return 2
    return 1


def _effective_scale(manifest_scale: str, inferred_scale: str) -> str:
    return manifest_scale if _scale_rank(manifest_scale) >= _scale_rank(inferred_scale) else inferred_scale


def _run_git(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = (proc.stdout or "") + (proc.stderr or "")
    return int(proc.returncode), out.strip()


def _resolve_repo_root(source: dict, *, cache_root: Path, execute_fetch: bool) -> tuple[Path | None, dict]:
    meta = {"status": "UNKNOWN", "notes": []}
    mode = str(source.get("mode") or "git").strip().lower()
    source_id = _slug(source.get("source_id"), default="source")

    if mode == "local":
        local_path = str(source.get("local_path") or "").strip()
        if not local_path:
            meta["status"] = "REJECT"
            meta["notes"].append("local_path_missing")
            return None, meta
        root = Path(local_path).expanduser()
        if not root.exists():
            meta["status"] = "NEEDS_REVIEW"
            meta["notes"].append(f"local_path_missing:{root}")
            return None, meta
        meta["status"] = "PASS"
        meta["notes"].append("local_source_resolved")
        return root, meta

    repo_url = str(source.get("repo_url") or "").strip()
    ref = str(source.get("ref") or "").strip()
    if not repo_url:
        meta["status"] = "REJECT"
        meta["notes"].append("repo_url_missing")
        return None, meta

    repo_root = cache_root / source_id
    if repo_root.exists():
        meta["status"] = "PASS"
        meta["notes"].append("repo_cache_hit")
        return repo_root, meta

    if not execute_fetch:
        meta["status"] = "NEEDS_REVIEW"
        meta["notes"].append("repo_missing_fetch_required")
        return None, meta

    repo_root.parent.mkdir(parents=True, exist_ok=True)
    rc, out = _run_git(["git", "clone", "--depth", "1", repo_url, str(repo_root)])
    if rc != 0:
        meta["status"] = "NEEDS_REVIEW"
        meta["notes"].append("git_clone_failed")
        meta["notes"].append(out[-800:] if out else "git_clone_failed_no_output")
        return None, meta

    if ref:
        rc, out = _run_git(["git", "-C", str(repo_root), "checkout", ref])
        if rc != 0:
            meta["status"] = "NEEDS_REVIEW"
            meta["notes"].append("git_checkout_failed")
            meta["notes"].append(out[-800:] if out else "git_checkout_failed_no_output")
            return None, meta

    meta["status"] = "PASS"
    meta["notes"].append("repo_fetched")
    return repo_root, meta


def _collect_mo_files(repo_root: Path, package_roots: list[str], max_models_per_source: int) -> list[Path]:
    scan_roots: list[Path] = []
    if package_roots:
        for rel in package_roots:
            p = (repo_root / rel).resolve()
            if p.exists() and p.is_dir():
                scan_roots.append(p)
    if not scan_roots:
        scan_roots = [repo_root]

    rows: list[Path] = []
    for root in scan_roots:
        for p in root.rglob("*.mo"):
            if p.is_file():
                rows.append(p)
    rows = sorted(set(rows))
    if int(max_models_per_source) > 0:
        return rows[: int(max_models_per_source)]
    return rows


def _source_url(source: dict, rel_path: str) -> str:
    mode = str(source.get("mode") or "git").strip().lower()
    if mode == "git":
        repo_url = str(source.get("repo_url") or "").strip().rstrip("/")
        ref = str(source.get("ref") or "").strip()
        if repo_url and ref:
            return f"{repo_url}/blob/{ref}/{rel_path}"
        if repo_url:
            return f"{repo_url}/blob/main/{rel_path}"
    return f"local://{rel_path}"


def _extract_sources(raw: dict | list) -> list[dict]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        rows = raw.get("sources")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _to_candidate(
    *,
    source: dict,
    source_id: str,
    repo_root: Path,
    model_path: Path,
    export_root: Path,
    source_name: str,
    medium_threshold: int,
    large_threshold: int,
) -> dict:
    repo_root_resolved = repo_root.resolve()
    model_path_resolved = model_path.resolve()
    try:
        rel_in_repo = str(model_path_resolved.relative_to(repo_root_resolved)).replace("\\", "/")
    except ValueError:
        rel_in_repo = str(model_path.name)
    export_path = export_root / source_id / rel_in_repo
    export_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(model_path, export_path)

    checksum = _sha256(export_path)
    stats = _complexity(export_path)
    score = int(stats.get("complexity_score", 0))
    manifest_scale = str(source.get("scale_hint") or "small").strip().lower()
    if manifest_scale not in {"small", "medium", "large"}:
        manifest_scale = "small"
    inferred_scale = _infer_scale(score, medium_threshold=medium_threshold, large_threshold=large_threshold)
    scale = _effective_scale(manifest_scale, inferred_scale)

    stem = _slug(model_path.stem, default="model")
    model_id = f"osm_{source_id}_{stem}_{checksum[:8]}"

    return {
        "candidate_id": model_id,
        "model_id": model_id,
        "name": model_path.stem,
        "local_path": str(export_path),
        "source_url": _source_url(source, rel_in_repo),
        "source_repo": str(source.get("repo_url") or source.get("local_path") or ""),
        "source_commit": str(source.get("ref") or ""),
        "license": str(source.get("license") or source.get("license_tag") or "UNKNOWN"),
        "scale_hint": scale,
        "expected_scale": scale,
        "checksum_sha256": checksum,
        "line_count": int(stats.get("line_count", 0)),
        "equation_count": int(stats.get("equation_count", 0)),
        "model_block_count": int(stats.get("model_block_count", 0)),
        "algorithm_count": int(stats.get("algorithm_count", 0)),
        "complexity_score": score,
        "repro_command": f"omc {export_path}",
        "domain": "physical_ai",
        "version_hint": str(source.get("ref") or "workspace"),
        "source_name": source_name,
        "notes": "open_source_harvested",
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Open-Source Harvest v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_sources: `{payload.get('total_sources')}`",
        f"- processed_sources: `{payload.get('processed_sources')}`",
        f"- total_candidates: `{payload.get('total_candidates')}`",
        f"- exported_models: `{payload.get('exported_models')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest real .mo assets from local/git open-source Modelica sources")
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--source-name", default="open_source_modelica_harvest_v1")
    parser.add_argument("--source-cache-root", default="assets_private/modelica_sources")
    parser.add_argument("--export-root", default="assets_private/modelica/open_source")
    parser.add_argument("--execute-fetch", action="store_true")
    parser.add_argument("--max-models-per-source", type=int, default=120)
    parser.add_argument("--min-medium-complexity-score", type=int, default=80)
    parser.add_argument("--min-large-complexity-score", type=int, default=140)
    parser.add_argument("--catalog-out", default="artifacts/dataset_modelica_open_source_harvest_v1/candidate_catalog.json")
    parser.add_argument("--out", default="artifacts/dataset_modelica_open_source_harvest_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    raw = _load_json(args.source_manifest)
    sources = _extract_sources(raw)

    reasons: list[str] = []
    alerts: list[str] = []
    if not sources:
        reasons.append("source_manifest_empty")

    cache_root = Path(args.source_cache_root)
    export_root = Path(args.export_root)
    export_root.mkdir(parents=True, exist_ok=True)

    harvested: list[dict] = []
    source_results: list[dict] = []
    processed_sources = 0
    fetched_sources = 0

    for src in sources:
        source_id = _slug(src.get("source_id"), default=f"source_{len(source_results) + 1}")
        repo_root, meta = _resolve_repo_root(src, cache_root=cache_root, execute_fetch=bool(args.execute_fetch))
        mode = str(src.get("mode") or "git").strip().lower()

        row = {
            "source_id": source_id,
            "mode": mode,
            "status": str(meta.get("status") or "UNKNOWN"),
            "notes": meta.get("notes") if isinstance(meta.get("notes"), list) else [],
            "repo_url": str(src.get("repo_url") or ""),
            "local_path": str(src.get("local_path") or ""),
            "ref": str(src.get("ref") or ""),
            "harvested_count": 0,
        }
        source_results.append(row)

        if row["status"] == "PASS":
            processed_sources += 1
            notes = row.get("notes") if isinstance(row.get("notes"), list) else []
            if "repo_fetched" in notes:
                fetched_sources += 1

        if repo_root is None:
            alerts.append(f"source_unavailable:{source_id}")
            continue

        package_roots = src.get("package_roots") if isinstance(src.get("package_roots"), list) else []
        package_roots = [str(x) for x in package_roots if str(x).strip()]
        mo_files = _collect_mo_files(repo_root, package_roots, int(args.max_models_per_source))
        if not mo_files:
            alerts.append(f"source_empty:{source_id}")
            continue

        for model_path in mo_files:
            harvested.append(
                _to_candidate(
                    source=src,
                    source_id=source_id,
                    repo_root=repo_root,
                    model_path=model_path,
                    export_root=export_root,
                    source_name=str(args.source_name),
                    medium_threshold=int(args.min_medium_complexity_score),
                    large_threshold=int(args.min_large_complexity_score),
                )
            )
        row["harvested_count"] = len(mo_files)

    dedup: dict[str, dict] = {}
    for row in harvested:
        dedup[str(row.get("model_id") or "")] = row
    harvested = sorted(dedup.values(), key=lambda x: str(x.get("model_id") or ""))

    scale_counts = {
        "small": len([x for x in harvested if str(x.get("scale_hint") or "") == "small"]),
        "medium": len([x for x in harvested if str(x.get("scale_hint") or "") == "medium"]),
        "large": len([x for x in harvested if str(x.get("scale_hint") or "") == "large"]),
    }

    if len(harvested) == 0:
        alerts.append("no_modelica_candidates_harvested")
    if scale_counts["medium"] == 0:
        alerts.append("medium_scale_candidates_missing")
    if scale_counts["large"] == 0:
        alerts.append("large_scale_candidates_missing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    catalog = {
        "schema_version": "modelica_open_source_candidate_catalog_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_name": str(args.source_name),
        "candidates": harvested,
    }
    _write_json(args.catalog_out, catalog)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_manifest": args.source_manifest,
        "total_sources": len(sources),
        "processed_sources": processed_sources,
        "fetched_sources": fetched_sources,
        "total_candidates": len(harvested),
        "exported_models": len(harvested),
        "scale_counts": scale_counts,
        "source_results": source_results,
        "catalog_out": args.catalog_out,
        "alerts": sorted(set(alerts)),
        "reasons": sorted(set(reasons)),
        "sources": {
            "source_cache_root": str(cache_root),
            "export_root": str(export_root),
            "execute_fetch": bool(args.execute_fetch),
            "max_models_per_source": int(args.max_models_per_source),
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_sources": len(sources),
                "processed_sources": processed_sources,
                "total_candidates": len(harvested),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
