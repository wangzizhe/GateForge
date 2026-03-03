from __future__ import annotations

import argparse
import json
from collections import Counter
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


def _norm_text(v: object) -> str:
    return str(v or "").strip()


def _signature(row: dict) -> str:
    model_id = _norm_text(row.get("target_model_id") or row.get("model_id"))
    if not model_id:
        model_id = Path(_norm_text(row.get("model_path") or row.get("mutated_model_path"))).stem
    parts = [
        model_id,
        _norm_text(row.get("target_scale")),
        _norm_text(row.get("failure_type") or row.get("expected_failure_type")),
        _norm_text(row.get("operator")),
        _norm_text(row.get("expected_stage")),
        _norm_text(row.get("seed")),
    ]
    return "|".join(parts)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Signature Uniqueness Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- unique_signatures: `{payload.get('unique_signatures')}`",
        f"- duplicate_signatures: `{payload.get('duplicate_signatures')}`",
        f"- unique_signature_ratio_pct: `{payload.get('unique_signature_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard against duplicated mutation signatures inflating scale")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--min-unique-signature-ratio-pct", type=float, default=96.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_signature_uniqueness_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    rows_raw = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    rows = [r for r in rows_raw if isinstance(r, dict)]
    if manifest and not rows:
        reasons.append("mutation_manifest_empty")

    counter: Counter[str] = Counter(_signature(r) for r in rows)
    total_mutations = len(rows)
    unique_signatures = len(counter)
    duplicate_signatures = max(0, total_mutations - unique_signatures)
    unique_ratio_pct = round((unique_signatures / total_mutations) * 100.0, 4) if total_mutations > 0 else 0.0
    top_duplicate_signatures = [
        {"signature": sig, "count": count}
        for sig, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)
        if count > 1
    ][:10]

    alerts: list[str] = []
    if duplicate_signatures > 0:
        alerts.append("duplicate_mutation_signatures_detected")
    if unique_ratio_pct < float(args.min_unique_signature_ratio_pct):
        alerts.append("unique_signature_ratio_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": total_mutations,
        "unique_signatures": unique_signatures,
        "duplicate_signatures": duplicate_signatures,
        "unique_signature_ratio_pct": unique_ratio_pct,
        "min_unique_signature_ratio_pct": float(args.min_unique_signature_ratio_pct),
        "top_duplicate_signatures": top_duplicate_signatures,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {"mutation_manifest": args.mutation_manifest},
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_mutations": total_mutations,
                "unique_signature_ratio_pct": unique_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
