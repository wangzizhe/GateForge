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


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _normalize_structure(text: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    no_line = re.sub(r"//.*?$", "", no_block, flags=re.M)
    no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '"s"', no_line)
    no_numbers = re.sub(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b", "0", no_strings)
    return re.sub(r"\s+", " ", no_numbers).strip().lower()


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source"]


def _extract_accepted_ids(payload: dict) -> set[str]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("candidate_id") or "").strip()
        if cid:
            out.add(cid)
    return out


def _is_executable_model_text(text: str) -> tuple[bool, str]:
    lower = text.lower()
    if "partial model " in lower:
        return False, "partial_model"
    model_match = re.search(r"(?im)^\s*model\s+([A-Za-z_]\w*)\b", text)
    if not model_match:
        return False, "model_block_missing"
    model_name = str(model_match.group(1))
    end_match = re.search(rf"(?im)^\s*end\s+{re.escape(model_name)}\s*;", text)
    if not end_match:
        return False, "model_end_missing"
    return True, "ok"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Executable Pool v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- raw_models: `{payload.get('raw_models')}`",
        f"- executable_unique_models: `{payload.get('executable_unique_models')}`",
        f"- executable_large_models: `{payload.get('executable_large_models')}`",
        f"- excluded_count: `{payload.get('excluded_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build executable and de-duplicated real Modelica model pool")
    parser.add_argument("--intake-registry-rows", required=True)
    parser.add_argument("--intake-runner-accepted", default=None)
    parser.add_argument("--out-registry", default="artifacts/dataset_real_model_executable_pool_v1/executable_registry_rows.json")
    parser.add_argument("--out", default="artifacts/dataset_real_model_executable_pool_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.intake_registry_rows)
    accepted_payload = _load_json(args.intake_runner_accepted)

    reasons: list[str] = []
    if not registry:
        reasons.append("intake_registry_rows_missing")

    models = _extract_models(registry)
    raw_models = len(models)
    accepted_ids = _extract_accepted_ids(accepted_payload) if accepted_payload else set()

    candidates: list[dict] = []
    excluded_reasons: dict[str, int] = {}
    excluded_samples: list[dict] = []

    for row in models:
        model_id = str(row.get("model_id") or "").strip()
        if accepted_ids and model_id and model_id not in accepted_ids:
            excluded_reasons["not_in_accepted_set"] = excluded_reasons.get("not_in_accepted_set", 0) + 1
            continue

        source_path = str(row.get("source_path") or "").strip()
        if not source_path:
            excluded_reasons["source_path_missing"] = excluded_reasons.get("source_path_missing", 0) + 1
            continue
        p = Path(source_path)
        if not p.exists():
            excluded_reasons["source_path_not_found"] = excluded_reasons.get("source_path_not_found", 0) + 1
            continue
        if p.name.lower() == "package.mo":
            excluded_reasons["package_mo_excluded"] = excluded_reasons.get("package_mo_excluded", 0) + 1
            continue

        text = _load_text(p)
        ok, reason = _is_executable_model_text(text)
        if not ok:
            excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            if len(excluded_samples) < 20:
                excluded_samples.append({"model_id": model_id, "source_path": source_path, "reason": reason})
            continue

        data = p.read_bytes()
        checksum = _sha256_bytes(data)
        structure_hash = _sha256_bytes(_normalize_structure(text).encode("utf-8"))
        scale = str(row.get("suggested_scale") or "").strip().lower()

        enriched = dict(row)
        enriched["source_path"] = source_path
        enriched["checksum_sha256"] = checksum
        enriched["structure_hash"] = structure_hash
        enriched["suggested_scale"] = scale if scale in {"small", "medium", "large"} else "small"
        candidates.append(enriched)

    # First dedupe by exact content checksum.
    by_checksum: dict[str, dict] = {}
    duplicate_checksum_removed = 0
    for row in candidates:
        checksum = str(row.get("checksum_sha256") or "")
        if checksum in by_checksum:
            duplicate_checksum_removed += 1
            continue
        by_checksum[checksum] = row
    checksum_unique = list(by_checksum.values())

    # Then dedupe by normalized structure hash.
    by_structure: dict[str, dict] = {}
    duplicate_structure_removed = 0
    for row in checksum_unique:
        s_hash = str(row.get("structure_hash") or "")
        if s_hash in by_structure:
            duplicate_structure_removed += 1
            continue
        by_structure[s_hash] = row
    executable_models = sorted(by_structure.values(), key=lambda x: str(x.get("model_id") or ""))

    executable_large = len([x for x in executable_models if str(x.get("suggested_scale") or "") == "large"])
    executable_medium = len([x for x in executable_models if str(x.get("suggested_scale") or "") == "medium"])
    executable_small = len([x for x in executable_models if str(x.get("suggested_scale") or "") == "small"])

    alerts: list[str] = []
    if raw_models == 0:
        alerts.append("raw_models_zero")
    if len(executable_models) == 0:
        alerts.append("executable_models_zero")
    if executable_large == 0:
        alerts.append("executable_large_models_zero")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    _write_json(
        args.out_registry,
        {
            "schema_version": "real_model_executable_registry_rows_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "models": executable_models,
        },
    )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "raw_models": raw_models,
        "accepted_candidates_count": len(accepted_ids),
        "executable_unique_models": len(executable_models),
        "executable_large_models": executable_large,
        "executable_medium_models": executable_medium,
        "executable_small_models": executable_small,
        "excluded_count": max(0, raw_models - len(executable_models)),
        "duplicate_checksum_removed_count": duplicate_checksum_removed,
        "duplicate_structure_removed_count": duplicate_structure_removed,
        "excluded_reason_counts": excluded_reasons,
        "excluded_samples": excluded_samples,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "artifacts": {
            "out_registry": args.out_registry,
        },
        "sources": {
            "intake_registry_rows": args.intake_registry_rows,
            "intake_runner_accepted": args.intake_runner_accepted,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "raw_models": raw_models,
                "executable_unique_models": len(executable_models),
                "executable_large_models": executable_large,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
