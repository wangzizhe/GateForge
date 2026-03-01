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


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _slug(v: object, *, default: str = "unknown") -> str:
    s = str(v or "").strip().lower()
    if not s:
        return default
    return s.replace("-", "_").replace(" ", "_")


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
        "# GateForge Anchor Model Pack v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- pack_quality_score: `{payload.get('pack_quality_score')}`",
        f"- selected_cases: `{payload.get('selected_cases')}`",
        f"- selected_large_cases: `{payload.get('selected_large_cases')}`",
        f"- unique_failure_types: `{payload.get('unique_failure_types')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reproducible anchor model pack from real models and validated mutations")
    parser.add_argument("--real-model-registry", required=True)
    parser.add_argument("--validated-mutation-manifest", required=True)
    parser.add_argument("--target-cases", type=int, default=24)
    parser.add_argument("--min-large-cases", type=int, default=6)
    parser.add_argument("--out", default="artifacts/dataset_anchor_model_pack_v1/summary.json")
    parser.add_argument("--pack-out", default="artifacts/dataset_anchor_model_pack_v1/pack.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.real_model_registry)
    manifest = _load_json(args.validated_mutation_manifest)

    reasons: list[str] = []
    models = registry.get("models") if isinstance(registry.get("models"), list) else []
    muts = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    if not models:
        reasons.append("real_model_registry_missing")
    if not muts:
        reasons.append("validated_mutation_manifest_missing")

    model_scale: dict[str, str] = {}
    for m in models:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("model_id") or "").strip()
        if mid:
            model_scale[mid] = _slug(m.get("suggested_scale"), default="unknown")

    ranked: list[dict] = []
    for row in muts:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("target_model_id") or row.get("model_id") or row.get("source_model_id") or "").strip()
        scale = model_scale.get(mid, _slug(row.get("target_scale"), default="unknown"))
        ftype = _slug(row.get("expected_failure_type"), default="unknown")
        method = _slug(row.get("mutation_type") or row.get("mutator") or row.get("method"), default="unknown")
        cid = str(row.get("mutation_id") or "").strip()
        if not cid:
            continue
        priority = 0
        if scale == "large":
            priority += 4
        elif scale == "medium":
            priority += 2
        if ftype in {"solver_non_convergence", "semantic_regression", "simulate_error", "runtime_overflow"}:
            priority += 3
        if method in {"equation_flip", "boundary_swap", "parameter_shift"}:
            priority += 2
        ranked.append(
            {
                "case_id": cid,
                "model_id": mid,
                "model_scale": scale,
                "failure_type": ftype,
                "mutation_method": method,
                "priority": priority,
            }
        )

    ranked.sort(key=lambda x: (-_to_int(x.get("priority")), str(x.get("case_id") or "")))
    target = max(1, int(args.target_cases))
    selected = ranked[:target]

    selected_large = [x for x in selected if x.get("model_scale") == "large"]
    selected_failure_types = sorted({str(x.get("failure_type") or "unknown") for x in selected})
    selected_models = sorted({str(x.get("model_id") or "") for x in selected if str(x.get("model_id") or "")})

    alerts: list[str] = []
    if len(selected) < target:
        alerts.append("anchor_pack_under_target")
    if len(selected_large) < int(args.min_large_cases):
        alerts.append("anchor_pack_large_cases_below_target")
    if len(selected_failure_types) < 4:
        alerts.append("anchor_pack_failure_type_diversity_low")

    score = 50.0
    score += min(20.0, len(selected) / max(1, target) * 20.0)
    score += min(15.0, len(selected_large) * 1.5)
    score += min(15.0, len(selected_failure_types) * 2.5)
    score = round(max(0.0, min(100.0, score)), 2)

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    pack_payload = {
        "schema_version": "anchor_model_pack_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": selected,
    }
    _write_json(args.pack_out, pack_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "pack_quality_score": score,
        "selected_cases": len(selected),
        "selected_large_cases": len(selected_large),
        "selected_models": len(selected_models),
        "unique_failure_types": len(selected_failure_types),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "pack_out": args.pack_out,
        "sources": {
            "real_model_registry": args.real_model_registry,
            "validated_mutation_manifest": args.validated_mutation_manifest,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "pack_quality_score": score, "selected_cases": len(selected)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
