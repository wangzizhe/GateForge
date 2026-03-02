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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _ratio(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return round((n / d) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Asset Uniqueness Index v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- asset_uniqueness_index: `{payload.get('asset_uniqueness_index')}`",
        f"- model_source_count: `{payload.get('model_source_count')}`",
        f"- unique_checksum_ratio_pct: `{payload.get('unique_checksum_ratio_pct')}`",
        f"- duplicate_model_count: `{payload.get('duplicate_model_count')}`",
        f"- source_diversity_count: `{payload.get('source_diversity_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute Modelica asset uniqueness index from registry evidence")
    parser.add_argument("--modelica-library-registry-summary", required=True)
    parser.add_argument("--modelica-library-provenance-guard-v1-summary", default=None)
    parser.add_argument("--min-unique-checksum-ratio-pct", type=float, default=95.0)
    parser.add_argument("--min-source-diversity-count", type=int, default=2)
    parser.add_argument("--out", default="artifacts/dataset_modelica_asset_uniqueness_index_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry_summary = _load_json(args.modelica_library_registry_summary)
    provenance = _load_json(args.modelica_library_provenance_guard_v1_summary)

    reasons: list[str] = []
    if not registry_summary:
        reasons.append("modelica_library_registry_summary_missing")

    registry_path = str(registry_summary.get("registry_path") or "")
    registry = _load_json(registry_path)
    if registry_summary and not registry:
        reasons.append("modelica_library_registry_missing")

    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    model_rows = [x for x in rows if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source"]

    checksums = [str(x.get("checksum_sha256") or "") for x in model_rows if str(x.get("checksum_sha256") or "")]
    model_source_count = len(model_rows)
    unique_checksum_count = len(set(checksums))
    duplicate_model_count = max(0, model_source_count - unique_checksum_count)

    sources = {str(x.get("source_name") or "").strip() for x in model_rows if str(x.get("source_name") or "").strip()}
    source_paths = [str(x.get("source_path") or "") for x in model_rows if str(x.get("source_path") or "")]
    unique_path_count = len(set(source_paths))

    unique_checksum_ratio = _ratio(unique_checksum_count, model_source_count)
    unique_path_ratio = _ratio(unique_path_count, model_source_count)
    source_diversity_count = len(sources)

    provenance_score = _to_float(provenance.get("provenance_confidence_score", 0.0))

    asset_uniqueness_index = round(
        max(
            0.0,
            min(
                100.0,
                unique_checksum_ratio * 0.55
                + unique_path_ratio * 0.2
                + min(100.0, source_diversity_count * 30.0) * 0.15
                + provenance_score * 0.1,
            ),
        ),
        2,
    )

    alerts: list[str] = []
    if model_source_count == 0:
        alerts.append("model_source_count_zero")
    if unique_checksum_ratio < float(args.min_unique_checksum_ratio_pct):
        alerts.append("unique_checksum_ratio_below_target")
    if source_diversity_count < int(args.min_source_diversity_count):
        alerts.append("source_diversity_low")
    if duplicate_model_count > 0:
        alerts.append("duplicate_models_present")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "asset_uniqueness_index": asset_uniqueness_index,
        "model_source_count": model_source_count,
        "unique_checksum_count": unique_checksum_count,
        "duplicate_model_count": duplicate_model_count,
        "unique_checksum_ratio_pct": unique_checksum_ratio,
        "unique_path_ratio_pct": unique_path_ratio,
        "source_diversity_count": source_diversity_count,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "modelica_library_registry_summary": args.modelica_library_registry_summary,
            "modelica_library_provenance_guard_v1_summary": args.modelica_library_provenance_guard_v1_summary,
            "resolved_registry_path": registry_path,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "asset_uniqueness_index": asset_uniqueness_index, "duplicate_model_count": duplicate_model_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
