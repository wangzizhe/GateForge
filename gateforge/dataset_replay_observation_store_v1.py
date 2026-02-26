from __future__ import annotations

import argparse
import hashlib
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


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _extract_rows(raw: dict) -> list[dict]:
    rows = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _final_attempt(row: dict) -> dict:
    attempts = row.get("attempts") if isinstance(row.get("attempts"), list) else []
    last = attempts[-1] if attempts and isinstance(attempts[-1], dict) else {}
    return last


def _observation_id(row: dict) -> str:
    final = _final_attempt(row)
    basis = json.dumps(
        {
            "mutation_id": str(row.get("mutation_id") or ""),
            "target_model_id": str(row.get("target_model_id") or ""),
            "target_scale": str(row.get("target_scale") or ""),
            "repro_command": str(row.get("repro_command") or ""),
            "return_code": final.get("return_code"),
            "timed_out": bool(final.get("timed_out", False)),
            "exception": str(final.get("exception") or ""),
        },
        sort_keys=True,
    )
    return _sha256_text(basis)[:20]


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t:
            continue
        try:
            obj = json.loads(t)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(x, ensure_ascii=True) for x in rows) + ("\n" if rows else "")
    path.write_text(text, encoding="utf-8")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Replay Observation Store v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- ingested_records: `{payload.get('ingested_records')}`",
        f"- duplicate_records_skipped: `{payload.get('duplicate_records_skipped')}`",
        f"- total_store_records: `{payload.get('total_store_records')}`",
        f"- unique_mutation_ids_in_store: `{payload.get('unique_mutation_ids_in_store')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist mutation replay observations into appendable/deduped jsonl store")
    parser.add_argument("--raw-observations", required=True)
    parser.add_argument("--store-path", default="artifacts/dataset_replay_observation_store_v1/observations.jsonl")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", default="artifacts/dataset_replay_observation_store_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    raw = _load_json(args.raw_observations)
    rows = _extract_rows(raw)

    reasons: list[str] = []
    if not raw:
        reasons.append("raw_observations_missing")
    if not rows:
        reasons.append("raw_observations_empty")

    store_path = Path(args.store_path)
    existing = _load_jsonl(store_path)
    by_id: dict[str, dict] = {}

    for row in existing:
        oid = str(row.get("observation_id") or "")
        if oid:
            by_id[oid] = row

    run_id = str(args.run_id or f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    ingested = 0
    duplicate = 0

    for row in rows:
        oid = _observation_id(row)
        if oid in by_id:
            duplicate += 1
            continue

        final = _final_attempt(row)
        record = {
            "observation_id": oid,
            "run_id": run_id,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "mutation_id": str(row.get("mutation_id") or ""),
            "target_model_id": str(row.get("target_model_id") or ""),
            "target_scale": str(row.get("target_scale") or ""),
            "execution_status": str(row.get("execution_status") or ""),
            "attempt_count": int(row.get("attempt_count") or 0),
            "final_return_code": final.get("return_code"),
            "timed_out": bool(final.get("timed_out", False)),
            "exception": str(final.get("exception") or ""),
            "duration_sec": final.get("duration_sec"),
            "repro_command": str(row.get("repro_command") or ""),
            "stdout": str(final.get("stdout") or ""),
            "stderr": str(final.get("stderr") or ""),
            "source_raw_observations": args.raw_observations,
        }
        by_id[oid] = record
        ingested += 1

    final_rows = sorted(by_id.values(), key=lambda x: str(x.get("observation_id") or ""))
    _write_jsonl(store_path, final_rows)

    unique_mutation_ids = len({str(x.get("mutation_id") or "") for x in final_rows if x.get("mutation_id")})

    status = "PASS"
    if "raw_observations_missing" in reasons:
        status = "FAIL"
    elif ingested == 0:
        if reasons:
            status = "NEEDS_REVIEW"
        else:
            reasons.append("no_new_records_ingested")
            status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "store_path": str(store_path),
        "run_id": run_id,
        "ingested_records": ingested,
        "duplicate_records_skipped": duplicate,
        "total_store_records": len(final_rows),
        "unique_mutation_ids_in_store": unique_mutation_ids,
        "reasons": sorted(set(reasons)),
        "sources": {"raw_observations": args.raw_observations},
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "ingested_records": ingested, "total_store_records": len(final_rows)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
