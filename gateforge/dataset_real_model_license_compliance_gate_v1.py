from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ALLOWED_LICENSES = {"mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause", "mpl-2.0", "cc0-1.0"}


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
    return t.replace("-", "_").replace(" ", "_")


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model License Compliance Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_models: `{payload.get('total_models')}`",
        f"- compliant_models: `{payload.get('compliant_models')}`",
        f"- disallowed_license_count: `{payload.get('disallowed_license_count')}`",
        f"- unknown_license_ratio_pct: `{payload.get('unknown_license_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate real model registry entries by license and provenance compliance")
    parser.add_argument("--real-model-registry", required=True)
    parser.add_argument("--allow-licenses", default="mit,apache-2.0,bsd-3-clause,bsd-2-clause,mpl-2.0,cc0-1.0")
    parser.add_argument("--max-unknown-license-ratio-pct", type=float, default=5.0)
    parser.add_argument("--open-source-intake-summary", default=None)
    parser.add_argument("--modelica-library-provenance-guard-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_real_model_license_compliance_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.real_model_registry)
    intake = _load_json(args.open_source_intake_summary)
    provenance_guard = _load_json(args.modelica_library_provenance_guard_summary)

    reasons: list[str] = []
    if not registry:
        reasons.append("real_model_registry_missing")

    allowed = {_slug(x, default="") for x in str(args.allow_licenses).split(",") if _slug(x, default="")}
    if not allowed:
        allowed = set(DEFAULT_ALLOWED_LICENSES)

    models = _extract_models(registry)
    total = len(models)
    if registry and total == 0:
        reasons.append("real_model_registry_empty")

    disallowed = 0
    unknown = 0
    missing_provenance = 0
    missing_repro = 0
    compliant = 0

    for row in models:
        license_tag = _slug(row.get("license_tag"), default="unknown")
        source_path = str(row.get("source_path") or "").strip()
        checksum = str(row.get("checksum_sha256") or "").strip()
        repro = row.get("reproducibility") if isinstance(row.get("reproducibility"), dict) else {}

        is_unknown = license_tag in {"", "unknown"}
        if is_unknown:
            unknown += 1
        if license_tag not in allowed:
            disallowed += 1
        if not source_path or not checksum:
            missing_provenance += 1
        if not str(repro.get("repro_command") or "").strip():
            missing_repro += 1

        if (license_tag in allowed) and (not is_unknown) and source_path and checksum and str(repro.get("repro_command") or "").strip():
            compliant += 1

    unknown_ratio = _ratio(unknown, total)

    alerts: list[str] = []
    if disallowed > 0:
        alerts.append("disallowed_license_detected")
    if unknown_ratio > float(args.max_unknown_license_ratio_pct):
        alerts.append("unknown_license_ratio_above_threshold")
    if missing_provenance > 0:
        alerts.append("provenance_fields_missing")
    if missing_repro > 0:
        alerts.append("repro_command_missing")

    intake_accepted_count = int(intake.get("accepted_count", 0) or 0)
    if intake_accepted_count > 0 and total < intake_accepted_count:
        alerts.append("registry_count_below_intake_accepted_count")

    provenance_status = str(provenance_guard.get("status") or "")
    if provenance_status and provenance_status != "PASS":
        alerts.append("provenance_guard_not_pass")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_models": total,
        "compliant_models": compliant,
        "disallowed_license_count": disallowed,
        "unknown_license_count": unknown,
        "unknown_license_ratio_pct": unknown_ratio,
        "missing_provenance_count": missing_provenance,
        "missing_repro_command_count": missing_repro,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "intake_accepted_count": intake_accepted_count,
            "provenance_guard_status": provenance_status,
        },
        "sources": {
            "real_model_registry": args.real_model_registry,
            "open_source_intake_summary": args.open_source_intake_summary,
            "modelica_library_provenance_guard_summary": args.modelica_library_provenance_guard_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "compliant_models": compliant, "disallowed_license_count": disallowed}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
