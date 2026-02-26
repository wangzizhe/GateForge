from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SCALES = ["small", "medium", "large"]


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


def _canonical_base(name: str) -> str:
    text = name.lower()
    text = re.sub(r"\b(small|medium|large)\b", "", text)
    text = re.sub(r"(_small|_medium|_large)", "", text)
    text = re.sub(r"(_short|_long)", "", text)
    text = re.sub(r"[0-9]+", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "family"


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _family_completeness(scale_map: dict[str, str]) -> str:
    available = {k for k, v in scale_map.items() if v}
    if {"small", "medium", "large"}.issubset(available):
        return "full"
    if {"medium", "large"}.issubset(available):
        return "growth_ready"
    if available:
        return "partial"
    return "empty"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Model Family Generator v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_families: `{payload.get('total_families')}`",
        f"- full_families: `{payload.get('full_families')}`",
        f"- growth_ready_families: `{payload.get('growth_ready_families')}`",
        "",
        "## Top Families",
        "",
    ]
    families = payload.get("families") if isinstance(payload.get("families"), list) else []
    for fam in families[:15]:
        lines.append(
            f"- `{fam.get('family_id')}` base=`{fam.get('canonical_base')}` completeness=`{fam.get('completeness')}` members=`{fam.get('member_count')}`"
        )
    if not families:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate model families from modelica library registry")
    parser.add_argument("--modelica-library-registry", required=True)
    parser.add_argument("--min-member-count", type=int, default=2)
    parser.add_argument("--manifest-out", default="artifacts/dataset_model_family_generator_v1/manifest.json")
    parser.add_argument("--out", default="artifacts/dataset_model_family_generator_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.modelica_library_registry)
    models = _extract_models(registry)

    reasons: list[str] = []
    if not registry:
        reasons.append("modelica_library_registry_missing")
    if not models:
        reasons.append("registry_models_missing")

    grouped: dict[str, list[dict]] = {}
    for row in models:
        path = str(row.get("source_path") or "")
        stem = Path(path).stem or str(row.get("model_id") or "")
        base = _canonical_base(stem)
        grouped.setdefault(base, []).append(row)

    families: list[dict] = []
    min_count = int(args.min_member_count)

    for base, rows in sorted(grouped.items(), key=lambda x: x[0]):
        if len(rows) < min_count:
            continue
        rows_sorted = sorted(rows, key=lambda x: str(x.get("model_id") or ""))
        scale_map = {"small": "", "medium": "", "large": ""}
        for row in rows_sorted:
            scale = str(row.get("suggested_scale") or "")
            if scale in scale_map and not scale_map[scale]:
                scale_map[scale] = str(row.get("model_id") or "")

        family = {
            "family_id": f"family_{base}",
            "canonical_base": base,
            "member_count": len(rows_sorted),
            "member_model_ids": [str(x.get("model_id") or "") for x in rows_sorted],
            "scale_map": scale_map,
            "completeness": _family_completeness(scale_map),
        }
        families.append(family)

    full_families = len([x for x in families if x.get("completeness") == "full"])
    growth_ready = len([x for x in families if x.get("completeness") == "growth_ready"])

    if not families:
        reasons.append("no_families_generated")
    if full_families == 0:
        reasons.append("no_full_scale_family")

    status = "PASS"
    if "modelica_library_registry_missing" in reasons or "registry_models_missing" in reasons:
        status = "FAIL"
    elif reasons:
        status = "NEEDS_REVIEW"

    manifest = {
        "schema_version": "model_family_manifest_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "families": families,
    }
    _write_json(args.manifest_out, manifest)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "manifest_path": args.manifest_out,
        "total_families": len(families),
        "full_families": full_families,
        "growth_ready_families": growth_ready,
        "reasons": sorted(set(reasons)),
        "families": families,
        "sources": {"modelica_library_registry": args.modelica_library_registry},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_families": len(families), "full_families": full_families}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
