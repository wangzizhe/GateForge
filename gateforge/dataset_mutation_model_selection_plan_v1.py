from __future__ import annotations

import argparse
import json
import re
from collections import Counter
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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or default


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Model Selection Plan v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- candidate_models: `{payload.get('candidate_models')}`",
        f"- selected_models: `{payload.get('selected_models')}`",
        f"- selected_large_ratio_pct: `{payload.get('selected_large_ratio_pct')}`",
        f"- selected_families: `{payload.get('selected_families')}`",
        f"- selected_source_buckets: `{payload.get('selected_source_buckets')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


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


def _infer_source_bucket(row: dict) -> str:
    source_path = Path(str(row.get("source_path") or ""))
    repo = _slug(row.get("source_repo"), default="repo")
    parent = _slug(source_path.parent.name, default="root")
    grand = _slug(source_path.parent.parent.name, default="")
    if grand:
        return f"{repo}:{grand}_{parent}"
    return f"{repo}:{parent}"


def _extract_models(payload: dict) -> list[dict]:
    rows = payload.get("models") if isinstance(payload.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source"]


def _pick_best_for_scale(
    rows: list[dict],
    *,
    selected_ids: set[str],
    family_counts: Counter[str],
    source_counts: Counter[str],
) -> dict | None:
    remaining = [r for r in rows if str(r.get("model_id") or "") not in selected_ids]
    if not remaining:
        return None
    best: dict | None = None
    best_key: tuple[float, float, str] | None = None
    for row in remaining:
        family = str(row.get("_family") or "other")
        source_bucket = str(row.get("_source_bucket") or "repo:root")
        base_score = float(row.get("_base_score") or 0.0)
        bonus = 0.0
        if family_counts.get(family, 0) == 0:
            bonus += 18.0
        if source_counts.get(source_bucket, 0) == 0:
            bonus += 12.0
        penalty = float(family_counts.get(family, 0) * 14 + source_counts.get(source_bucket, 0) * 10)
        composite = base_score + bonus - penalty
        key = (composite, base_score, str(row.get("model_id") or ""))
        if best_key is None or key > best_key:
            best = row
            best_key = key
    return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Build balanced mutation model selection plan for medium/large real models")
    parser.add_argument("--executable-registry", required=True)
    parser.add_argument("--target-scales", default="medium,large")
    parser.add_argument("--max-models", type=int, default=0)
    parser.add_argument("--min-covered-scales", type=int, default=0)
    parser.add_argument("--min-large-ratio-pct", type=float, default=25.0)
    parser.add_argument("--min-covered-families", type=int, default=4)
    parser.add_argument("--min-source-buckets", type=int, default=2)
    parser.add_argument("--plan-out", default="artifacts/dataset_mutation_model_selection_plan_v1/selection_plan.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_model_selection_plan_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.executable_registry)
    reasons: list[str] = []
    if not registry:
        reasons.append("executable_registry_missing")

    target_scales = {_slug(x, default="") for x in str(args.target_scales).split(",") if _slug(x, default="")}
    if not target_scales:
        target_scales = {"medium", "large"}

    rows = _extract_models(registry)
    candidates: list[dict] = []
    for row in rows:
        scale = _slug(row.get("suggested_scale"), default="small")
        if scale not in target_scales:
            continue
        model_id = str(row.get("model_id") or "").strip()
        source_path = str(row.get("source_path") or "").strip()
        if not model_id or not source_path:
            continue
        complexity_score = _to_int(row.get("complexity_score", 0))
        family = _infer_family(
            source_path=source_path,
            model_name=str(row.get("name") or Path(source_path).stem),
            source_name=str(row.get("source_name") or ""),
        )
        source_bucket = _infer_source_bucket(row)
        scale_bonus = 120 if scale == "large" else 70 if scale == "medium" else 20
        base_score = complexity_score + scale_bonus
        enriched = dict(row)
        enriched["_scale"] = scale
        enriched["_family"] = family
        enriched["_source_bucket"] = source_bucket
        enriched["_base_score"] = base_score
        candidates.append(enriched)

    target_count = len(candidates)
    if int(args.max_models) > 0:
        target_count = min(target_count, int(args.max_models))

    selected: list[dict] = []
    selected_ids: set[str] = set()
    scale_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    selected_large = 0
    min_large_ratio = max(0.0, min(1.0, float(args.min_large_ratio_pct) / 100.0))

    required_scale_count = min(len(target_scales), max(0, int(args.min_covered_scales)))
    if required_scale_count > 0 and target_count > 0:
        preferred_scales = [s for s in ("small", "medium", "large") if s in target_scales]
        for scale in preferred_scales:
            if len(selected) >= target_count:
                break
            best_for_scale = _pick_best_for_scale(
                [r for r in candidates if str(r.get("_scale") or "") == scale],
                selected_ids=selected_ids,
                family_counts=family_counts,
                source_counts=source_counts,
            )
            if best_for_scale is None:
                continue
            best_model_id = str(best_for_scale.get("model_id") or "")
            selected.append(best_for_scale)
            selected_ids.add(best_model_id)
            scale_counts[str(best_for_scale.get("_scale") or "small")] += 1
            family_counts[str(best_for_scale.get("_family") or "other")] += 1
            source_counts[str(best_for_scale.get("_source_bucket") or "repo:root")] += 1
            if str(best_for_scale.get("_scale") or "") == "large":
                selected_large += 1
            if len(scale_counts) >= required_scale_count:
                break

    while len(selected) < target_count:
        remaining = [r for r in candidates if str(r.get("model_id") or "") not in selected_ids]
        if not remaining:
            break
        has_large_remaining = any(str(r.get("_scale") or "") == "large" for r in remaining)
        current_large_ratio = (selected_large / len(selected)) if selected else 1.0

        best: dict | None = None
        best_key: tuple[float, int, int, float, str] | None = None
        for row in remaining:
            model_id = str(row.get("model_id") or "")
            scale = str(row.get("_scale") or "small")
            family = str(row.get("_family") or "other")
            source_bucket = str(row.get("_source_bucket") or "repo:root")
            base_score = float(row.get("_base_score") or 0.0)

            bonus = 0.0
            if scale_counts.get(scale, 0) == 0:
                bonus += 48.0
            if family_counts.get(family, 0) == 0:
                bonus += 18.0
            if source_counts.get(source_bucket, 0) == 0:
                bonus += 12.0
            if selected and current_large_ratio < min_large_ratio:
                if scale == "large":
                    bonus += 90.0
                elif has_large_remaining:
                    bonus -= 28.0

            penalty = float(family_counts.get(family, 0) * 14 + source_counts.get(source_bucket, 0) * 10)
            composite = base_score + bonus - penalty
            key = (composite, 1 if scale == "large" else 0, 1 if family_counts.get(family, 0) == 0 else 0, base_score, model_id)
            if best_key is None or key > best_key:
                best = row
                best_key = key

        if best is None:
            break
        best_model_id = str(best.get("model_id") or "")
        selected.append(best)
        selected_ids.add(best_model_id)
        scale_counts[str(best.get("_scale") or "small")] += 1
        family_counts[str(best.get("_family") or "other")] += 1
        source_counts[str(best.get("_source_bucket") or "repo:root")] += 1
        if str(best.get("_scale") or "") == "large":
            selected_large += 1

    selected_rows = [
        {
            "model_id": str(r.get("model_id") or ""),
            "suggested_scale": str(r.get("_scale") or "small"),
            "family": str(r.get("_family") or "other"),
            "source_bucket": str(r.get("_source_bucket") or "repo:root"),
            "complexity_score": _to_int(r.get("complexity_score", 0)),
            "selection_base_score": _to_int(r.get("_base_score", 0)),
            "source_path": str(r.get("source_path") or ""),
        }
        for r in selected
    ]
    selected_model_ids = [str(r.get("model_id") or "") for r in selected_rows if str(r.get("model_id") or "")]
    selected_large_models = len([r for r in selected_rows if str(r.get("suggested_scale") or "") == "large"])
    selected_large_ratio_pct = round((selected_large_models / max(1, len(selected_rows))) * 100.0, 2)
    selected_scale_counts = dict(sorted(scale_counts.items(), key=lambda kv: kv[0]))
    selected_family_counts = dict(sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0])))
    selected_source_bucket_counts = dict(sorted(source_counts.items(), key=lambda kv: (-kv[1], kv[0])))
    max_family_share_pct = round((max(family_counts.values()) / max(1, len(selected_rows))) * 100.0, 2) if family_counts else 0.0

    alerts: list[str] = []
    if not candidates:
        alerts.append("candidate_models_empty")
    if not selected_rows:
        alerts.append("selected_models_empty")
    if selected_large_ratio_pct < float(args.min_large_ratio_pct):
        alerts.append("selected_large_ratio_below_threshold")
    if int(args.min_covered_scales) > 0 and len(selected_scale_counts) < int(args.min_covered_scales):
        alerts.append("selected_scale_coverage_below_threshold")
    if len(selected_family_counts) < int(args.min_covered_families):
        alerts.append("selected_family_coverage_below_threshold")
    if len(selected_source_bucket_counts) < int(args.min_source_buckets):
        alerts.append("selected_source_bucket_coverage_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    plan_payload = {
        "schema_version": "mutation_model_selection_plan_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_scales": sorted(target_scales),
        "selected_model_ids": selected_model_ids,
        "selected_models": selected_rows,
    }
    _write_json(args.plan_out, plan_payload)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "candidate_models": len(candidates),
        "selected_models": len(selected_rows),
        "selected_large_models": selected_large_models,
        "selected_large_ratio_pct": selected_large_ratio_pct,
        "selected_scale_counts": selected_scale_counts,
        "selected_families": len(selected_family_counts),
        "selected_source_buckets": len(selected_source_bucket_counts),
        "selected_family_counts": selected_family_counts,
        "selected_source_bucket_counts": selected_source_bucket_counts,
        "max_family_share_pct": max_family_share_pct,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "artifacts": {
            "plan_out": args.plan_out,
        },
        "sources": {
            "executable_registry": args.executable_registry,
            "target_scales": sorted(target_scales),
            "max_models": int(args.max_models),
            "min_covered_scales": int(args.min_covered_scales),
            "min_large_ratio_pct": float(args.min_large_ratio_pct),
            "min_covered_families": int(args.min_covered_families),
            "min_source_buckets": int(args.min_source_buckets),
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "candidate_models": len(candidates),
                "selected_models": len(selected_rows),
                "selected_large_ratio_pct": selected_large_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
