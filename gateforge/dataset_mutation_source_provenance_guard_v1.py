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


def _ratio_pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((num / den) * 100.0, 4)


def _path_in_roots(p: Path, roots: list[Path]) -> bool:
    if not roots:
        return True
    for root in roots:
        try:
            p.resolve().relative_to(root.resolve())
            return True
        except Exception:
            continue
    return False


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Source Provenance Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- with_source_path_count: `{payload.get('with_source_path_count')}`",
        f"- existing_source_path_ratio_pct: `{payload.get('existing_source_path_ratio_pct')}`",
        f"- allowed_root_ratio_pct: `{payload.get('allowed_root_ratio_pct')}`",
        f"- registry_match_ratio_pct: `{payload.get('registry_match_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard mutation source-model provenance authenticity")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--executable-registry", default=None)
    parser.add_argument("--allowed-model-roots", default="")
    parser.add_argument("--min-existing-source-path-ratio-pct", type=float, default=95.0)
    parser.add_argument("--min-allowed-root-ratio-pct", type=float, default=95.0)
    parser.add_argument("--min-registry-match-ratio-pct", type=float, default=80.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_source_provenance_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    registry = _load_json(args.executable_registry)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")

    mutation_rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    mutations = [row for row in mutation_rows if isinstance(row, dict)]
    if manifest and not mutations:
        reasons.append("mutation_manifest_empty")

    allowed_roots: list[Path] = []
    for token in str(args.allowed_model_roots).replace(":", ",").split(","):
        text = token.strip()
        if text:
            allowed_roots.append(Path(text))

    registry_rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    registry_model_ids = {
        str(row.get("model_id") or "").strip()
        for row in registry_rows
        if isinstance(row, dict) and str(row.get("model_id") or "").strip()
    }

    total_mutations = len(mutations)
    with_source_path_count = 0
    existing_source_path_count = 0
    allowed_root_count = 0
    registry_match_count = 0
    unique_source_models: set[str] = set()

    for row in mutations:
        model_id = str(row.get("target_model_id") or row.get("model_id") or "").strip()
        if model_id:
            unique_source_models.add(model_id)
            if model_id in registry_model_ids:
                registry_match_count += 1

        source_path = str(row.get("source_model_path") or row.get("model_path") or "").strip()
        if not source_path:
            continue
        with_source_path_count += 1
        source = Path(source_path)
        if source.exists():
            existing_source_path_count += 1
        if _path_in_roots(source, allowed_roots):
            allowed_root_count += 1

    existing_source_path_ratio_pct = _ratio_pct(existing_source_path_count, with_source_path_count)
    allowed_root_ratio_pct = _ratio_pct(allowed_root_count, with_source_path_count)
    registry_match_ratio_pct = _ratio_pct(registry_match_count, total_mutations)

    alerts: list[str] = []
    if with_source_path_count == 0:
        alerts.append("mutation_source_path_missing")
    if existing_source_path_ratio_pct < float(args.min_existing_source_path_ratio_pct):
        alerts.append("existing_source_path_ratio_below_threshold")
    if allowed_root_ratio_pct < float(args.min_allowed_root_ratio_pct):
        alerts.append("allowed_root_ratio_below_threshold")
    if registry_model_ids and registry_match_ratio_pct < float(args.min_registry_match_ratio_pct):
        alerts.append("registry_match_ratio_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": total_mutations,
        "with_source_path_count": with_source_path_count,
        "existing_source_path_count": existing_source_path_count,
        "existing_source_path_ratio_pct": existing_source_path_ratio_pct,
        "allowed_root_count": allowed_root_count,
        "allowed_root_ratio_pct": allowed_root_ratio_pct,
        "registry_match_count": registry_match_count,
        "registry_match_ratio_pct": registry_match_ratio_pct,
        "unique_source_models": len(unique_source_models),
        "allowed_model_roots": [str(x) for x in allowed_roots],
        "thresholds": {
            "min_existing_source_path_ratio_pct": float(args.min_existing_source_path_ratio_pct),
            "min_allowed_root_ratio_pct": float(args.min_allowed_root_ratio_pct),
            "min_registry_match_ratio_pct": float(args.min_registry_match_ratio_pct),
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "executable_registry": args.executable_registry,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "existing_source_path_ratio_pct": existing_source_path_ratio_pct,
                "allowed_root_ratio_pct": allowed_root_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
