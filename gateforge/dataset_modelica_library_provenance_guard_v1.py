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


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _is_nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Library Provenance Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- provenance_completeness_pct: `{payload.get('provenance_completeness_pct')}`",
        f"- reproducibility_completeness_pct: `{payload.get('reproducibility_completeness_pct')}`",
        f"- unknown_license_ratio_pct: `{payload.get('unknown_license_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Modelica registry provenance and reproducibility metadata quality")
    parser.add_argument("--modelica-library-registry", required=True)
    parser.add_argument("--open-source-intake-summary", default=None)
    parser.add_argument("--modelica-library-expansion-plan-summary", default=None)
    parser.add_argument("--max-unknown-license-ratio-pct", type=float, default=20.0)
    parser.add_argument("--min-provenance-completeness-pct", type=float, default=95.0)
    parser.add_argument("--min-reproducibility-completeness-pct", type=float, default=95.0)
    parser.add_argument("--out", default="artifacts/dataset_modelica_library_provenance_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.modelica_library_registry)
    intake = _load_json(args.open_source_intake_summary)
    expansion = _load_json(args.modelica_library_expansion_plan_summary)

    reasons: list[str] = []
    if not registry:
        reasons.append("modelica_library_registry_missing")

    rows = _extract_models(registry)
    total = len(rows)
    if registry and total == 0:
        reasons.append("modelica_library_registry_empty")

    provenance_ok = 0
    reproducibility_ok = 0
    unknown_license = 0
    source_names: set[str] = set()
    missing_fields: dict[str, int] = {}

    for row in rows:
        required_provenance = [
            "model_id",
            "source_path",
            "source_name",
            "license_tag",
            "checksum_sha256",
        ]
        p_ok = True
        for key in required_provenance:
            if not _is_nonempty(row.get(key)):
                p_ok = False
                missing_fields[key] = missing_fields.get(key, 0) + 1
        if p_ok:
            provenance_ok += 1

        repro = row.get("reproducibility") if isinstance(row.get("reproducibility"), dict) else {}
        if _is_nonempty(repro.get("om_version")) and _is_nonempty(repro.get("repro_command")):
            reproducibility_ok += 1
        else:
            missing_fields["reproducibility"] = missing_fields.get("reproducibility", 0) + 1

        license_tag = str(row.get("license_tag") or "").strip().lower()
        if not license_tag or license_tag == "unknown":
            unknown_license += 1

        source_name = str(row.get("source_name") or "").strip()
        if source_name:
            source_names.add(source_name)

    provenance_completeness = _ratio(provenance_ok, total)
    reproducibility_completeness = _ratio(reproducibility_ok, total)
    unknown_license_ratio = _ratio(unknown_license, total)
    source_diversity_count = len(source_names)

    accepted_count = _to_int(intake.get("accepted_count", 0))
    weekly_target = _to_int(expansion.get("weekly_new_models_target", 0))

    alerts: list[str] = []
    if provenance_completeness < float(args.min_provenance_completeness_pct):
        alerts.append("provenance_completeness_below_threshold")
    if reproducibility_completeness < float(args.min_reproducibility_completeness_pct):
        alerts.append("reproducibility_completeness_below_threshold")
    if unknown_license_ratio > float(args.max_unknown_license_ratio_pct):
        alerts.append("unknown_license_ratio_above_threshold")
    if source_diversity_count < 2 and total > 0:
        alerts.append("source_diversity_low")
    if accepted_count > 0 and total < accepted_count:
        alerts.append("registry_rows_below_intake_accepted_count")
    if weekly_target >= 6 and provenance_completeness < 98.0:
        alerts.append("expansion_target_high_with_metadata_risk")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_models": total,
        "provenance_completeness_pct": provenance_completeness,
        "reproducibility_completeness_pct": reproducibility_completeness,
        "unknown_license_ratio_pct": unknown_license_ratio,
        "source_diversity_count": source_diversity_count,
        "missing_field_counts": missing_fields,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "intake_accepted_count": accepted_count,
            "expansion_weekly_new_models_target": weekly_target,
        },
        "sources": {
            "modelica_library_registry": args.modelica_library_registry,
            "open_source_intake_summary": args.open_source_intake_summary,
            "modelica_library_expansion_plan_summary": args.modelica_library_expansion_plan_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "provenance_completeness_pct": provenance_completeness,
                "unknown_license_ratio_pct": unknown_license_ratio,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
