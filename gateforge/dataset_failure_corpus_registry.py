from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_MODEL_SCALES = ["small", "medium", "large"]


def _load_json(path: str) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_registry(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_slug(value: object, *, default: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text.replace("-", "_").replace(" ", "_")


def _extract_cases(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        rows = payload.get("cases")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _build_fingerprint(case: dict) -> str:
    basis = {
        "failure_type": _to_slug(case.get("failure_type")),
        "model_scale": _to_slug(case.get("model_scale")),
        "failure_stage": _to_slug(case.get("failure_stage")),
        "severity": _to_slug(case.get("severity")),
        "detected": bool(case.get("detected", False)),
        "false_positive": bool(case.get("false_positive", False)),
        "regressed": bool(case.get("regressed", False)),
        "model_name": str(case.get("model_name") or ""),
    }
    return _stable_hash(basis)


def _count_map(records: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in records:
        k = _to_slug(row.get(key))
        out[k] = out.get(k, 0) + 1
    return out


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Corpus Registry",
        "",
        f"- status: `{payload.get('status')}`",
        f"- corpus_version: `{payload.get('corpus_version')}`",
        f"- total_records: `{payload.get('total_records')}`",
        f"- duplicate_fingerprint_count: `{payload.get('duplicate_fingerprint_count')}`",
        f"- source_catalog_count: `{payload.get('source_catalog_count')}`",
        "",
        "## Scale Coverage",
        "",
    ]
    scale_counts = payload.get("model_scale_counts") if isinstance(payload.get("model_scale_counts"), dict) else {}
    for key in REQUIRED_MODEL_SCALES:
        lines.append(f"- {key}: `{scale_counts.get(key, 0)}`")

    lines.extend(["", "## Alerts", ""])
    alerts = payload.get("alerts")
    if isinstance(alerts, list) and alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain failure corpus registry with stable fingerprints")
    parser.add_argument("--catalog", action="append", default=[])
    parser.add_argument("--registry", default="artifacts/dataset_failure_corpus_registry/registry.json")
    parser.add_argument("--out", default="artifacts/dataset_failure_corpus_registry/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    registry_path = Path(args.registry)
    existing = _load_registry(registry_path)

    existing_by_fingerprint: dict[str, dict] = {}
    for row in existing:
        fp = str(row.get("fingerprint") or "")
        if fp:
            existing_by_fingerprint[fp] = row

    ingested_rows: list[dict] = []
    duplicate_fingerprint_count = 0

    for catalog_path in args.catalog:
        payload = _load_json(catalog_path)
        for idx, case in enumerate(_extract_cases(payload)):
            fingerprint = _build_fingerprint(case)
            if fingerprint in existing_by_fingerprint:
                duplicate_fingerprint_count += 1
                continue
            corpus_case_id = f"fc-{fingerprint[:12]}"
            row = {
                "corpus_case_id": corpus_case_id,
                "fingerprint": fingerprint,
                "registered_at_utc": now,
                "source_catalog_path": catalog_path,
                "source_case_index": idx,
                "failure_type": _to_slug(case.get("failure_type")),
                "model_scale": _to_slug(case.get("model_scale")),
                "failure_stage": _to_slug(case.get("failure_stage")),
                "severity": _to_slug(case.get("severity"), default="medium"),
                "model_name": str(case.get("model_name") or ""),
            }
            existing_by_fingerprint[fingerprint] = row
            ingested_rows.append(row)

    records = sorted(existing_by_fingerprint.values(), key=lambda x: str(x.get("corpus_case_id") or ""))
    _write_json(args.registry, records)

    fingerprints = [str(x.get("fingerprint") or "") for x in records if isinstance(x.get("fingerprint"), str)]
    corpus_version = _stable_hash(sorted(fingerprints))[:16] if fingerprints else "empty"

    model_scale_counts = _count_map(records, "model_scale")
    failure_type_counts = _count_map(records, "failure_type")
    severity_counts = _count_map(records, "severity")
    source_catalogs = sorted(set(str(x.get("source_catalog_path") or "") for x in records if x.get("source_catalog_path")))

    alerts: list[str] = []
    if not records:
        alerts.append("failure_corpus_empty")
    missing_scales = [k for k in REQUIRED_MODEL_SCALES if int(model_scale_counts.get(k, 0) or 0) == 0]
    if missing_scales:
        alerts.append("model_scale_coverage_incomplete")
    if duplicate_fingerprint_count > 0:
        alerts.append("duplicate_fingerprint_detected")

    status = "PASS"
    if "failure_corpus_empty" in alerts:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": now,
        "status": status,
        "corpus_version": corpus_version,
        "registry_path": args.registry,
        "catalog_count": len(args.catalog),
        "source_catalog_count": len(source_catalogs),
        "ingested_count": len(ingested_rows),
        "total_records": len(records),
        "unique_fingerprint_count": len(fingerprints),
        "duplicate_fingerprint_count": duplicate_fingerprint_count,
        "missing_model_scales": missing_scales,
        "model_scale_counts": model_scale_counts,
        "failure_type_counts": failure_type_counts,
        "severity_counts": severity_counts,
        "alerts": alerts,
        "sources": {"catalog_paths": args.catalog},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "total_records": summary.get("total_records")}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
