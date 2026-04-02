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
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return "".join(ch if ch.isalnum() else "_" for ch in t).strip("_") or default


def _extract_models(payload: dict) -> list[dict]:
    rows = payload.get("models") if isinstance(payload.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _append_unique(values: list[str], value: str, max_items: int = 12) -> list[str]:
    v = str(value or "").strip()
    if not v:
        return values
    out = [str(x) for x in values if str(x).strip()]
    if v in out:
        return out
    out.append(v)
    return out[-max_items:]


def _canonical_id(row: dict) -> str:
    structure_hash = str(row.get("structure_hash") or "").strip()
    checksum = str(row.get("checksum_sha256") or "").strip()
    source_path = str(row.get("source_path") or "").strip()
    signature = "|".join([structure_hash, checksum, source_path])
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return f"canon_{digest[:16]}"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Canonical Registry v2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- current_unique_models: `{payload.get('current_unique_models')}`",
        f"- canonical_total_models: `{payload.get('canonical_total_models')}`",
        f"- canonical_new_models: `{payload.get('canonical_new_models')}`",
        f"- canonical_net_growth_models: `{payload.get('canonical_net_growth_models')}`",
        f"- canonical_new_large_models: `{payload.get('canonical_new_large_models')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build persistent canonical real-model registry across runs")
    parser.add_argument("--current-executable-registry", required=True)
    parser.add_argument("--previous-canonical-registry", default=None)
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--out-registry", default="artifacts/dataset_real_model_canonical_registry_v2/registry.json")
    parser.add_argument("--out", default="artifacts/dataset_real_model_canonical_registry_v2/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current_payload = _load_json(args.current_executable_registry)
    previous_payload = _load_json(args.previous_canonical_registry)
    now = datetime.now(timezone.utc).isoformat()
    run_tag = str(args.run_tag or now[:19].replace(":", "").replace("-", ""))

    reasons: list[str] = []
    if not current_payload:
        reasons.append("current_executable_registry_missing")

    current_rows = _extract_models(current_payload)
    previous_rows = _extract_models(previous_payload)

    previous_map: dict[str, dict] = {}
    for row in previous_rows:
        cid = str(row.get("canonical_id") or "").strip()
        if not cid:
            continue
        previous_map[cid] = dict(row)

    current_unique: dict[str, dict] = {}
    current_duplicate_collisions = 0
    for row in current_rows:
        cid = _canonical_id(row)
        if cid in current_unique:
            current_duplicate_collisions += 1
            continue
        current_unique[cid] = row

    merged: dict[str, dict] = {k: dict(v) for k, v in previous_map.items()}
    new_count = 0
    existing_count = 0
    new_large_count = 0

    for cid, row in current_unique.items():
        model_id = str(row.get("model_id") or "")
        source_path = str(row.get("source_path") or "")
        source_name = str(row.get("source_name") or "")
        scale = _slug(row.get("suggested_scale"), default="small")
        checksum = str(row.get("checksum_sha256") or "")
        structure_hash = str(row.get("structure_hash") or "")

        if cid in merged:
            existing_count += 1
            prev = merged[cid]
            merged[cid] = {
                **prev,
                "canonical_id": cid,
                "latest_model_id": model_id or str(prev.get("latest_model_id") or ""),
                "latest_source_path": source_path or str(prev.get("latest_source_path") or ""),
                "latest_scale": scale or str(prev.get("latest_scale") or "small"),
                "checksum_sha256": checksum or str(prev.get("checksum_sha256") or ""),
                "structure_hash": structure_hash or str(prev.get("structure_hash") or ""),
                "model_ids": _append_unique(prev.get("model_ids") if isinstance(prev.get("model_ids"), list) else [], model_id),
                "source_paths": _append_unique(prev.get("source_paths") if isinstance(prev.get("source_paths"), list) else [], source_path),
                "source_names": _append_unique(prev.get("source_names") if isinstance(prev.get("source_names"), list) else [], source_name),
                "scales_seen": _append_unique(prev.get("scales_seen") if isinstance(prev.get("scales_seen"), list) else [], scale),
                "last_seen_run_tag": run_tag,
                "last_seen_utc": now,
                "seen_batches": _to_int(prev.get("seen_batches", 0)) + 1,
            }
            continue

        new_count += 1
        if scale == "large":
            new_large_count += 1
        merged[cid] = {
            "canonical_id": cid,
            "latest_model_id": model_id,
            "latest_source_path": source_path,
            "latest_scale": scale,
            "checksum_sha256": checksum,
            "structure_hash": structure_hash,
            "model_ids": _append_unique([], model_id),
            "source_paths": _append_unique([], source_path),
            "source_names": _append_unique([], source_name),
            "scales_seen": _append_unique([], scale),
            "first_seen_run_tag": run_tag,
            "first_seen_utc": now,
            "last_seen_run_tag": run_tag,
            "last_seen_utc": now,
            "seen_batches": 1,
        }

    canonical_rows = sorted(merged.values(), key=lambda x: str(x.get("canonical_id") or ""))
    canonical_total = len(canonical_rows)
    previous_total = len(previous_map)
    net_growth = canonical_total - previous_total
    canonical_large_total = len([x for x in canonical_rows if str(x.get("latest_scale") or "") == "large"])

    alerts: list[str] = []
    if canonical_total == 0:
        alerts.append("canonical_registry_empty")
    if new_count == 0:
        alerts.append("canonical_new_models_zero")
    if new_large_count == 0:
        alerts.append("canonical_new_large_models_zero")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    _write_json(
        args.out_registry,
        {
            "schema_version": "real_model_canonical_registry_v2",
            "generated_at_utc": now,
            "run_tag": run_tag,
            "models": canonical_rows,
        },
    )

    payload = {
        "generated_at_utc": now,
        "status": status,
        "run_tag": run_tag,
        "current_unique_models": len(current_unique),
        "current_duplicate_collisions": current_duplicate_collisions,
        "canonical_total_models": canonical_total,
        "canonical_large_total_models": canonical_large_total,
        "canonical_previous_total_models": previous_total,
        "canonical_existing_models": existing_count,
        "canonical_new_models": new_count,
        "canonical_net_growth_models": net_growth,
        "canonical_new_large_models": new_large_count,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "artifacts": {"out_registry": args.out_registry},
        "sources": {
            "current_executable_registry": args.current_executable_registry,
            "previous_canonical_registry": args.previous_canonical_registry,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "canonical_total_models": canonical_total,
                "canonical_new_models": new_count,
                "canonical_net_growth_models": net_growth,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
