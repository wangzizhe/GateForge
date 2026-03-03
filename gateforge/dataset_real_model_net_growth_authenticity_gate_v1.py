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


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Net Growth Authenticity Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- canonical_new_models: `{payload.get('canonical_new_models')}`",
        f"- net_new_unique_models: `{payload.get('net_new_unique_models')}`",
        f"- true_growth_ratio_pct: `{payload.get('true_growth_ratio_pct')}`",
        f"- suspected_duplicate_ratio_pct: `{payload.get('suspected_duplicate_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Assess whether canonical new models are authentic net growth")
    parser.add_argument("--canonical-registry-summary", required=True)
    parser.add_argument("--canonical-registry", required=True)
    parser.add_argument("--min-true-growth-ratio-pct", type=float, default=70.0)
    parser.add_argument("--max-suspected-duplicate-ratio-pct", type=float, default=30.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_net_growth_authenticity_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    summary = _load_json(args.canonical_registry_summary)
    registry = _load_json(args.canonical_registry)
    reasons: list[str] = []
    if not summary:
        reasons.append("canonical_registry_summary_missing")
    if not registry:
        reasons.append("canonical_registry_missing")

    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    run_tag = str(summary.get("run_tag") or "").strip()
    if not run_tag and not reasons:
        reasons.append("canonical_run_tag_missing")

    new_rows = [r for r in rows if isinstance(r, dict) and str(r.get("first_seen_run_tag") or "") == run_tag]
    old_rows = [r for r in rows if isinstance(r, dict) and str(r.get("first_seen_run_tag") or "") != run_tag]

    old_structure = {str(r.get("structure_hash") or "") for r in old_rows if str(r.get("structure_hash") or "")}
    old_checksum = {str(r.get("checksum_sha256") or "") for r in old_rows if str(r.get("checksum_sha256") or "")}

    suspicious_samples: list[dict] = []
    suspicious_duplicate_count = 0
    for row in new_rows:
        structure_hash = str(row.get("structure_hash") or "")
        checksum = str(row.get("checksum_sha256") or "")
        suspicious = False
        reason = ""
        if structure_hash and structure_hash in old_structure:
            suspicious = True
            reason = "structure_hash_seen_before"
        elif checksum and checksum in old_checksum:
            suspicious = True
            reason = "checksum_seen_before"
        if suspicious:
            suspicious_duplicate_count += 1
            if len(suspicious_samples) < 20:
                suspicious_samples.append(
                    {
                        "canonical_id": str(row.get("canonical_id") or ""),
                        "latest_model_id": str(row.get("latest_model_id") or ""),
                        "latest_source_path": str(row.get("latest_source_path") or ""),
                        "reason": reason,
                    }
                )

    canonical_new_models = len(new_rows)
    net_new_unique_models = max(0, canonical_new_models - suspicious_duplicate_count)
    true_growth_ratio_pct = _ratio(net_new_unique_models, canonical_new_models)
    suspected_duplicate_ratio_pct = _ratio(suspicious_duplicate_count, canonical_new_models)
    summary_new = _to_int(summary.get("canonical_new_models", 0))
    summary_mismatch = abs(summary_new - canonical_new_models)

    new_large = len([r for r in new_rows if str(r.get("latest_scale") or "") == "large"])
    net_new_unique_large = max(
        0,
        len(
            [
                r
                for r in new_rows
                if str(r.get("latest_scale") or "") == "large"
                and str(r.get("structure_hash") or "") not in old_structure
                and str(r.get("checksum_sha256") or "") not in old_checksum
            ]
        ),
    )

    alerts: list[str] = []
    if canonical_new_models <= 0:
        alerts.append("canonical_new_models_zero")
    if true_growth_ratio_pct < float(args.min_true_growth_ratio_pct):
        alerts.append("true_growth_ratio_below_threshold")
    if suspected_duplicate_ratio_pct > float(args.max_suspected_duplicate_ratio_pct):
        alerts.append("suspected_duplicate_ratio_above_threshold")
    if summary_mismatch > 0:
        alerts.append("canonical_new_models_summary_mismatch")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "run_tag": run_tag,
        "canonical_new_models": canonical_new_models,
        "canonical_new_models_from_summary": summary_new,
        "canonical_new_models_summary_mismatch": summary_mismatch,
        "suspicious_duplicate_new_models": suspicious_duplicate_count,
        "suspected_duplicate_ratio_pct": suspected_duplicate_ratio_pct,
        "net_new_unique_models": net_new_unique_models,
        "true_growth_ratio_pct": true_growth_ratio_pct,
        "canonical_new_large_models": new_large,
        "net_new_unique_large_models": net_new_unique_large,
        "suspicious_samples": suspicious_samples,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "canonical_registry_summary": args.canonical_registry_summary,
            "canonical_registry": args.canonical_registry,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "canonical_new_models": canonical_new_models,
                "net_new_unique_models": net_new_unique_models,
                "true_growth_ratio_pct": true_growth_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
