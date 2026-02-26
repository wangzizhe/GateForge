from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "failure_corpus_db_v1"
REQUIRED_FIELDS = [
    "case_id",
    "fingerprint",
    "model_scale",
    "failure_type",
    "failure_stage",
    "severity",
    "reproducibility",
]


def _load_json_any(path: str | None) -> object:
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


def _slug(v: object, *, default: str = "unknown") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _extract_registry_records(raw: object) -> list[dict]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        rows = raw.get("records")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _normalize_row(row: dict, idx: int, repro_defaults: dict) -> dict:
    case_id = str(row.get("corpus_case_id") or row.get("case_id") or f"fcdb-{idx:06d}")
    repro = row.get("reproducibility") if isinstance(row.get("reproducibility"), dict) else {}
    simulator_version = str(repro.get("simulator_version") or repro_defaults.get("simulator_version") or "unknown")
    seed = int(repro.get("seed") or repro_defaults.get("seed") or 0)
    scenario_hash = str(repro.get("scenario_hash") or repro_defaults.get("scenario_hash") or "unknown")
    repro_command = str(repro.get("repro_command") or repro_defaults.get("repro_command") or "unknown")

    return {
        "case_id": case_id,
        "fingerprint": str(row.get("fingerprint") or ""),
        "model_scale": _slug(row.get("model_scale")),
        "failure_type": _slug(row.get("failure_type")),
        "failure_stage": _slug(row.get("failure_stage")),
        "severity": _slug(row.get("severity"), default="medium"),
        "model_name": str(row.get("model_name") or ""),
        "source_catalog_path": str(row.get("source_catalog_path") or ""),
        "registered_at_utc": str(row.get("registered_at_utc") or ""),
        "reproducibility": {
            "simulator_version": simulator_version,
            "seed": seed,
            "scenario_hash": scenario_hash,
            "repro_command": repro_command,
        },
    }


def _completeness_ratio(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    ok = 0
    for row in rows:
        def field_ok(key: str) -> bool:
            if key not in row:
                return False
            value = row.get(key)
            if value is None or value == "":
                return False
            if isinstance(value, dict) and not value:
                return False
            return True

        if all(field_ok(k) for k in REQUIRED_FIELDS):
            ok += 1
    return round((ok / len(rows)) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Corpus DB v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        f"- completeness_ratio_pct: `{payload.get('completeness_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized failure corpus database v1 with reproducibility metadata")
    parser.add_argument("--failure-corpus-registry", required=True)
    parser.add_argument("--repro-defaults", default=None)
    parser.add_argument("--db-out", default="artifacts/dataset_failure_corpus_db_v1/db.json")
    parser.add_argument("--out", default="artifacts/dataset_failure_corpus_db_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry_raw = _load_json_any(args.failure_corpus_registry)
    repro_defaults_raw = _load_json_any(args.repro_defaults)
    repro_defaults = repro_defaults_raw if isinstance(repro_defaults_raw, dict) else {}

    reasons: list[str] = []
    records = _extract_registry_records(registry_raw)
    if not records:
        reasons.append("registry_records_missing")

    db_rows = [_normalize_row(row, i + 1, repro_defaults) for i, row in enumerate(records)]
    completeness = _completeness_ratio(db_rows)

    db_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": db_rows,
    }
    _write_json(args.db_out, db_payload)

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif completeness < 98.0:
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "db_path": args.db_out,
        "total_cases": len(db_rows),
        "completeness_ratio_pct": completeness,
        "reasons": reasons,
        "sources": {
            "failure_corpus_registry": args.failure_corpus_registry,
            "repro_defaults": args.repro_defaults,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_cases": len(db_rows), "completeness_ratio_pct": completeness}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
