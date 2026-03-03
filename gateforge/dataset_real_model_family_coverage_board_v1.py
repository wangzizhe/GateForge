from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path


FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fluid": ("fluid", "hydraulic", "pipe", "tank", "valve", "pump"),
    "thermal": ("thermal", "heat", "temperature", "boiler", "conductor"),
    "electrical": ("electrical", "voltage", "current", "power", "circuit"),
    "mechanical": ("mechanical", "mass", "spring", "damper", "gear", "rotational"),
    "control": ("control", "controller", "pid", "signal", "regulation"),
    "multi_domain": ("multibody", "multi", "system", "plant", "hybrid"),
}


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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or default


def _infer_family(*, source_path: str, model_name: str, source_name: str) -> str:
    text = " ".join([source_path, model_name, source_name]).lower()
    for family, keywords in FAMILY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return family
    p = Path(source_path)
    parent = _slug(p.parent.name, default="other")
    if parent and parent not in {"", ".", "modelica"}:
        return f"other_{parent}"
    return "other"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _entropy(counts: list[int]) -> float:
    total = sum(max(0, c) for c in counts)
    if total <= 0:
        return 0.0
    val = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        val -= p * math.log(p, 2)
    return round(val, 4)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Family Coverage Board v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- covered_families: `{payload.get('covered_families')}`",
        f"- total_models: `{payload.get('total_models')}`",
        f"- family_entropy: `{payload.get('family_entropy')}`",
        f"- large_model_ratio: `{payload.get('large_model_ratio')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute model family coverage for real Modelica pool")
    parser.add_argument("--executable-registry", required=True)
    parser.add_argument("--mutation-manifest", default=None)
    parser.add_argument("--min-covered-families", type=int, default=4)
    parser.add_argument("--min-family-entropy", type=float, default=1.6)
    parser.add_argument("--min-large-model-ratio", type=float, default=0.15)
    parser.add_argument("--out", default="artifacts/dataset_real_model_family_coverage_board_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.executable_registry)
    mutation_manifest = _load_json(args.mutation_manifest)
    reasons: list[str] = []
    if not registry:
        reasons.append("executable_registry_missing")

    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    model_rows = [r for r in rows if isinstance(r, dict) and str(r.get("asset_type") or "") == "model_source"]
    mutations = mutation_manifest.get("mutations") if isinstance(mutation_manifest.get("mutations"), list) else []

    model_family: dict[str, str] = {}
    family_stats: dict[str, dict[str, int]] = {}
    large_models = 0
    for row in model_rows:
        model_id = str(row.get("model_id") or "")
        source_path = str(row.get("source_path") or "")
        source_name = str(row.get("source_name") or "")
        model_name = str(row.get("name") or Path(source_path).stem)
        family = _infer_family(source_path=source_path, model_name=model_name, source_name=source_name)
        model_family[model_id] = family
        if family not in family_stats:
            family_stats[family] = {"model_count": 0, "large_model_count": 0, "mutation_count": 0}
        family_stats[family]["model_count"] += 1
        if str(row.get("suggested_scale") or "").lower() == "large":
            family_stats[family]["large_model_count"] += 1
            large_models += 1

    for row in mutations:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("target_model_id") or "")
        family = model_family.get(model_id, "unknown")
        if family not in family_stats:
            family_stats[family] = {"model_count": 0, "large_model_count": 0, "mutation_count": 0}
        family_stats[family]["mutation_count"] += 1

    family_rows = [
        {
            "family": k,
            "model_count": v["model_count"],
            "large_model_count": v["large_model_count"],
            "mutation_count": v["mutation_count"],
            "large_ratio": round(v["large_model_count"] / max(1, v["model_count"]), 4),
            "mutations_per_model": round(v["mutation_count"] / max(1, v["model_count"]), 4),
        }
        for k, v in family_stats.items()
    ]
    family_rows.sort(key=lambda r: (-_to_int(r.get("model_count", 0)), str(r.get("family") or "")))

    total_models = len(model_rows)
    covered_families = len([r for r in family_rows if _to_int(r.get("model_count", 0)) > 0])
    family_entropy = _entropy([_to_int(r.get("model_count", 0)) for r in family_rows if str(r.get("family") or "") != "unknown"])
    large_model_ratio = round(large_models / max(1, total_models), 4)

    alerts: list[str] = []
    if total_models == 0:
        alerts.append("no_models_in_registry")
    if covered_families < int(args.min_covered_families):
        alerts.append("covered_families_below_threshold")
    if family_entropy < float(args.min_family_entropy):
        alerts.append("family_entropy_low")
    if large_model_ratio < float(args.min_large_model_ratio):
        alerts.append("large_model_ratio_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_models": total_models,
        "covered_families": covered_families,
        "family_entropy": family_entropy,
        "large_model_ratio": large_model_ratio,
        "families": family_rows,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "executable_registry": args.executable_registry,
            "mutation_manifest": args.mutation_manifest,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "covered_families": covered_families, "total_models": total_models}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
