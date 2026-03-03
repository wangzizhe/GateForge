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


def _slug(v: object, *, default: str = "unknown") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return "".join(ch if ch.isalnum() else "_" for ch in t).strip("_") or default


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _extract_rows(payload: dict, key: str) -> list[dict]:
    rows = payload.get(key) if isinstance(payload.get(key), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_manifest_map(payload: dict) -> dict[str, dict]:
    rows = _extract_rows(payload, "mutations")
    out: dict[str, dict] = {}
    for row in rows:
        mid = str(row.get("mutation_id") or "").strip()
        if mid:
            out[mid] = row
    return out


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Mismatch Triage Dataset v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- mismatch_count: `{payload.get('mismatch_count')}`",
        f"- grouped_signatures: `{payload.get('grouped_signatures')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build mismatch triage dataset from mutation validation records")
    parser.add_argument("--validation-records", required=True)
    parser.add_argument("--mutation-manifest", default=None)
    parser.add_argument("--max-groups", type=int, default=50)
    parser.add_argument("--triage-dataset-out", default="artifacts/dataset_mutation_mismatch_triage_dataset_v1/triage_dataset.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_mismatch_triage_dataset_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    records_payload = _load_json(args.validation_records)
    manifest_payload = _load_json(args.mutation_manifest)
    records = _extract_rows(records_payload, "mutation_records")
    manifest_map = _extract_manifest_map(manifest_payload) if manifest_payload else {}

    reasons: list[str] = []
    if not records_payload:
        reasons.append("validation_records_missing")

    groups: dict[str, dict] = {}
    mismatch_count = 0

    for row in records:
        stage_match = bool(row.get("stage_match"))
        type_match = bool(row.get("type_match"))
        if stage_match and type_match:
            continue

        mismatch_count += 1
        mutation_id = str(row.get("mutation_id") or "").strip()
        mrow = manifest_map.get(mutation_id, {})
        scale = _slug(mrow.get("target_scale") or row.get("target_scale"), default="unknown")
        operator = _slug(mrow.get("operator") or row.get("operator"), default="unknown")
        operator_family = _slug(mrow.get("operator_family"), default="unknown")
        expected_type = _slug(row.get("expected_failure_type"), default="unknown")
        observed_type = _slug(row.get("observed_failure_type"), default="unknown")
        expected_stage = _slug(row.get("expected_stage"), default="unknown")
        observed_stage = _slug(row.get("observed_stage"), default="unknown")

        signature = f"{scale}|{expected_type}|{observed_type}|{expected_stage}|{observed_stage}|{operator_family}|{operator}"
        bucket = groups.get(signature)
        if not bucket:
            bucket = {
                "signature": signature,
                "target_scale": scale,
                "expected_failure_type": expected_type,
                "observed_failure_type": observed_type,
                "expected_stage": expected_stage,
                "observed_stage": observed_stage,
                "operator_family": operator_family,
                "operator": operator,
                "count": 0,
                "example_mutation_ids": [],
            }
            groups[signature] = bucket
        bucket["count"] = _to_int(bucket.get("count", 0)) + 1
        if mutation_id and len(bucket["example_mutation_ids"]) < 12:
            bucket["example_mutation_ids"].append(mutation_id)

    grouped = sorted(groups.values(), key=lambda x: (-_to_int(x.get("count", 0)), str(x.get("signature") or "")))
    grouped = grouped[: max(1, int(args.max_groups))]

    status = "PASS"
    alerts: list[str] = []
    if reasons:
        status = "FAIL"
    elif mismatch_count > 0:
        status = "NEEDS_REVIEW"
        alerts.append("mismatch_triage_required")

    triage_dataset = {
        "schema_version": "mutation_mismatch_triage_dataset_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": grouped,
    }
    _write_json(args.triage_dataset_out, triage_dataset)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mismatch_count": mismatch_count,
        "grouped_signatures": len(grouped),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "triage_dataset_path": args.triage_dataset_out,
        "sources": {
            "validation_records": args.validation_records,
            "mutation_manifest": args.mutation_manifest,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "mismatch_count": mismatch_count, "grouped_signatures": len(grouped)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
