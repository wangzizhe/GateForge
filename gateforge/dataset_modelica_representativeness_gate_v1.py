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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    rows = sorted(values)
    n = len(rows)
    mid = n // 2
    if n % 2 == 1:
        return round(rows[mid], 2)
    return round((rows[mid - 1] + rows[mid]) / 2.0, 2)


def _complexity_threshold(scale: str) -> int:
    if scale == "large":
        return 260
    if scale == "medium":
        return 120
    return 40


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Representativeness Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- representativeness_score: `{payload.get('representativeness_score')}`",
        f"- model_source_count: `{payload.get('model_source_count')}`",
        f"- representative_model_count: `{payload.get('representative_model_count')}`",
        f"- representative_ratio_pct: `{payload.get('representative_ratio_pct')}`",
        f"- large_model_count: `{payload.get('large_model_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate Modelica model-asset representativeness for moat evidence")
    parser.add_argument("--modelica-library-registry-summary", required=True)
    parser.add_argument("--model-asset-inventory-report-summary", default=None)
    parser.add_argument("--real-model-intake-portfolio-summary", default=None)
    parser.add_argument("--min-model-source-count", type=int, default=6)
    parser.add_argument("--min-large-model-count", type=int, default=1)
    parser.add_argument("--min-representative-ratio-pct", type=float, default=45.0)
    parser.add_argument("--out", default="artifacts/dataset_modelica_representativeness_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry_summary = _load_json(args.modelica_library_registry_summary)
    inventory = _load_json(args.model_asset_inventory_report_summary)
    portfolio = _load_json(args.real_model_intake_portfolio_summary)

    reasons: list[str] = []
    if not registry_summary:
        reasons.append("modelica_library_registry_summary_missing")

    registry = _load_json(str(registry_summary.get("registry_path") or ""))
    if registry_summary and not registry:
        reasons.append("modelica_library_registry_missing")

    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    model_rows = [x for x in rows if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source"]

    complexities: list[float] = []
    representative = 0
    large_models = 0
    medium_models = 0
    source_names: set[str] = set()

    for row in model_rows:
        scale = str(row.get("suggested_scale") or "small").strip().lower()
        comp = row.get("complexity") if isinstance(row.get("complexity"), dict) else {}
        score = _to_int(comp.get("complexity_score", 0))
        complexities.append(float(score))
        source = str(row.get("source_name") or "").strip()
        if source:
            source_names.add(source)
        if scale == "large":
            large_models += 1
        if scale == "medium":
            medium_models += 1
        if score >= _complexity_threshold(scale):
            representative += 1

    model_source_count = len(model_rows)
    representative_ratio = round((representative / model_source_count) * 100.0, 2) if model_source_count > 0 else 0.0
    median_complexity_score = _median(complexities)

    inventory_total = _to_int(inventory.get("total_models", 0)) if inventory else 0
    portfolio_real = _to_int(portfolio.get("total_real_models", 0)) if portfolio else 0

    representativeness_score = round(
        max(
            0.0,
            min(
                100.0,
                (representative_ratio * 0.45)
                + (min(100.0, model_source_count * 10.0) * 0.2)
                + (min(100.0, large_models * 30.0) * 0.15)
                + (min(100.0, median_complexity_score / 4.0) * 0.2),
            ),
        ),
        2,
    )

    alerts: list[str] = []
    if model_source_count < int(args.min_model_source_count):
        alerts.append("model_source_count_below_target")
    if large_models < int(args.min_large_model_count):
        alerts.append("large_model_count_below_target")
    if representative_ratio < float(args.min_representative_ratio_pct):
        alerts.append("representative_ratio_below_target")
    if median_complexity_score < 100.0:
        alerts.append("median_complexity_low")
    if source_names and len(source_names) < 2:
        alerts.append("source_diversity_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "representativeness_score": representativeness_score,
        "model_source_count": model_source_count,
        "medium_model_count": medium_models,
        "large_model_count": large_models,
        "representative_model_count": representative,
        "representative_ratio_pct": representative_ratio,
        "median_complexity_score": median_complexity_score,
        "source_diversity_count": len(source_names),
        "signals": {
            "inventory_total_models": inventory_total,
            "portfolio_total_real_models": portfolio_real,
            "registry_total_assets": _to_int(registry_summary.get("total_assets", 0)),
            "inventory_registry_delta": abs(model_source_count - inventory_total) if inventory else 0,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "modelica_library_registry_summary": args.modelica_library_registry_summary,
            "model_asset_inventory_report_summary": args.model_asset_inventory_report_summary,
            "real_model_intake_portfolio_summary": args.real_model_intake_portfolio_summary,
            "resolved_modelica_library_registry": str(registry_summary.get("registry_path") or ""),
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "representativeness_score": representativeness_score,
                "model_source_count": model_source_count,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
