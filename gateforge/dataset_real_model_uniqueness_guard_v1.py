from __future__ import annotations

import argparse
import hashlib
import json
import re
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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _normalize_structure(text: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    no_line = re.sub(r"//.*?$", "", no_block, flags=re.M)
    no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '"s"', no_line)
    no_numbers = re.sub(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b", "0", no_strings)
    collapsed = re.sub(r"\s+", " ", no_numbers).strip().lower()
    return collapsed


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Uniqueness Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- unique_checksum_count: `{payload.get('unique_checksum_count')}`",
        f"- unique_structure_count: `{payload.get('unique_structure_count')}`",
        f"- duplicate_ratio_pct: `{payload.get('duplicate_ratio_pct')}`",
        f"- unique_checksum_ratio_pct: `{payload.get('unique_checksum_ratio_pct')}`",
        f"- unique_structure_ratio_pct: `{payload.get('unique_structure_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard real-model accepted set against duplicate inflation")
    parser.add_argument("--intake-runner-accepted", required=True)
    parser.add_argument("--intake-registry-rows", default=None)
    parser.add_argument("--min-unique-checksum-ratio-pct", type=float, default=92.0)
    parser.add_argument("--min-unique-structure-ratio-pct", type=float, default=88.0)
    parser.add_argument("--max-duplicate-ratio-pct", type=float, default=8.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_uniqueness_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    accepted_payload = _load_json(args.intake_runner_accepted)
    registry_payload = _load_json(args.intake_registry_rows)

    reasons: list[str] = []
    if not accepted_payload:
        reasons.append("intake_runner_accepted_missing")

    rows = accepted_payload.get("rows") if isinstance(accepted_payload.get("rows"), list) else []
    accepted_rows = [x for x in rows if isinstance(x, dict)]
    accepted_count = len(accepted_rows)
    if accepted_payload and accepted_count == 0:
        reasons.append("intake_runner_accepted_empty")

    registry_rows = registry_payload.get("models") if isinstance(registry_payload.get("models"), list) else []
    registry_by_id = {}
    for row in registry_rows:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("model_id") or "").strip()
        if model_id:
            registry_by_id[model_id] = row

    checksum_groups: dict[str, list[dict]] = {}
    structure_groups: dict[str, list[dict]] = {}
    missing_paths: list[str] = []

    for row in accepted_rows:
        model_path_text = str(row.get("model_path") or "").strip()
        candidate_id = str(row.get("candidate_id") or "").strip()
        source_url = str(row.get("source_url") or "").strip()
        if not model_path_text:
            missing_paths.append(candidate_id or "<missing_path>")
            continue
        model_path = Path(model_path_text)
        if not model_path.exists():
            missing_paths.append(model_path_text)
            continue

        data = model_path.read_bytes()
        checksum = _sha256_bytes(data)
        text = _load_text(model_path)
        structure_hash = _sha256_bytes(_normalize_structure(text).encode("utf-8"))

        registry_row = registry_by_id.get(candidate_id, {})
        meta = {
            "candidate_id": candidate_id,
            "model_path": model_path_text,
            "source_url": source_url,
            "source_name": str(registry_row.get("source_name") or ""),
            "suggested_scale": str(registry_row.get("suggested_scale") or row.get("expected_scale") or ""),
        }
        checksum_groups.setdefault(checksum, []).append(meta)
        structure_groups.setdefault(structure_hash, []).append(meta)

    unique_checksum_count = len(checksum_groups)
    unique_structure_count = len(structure_groups)
    duplicate_count = max(0, accepted_count - unique_checksum_count)
    duplicate_ratio_pct = _ratio(duplicate_count, accepted_count)
    unique_checksum_ratio_pct = _ratio(unique_checksum_count, accepted_count)
    unique_structure_ratio_pct = _ratio(unique_structure_count, accepted_count)

    duplicate_clusters_by_checksum = [
        {
            "hash": h,
            "count": len(v),
            "sample_model_paths": sorted({str(x.get("model_path") or "") for x in v})[:5],
            "sample_candidate_ids": sorted({str(x.get("candidate_id") or "") for x in v})[:5],
        }
        for h, v in checksum_groups.items()
        if len(v) > 1
    ]
    duplicate_clusters_by_checksum.sort(key=lambda x: int(x.get("count", 0)), reverse=True)

    duplicate_clusters_by_structure = [
        {
            "hash": h,
            "count": len(v),
            "sample_model_paths": sorted({str(x.get("model_path") or "") for x in v})[:5],
        }
        for h, v in structure_groups.items()
        if len(v) > 1
    ]
    duplicate_clusters_by_structure.sort(key=lambda x: int(x.get("count", 0)), reverse=True)

    alerts: list[str] = []
    if missing_paths:
        alerts.append("accepted_model_paths_missing")
    if unique_checksum_ratio_pct < float(args.min_unique_checksum_ratio_pct):
        alerts.append("unique_checksum_ratio_below_target")
    if unique_structure_ratio_pct < float(args.min_unique_structure_ratio_pct):
        alerts.append("unique_structure_ratio_below_target")
    if duplicate_ratio_pct > float(args.max_duplicate_ratio_pct):
        alerts.append("duplicate_ratio_above_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "accepted_count": accepted_count,
        "unique_checksum_count": unique_checksum_count,
        "unique_structure_count": unique_structure_count,
        "duplicate_count": duplicate_count,
        "duplicate_ratio_pct": duplicate_ratio_pct,
        "unique_checksum_ratio_pct": unique_checksum_ratio_pct,
        "unique_structure_ratio_pct": unique_structure_ratio_pct,
        "effective_unique_accepted_models": unique_checksum_count,
        "missing_model_path_count": len(missing_paths),
        "top_duplicate_clusters_by_checksum": duplicate_clusters_by_checksum[:10],
        "top_duplicate_clusters_by_structure": duplicate_clusters_by_structure[:10],
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "intake_runner_accepted": args.intake_runner_accepted,
            "intake_registry_rows": args.intake_registry_rows,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "accepted_count": accepted_count,
                "unique_checksum_count": unique_checksum_count,
                "duplicate_ratio_pct": duplicate_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
